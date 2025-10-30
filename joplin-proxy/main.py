import os
import re
from typing import Optional, Set
from fastapi import FastAPI, HTTPException, Request
import requests
from markdown_it import MarkdownIt
from fastapi.responses import HTMLResponse, StreamingResponse
from dotenv import load_dotenv
import bleach
import logging

# 建議放在檔案開頭，設定 logging
logging.basicConfig(level=logging.INFO)

load_dotenv()

API_URL = os.getenv("JOPLIN_DATA_API_URL")
API_TOKEN = os.getenv("JOPLIN_DATA_API_TOKEN")
# parse ALLOWED_FOLDER_IDS as a comma-separated list (optional)
_allowed_folder_ids_env = os.getenv("ALLOWED_FOLDER_IDS", "")
ALLOWED_FOLDER_IDS: Optional[Set[str]] = (
    set([s.strip() for s in _allowed_folder_ids_env.split(",") if s.strip()]) or None
)
NOTES_URL_PREFIX = os.getenv("NOTES_URL_PREFIX", "")
SERVER_URL = os.getenv("JOPLIN_SERVER_URL")
USER = os.getenv("JOPLIN_USERNAME")
PASS = os.getenv("JOPLIN_PASSWORD")

# Bleach configuration: allow a reasonably safe subset of tags/attributes
ALLOWED_TAGS = list(bleach.sanitizer.ALLOWED_TAGS) + [
    "img",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "pre",
    "code",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "p",
    "ol",
    "ul",
    "li",
    "br",
]
ALLOWED_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "*": ["class", "id"],
}
ALLOWED_PROTOCOLS = list(bleach.sanitizer.ALLOWED_PROTOCOLS) + ["data", "http", "https"]

app = FastAPI(root_path=NOTES_URL_PREFIX)

def remove_p_around_img(html: str) -> str:
    # 移除 <p> 僅包住一個 <img> 的情況（允許 img 前後有空白）
    html = re.sub(r'<p>\s*(<img[^>]+>)\s*</p>', r'\1', html)
    return html


def lines_to_paragraphs(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return ''.join(f'<p>{line}</p>' for line in lines)


def get_session(user, passwd):
    url = f"{SERVER_URL}/api/sessions"
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Accept': 'application/json'
    }
    data = {
        'email': user,
        'password': passwd,
    }

    res = requests.post(url, json=data, headers=headers)

    if res.status_code != 200:
        return None
    return res.json()['id']


def client_ip_from_request(request: Request) -> Optional[str]:
    # Honor X-Forwarded-For if present (common behind ingress)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # take first
        return xff.split(",")[0].strip()
    # fallback to request.client
    client = request.client
    if client:
        return client.host
    return None


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


import json
def get_share_id(token, note_id):
    url = f"{SERVER_URL}/api/shares"
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Accept': 'application/json',
        'X-Api-Auth': token
    }
    data = {
        'note_id': note_id,
        'recursive': 0
    }

    res = requests.post(url, json=data, headers=headers)
    data_bytes = res.content
    data_str = data_bytes.decode('utf-8')
    data = json.loads(data_str)

    if res.status_code != 200:
        return ''
    else:
        return data['id']
    

def del_share_id(token, item_id):
    url = f"{SERVER_URL}/api/shares/{item_id}"
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Accept': 'application/json',
        'X-Api-Auth': token
    }

    res = requests.delete(url, headers=headers)

    if res.status_code != 200:
        return False
    else:
        return True
    

import os
import io
import mimetypes
from PIL import Image
from PIL import ImageEnhance  # 你原本沒 import，要加上

CACHE_DIR = "/tmp/joplin-cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def is_image(content_type):
    return content_type.startswith("image/")


def resize_and_convert_to_jpeg(content, max_size=(1200, 1200)):
    try:
        img = Image.open(io.BytesIO(content))
        img.thumbnail(max_size)
        # 增強對比
        #img = ImageEnhance.Contrast(img).enhance(1.3)
        # 增強亮度
        #img = ImageEnhance.Brightness(img).enhance(1.1)
        # 色彩數量壓縮
        #img = img.quantize(colors=256, method=2, dither=Image.FLOYDSTEINBERG)
        # 再轉回 RGB（JPEG 不支援 palette）
        img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70, progressive=True)  # quality 可自訂
        buf.seek(0)
        return buf.read()
    except Exception:
        logging.warning(f"resize_and_convert_to_jpeg failed: {e}")
        return content  # 如果失敗則直接回傳原始內容


