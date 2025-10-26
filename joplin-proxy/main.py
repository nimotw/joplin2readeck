import os
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException, Request
import requests
import markdown2
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("JOPLIN_DATA_API_URL")
API_TOKEN = os.getenv("JOPLIN_DATA_API_TOKEN")
ALLOWED_FOLDER_IDS = os.getenv("ALLOWED_FOLDER_IDS")
NOTES_URL_PREFIX = os.getenv("NOTES_URL_PREFIX", "")

app = FastAPI(root_path=NOTES_URL_PREFIX)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

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

@app.get("/n/{note_id}", response_class=HTMLResponse)
def get_note(note_id: str, request: Request):
    """
    # 1) optional IP whitelist
    if IP_WHITELIST:
        ip = client_ip_from_request(request)
    if not ip or ip not in IP_WHITELIST:
        raise HTTPException(status_code=403, detail="Forbidden: IP not allowed")

    # 2) check User-Agent contains "instapaper"
    ua = request.headers.get("user-agent", "")
    if "instapaper" not in ua.lower():
        raise HTTPException(status_code=403, detail="Forbidden: only Instapaper user-agent allowed")
    """

    # 3) fetch note metadata
    endpoint = f"{API_URL.rstrip('/')}/notes/{note_id}"
    #return f"<h1>Note {note_id} OK {endpoint}</h1>"
    try:
        r = requests.get(endpoint, timeout=10, params={
            'token': API_TOKEN,
            'fields': 'id, parent_id, title, body',
        })
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
    body = note.get("body", "")

    # If body already looks like HTML (contains "<html" or "<div"), we could pass it through.
    # But convert from Markdown to HTML for safe rendering:
    body_html = markdown2.markdown(body)

    title = note.get("title", "Untitled")
    html = f"""<!doctype html>
      <head>
        <title>{title}</title>
      </head>
      <body>
        {body_html}
      </body>
    </html>
    """ 
    return HTMLResponse(content=html, status_code=200)