@app.get("/r/{resource_id}", name="get_resource")
@app.get("/v1/r/{resource_id}", name="get_resource_v1")
def get_resource(resource_id: str):
    if not API_URL or not API_TOKEN:
        raise HTTPException(status_code=500, detail="Server misconfiguration: missing Joplin API settings")

    cache_path = os.path.join(CACHE_DIR, f"{resource_id}.jpg")
    if os.path.exists(cache_path):
        return StreamingResponse(open(cache_path, "rb"), media_type="image/jpeg")

    endpoint = f"{API_URL.rstrip('/')}/resources/{resource_id}/notes"
    try:
        r = requests.get(endpoint, timeout=10, params={"token": API_TOKEN})
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Bad Gateway: failed to contact Joplin API")
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Note not found")
    note_id = r.json()['items'][0]['id']

    token = get_session(USER, PASS)
    share_id = get_share_id(token, note_id)
    endpoint = f"{SERVER_URL.rstrip('/')}/shares/{share_id}?resource_id={resource_id}"

    try:
        r = requests.get(endpoint, stream=True, timeout=15)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Bad Gateway: failed to contact Joplin API for resource")
    if r.status_code != 200:
        raise HTTPException(status_code=404, detail=f"Resource not found status_code: {r.status_code}")

    content = r.content
    content_type = r.headers.get("Content-Type", "application/octet-stream")

    if is_image(content_type):
        jpeg_content = resize_and_convert_to_jpeg(content)
        with open(cache_path, "wb") as f:
            f.write(jpeg_content)
        return StreamingResponse(io.BytesIO(jpeg_content), media_type="image/jpeg")
    else:
        # 非圖片，直接 cache 原檔
        with open(cache_path, "wb") as f:
            f.write(content)
        return StreamingResponse(io.BytesIO(content), media_type=content_type)


def _replace_joplin_resource_links(body: str, request: Request) -> str:
    """
    Replace Joplin resource references in Markdown / HTML with proxied URLs to /v1/r/{resource_id}.

    Handles common patterns:
      - Markdown images: ![alt](:/resourceid)
      - Inline HTML images: <img src=":/resourceid" ...>
      - Plain :/resourceid inside parentheses (:/resourceid)

    Uses request.url_for to build URLs that respect app root_path and uses the v1 resource endpoint name.
    """
    # Use the v1 resource route name to ensure versioned URL is used
    url_builder = lambda resource_id: request.url_for("get_resource_v1", resource_id=resource_id)

    # pattern for markdown image: ![alt](:/resourceid)
    md_img_pattern = re.compile(r'!\[([^\]]*)\]\(:/([0-9a-fA-F\-]+)\)')
    body = md_img_pattern.sub(lambda m: f'![{m.group(1)}]({url_builder(m.group(2))})', body)

    # pattern for inline HTML img src=":/resourceid" or src=':/resourceid'
    html_img_pattern = re.compile(r'(<img\s+[^>]*src=[\'"]):/([0-9a-fA-F\-]+)([\'"][^>]*>)', flags=re.IGNORECASE)
    body = html_img_pattern.sub(lambda m: f'{m.group(1)}{url_builder(m.group(2))}{m.group(3)}', body)

    # pattern for plain :/resourceid inside parentheses e.g. (:/resourceid)
    plain_link_pattern = re.compile(r'\(:/([0-9a-fA-F\-]+)\)')
    body = plain_link_pattern.sub(lambda m: f'({url_builder(m.group(1))})', body)

    return body


@app.get("/n/{note_id}", response_class=HTMLResponse)
@app.get("/v1/n/{note_id}", response_class=HTMLResponse)
def get_note(note_id: str, request: Request):
    """
    Fetch a Joplin note and render it as HTML. Supports both /n/{id} and /v1/n/{id}.
    - Rewrites Joplin resource references (:/<id>) to proxied /v1/r/<id> URLs so images/resources display.
    - Renders Markdown with markdown-it-py (allow inline HTML).
    - Sanitizes output with bleach and linkifies bare URLs.
    """
    # 3) fetch note metadata
    if not API_URL or not API_TOKEN:
        raise HTTPException(status_code=500, detail="Server misconfiguration: missing Joplin API settings")

    endpoint = f"{API_URL.rstrip('/')}/notes/{note_id}"
    try:
        r = requests.get(endpoint, timeout=10, params={"token": API_TOKEN, "fields": "id, parent_id, title, body"})
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Bad Gateway: failed to contact Joplin API")

    if r.status_code != 200:
        raise HTTPException(status_code=404, detail="Note not found")


    note = r.json()
    parent_id = note.get("parent_id")

    # 4) check folder whitelist if configured
    if ALLOWED_FOLDER_IDS and parent_id not in ALLOWED_FOLDER_IDS:
        raise HTTPException(status_code=403, detail="Forbidden: note not in allowed folder")

    # 5) render body (Joplin stores note body in Markdown/HTML; often it's Markdown)
    body = note.get("body", "") or ""

    # Replace Joplin resource tokens (:/<id>) with proxied resource URLs (v1)
    body = _replace_joplin_resource_links(body, request)

    # Convert from Markdown to HTML using markdown-it-py and allow inline HTML
    md = MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True, "breaks": True})
    body_html = md.render(body)

    # Sanitize rendered HTML with bleach to allow a safe subset of inline HTML
    cleaned = bleach.clean(
        body_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=False,  # set to True to remove disallowed tags rather than escape them
    )

    # Ensure links are safe / have rel attributes and convert bare URLs to links
    safe_html = bleach.linkify(cleaned)

    title = note.get("title", "Untitled")
    html = f"""<!doctype html>
      <head>
        <meta charset="utf-8" />
        <title>{title}</title>
      </head>
      <body>
        {safe_html}
      </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)
