
import os, sys
import requests
import click
from datetime import datetime, timedelta

from dotenv import load_dotenv
from typing import List, Dict, Optional

load_dotenv()

API_URL = os.getenv("JOPLIN_DATA_API_URL")
API_TOKEN = os.getenv("JOPLIN_DATA_API_TOKEN")
SERVER_URL = os.getenv("JOPLIN_SERVER_URL")
USER = os.getenv("JOPLIN_USERNAME")
PASS = os.getenv("JOPLIN_PASSWORD")
READECK_URL = os.getenv("READECK_URL")
READECK_TOKEN = os.getenv("READECK_TOKEN")

def format_ym_week(date_str: str = None) -> str:
    """回傳 'YYYYMMWW' 格式，WW 為當月第幾週（兩位數）。預設使用今天日期。"""
    if date_str:
        date = datetime.strptime(date_str, "%Y%m%d")
    else:
        date = datetime.today()

    #first_day = date.replace(day=1)
    #first_weekday = first_day.weekday()  # 星期一為 0
    day_of_month = date.day
    #week_of_month = (day_of_month + first_weekday - 1) // 7 + 1
    week_of_month = (day_of_month) // 7 + 1
    return f"{date.strftime('%Y%m')}{week_of_month:02d}"

def ensure_yearmonth_tag(api_base_url, token, yearmonth=None):
    """
    確保 Joplin 中存在指定的 yearmonth 標籤（格式: 'YYYYMM'），若不存在則建立。

    :param api_base_url: Joplin API base URL，例如 http://localhost:41184
    :param token: Joplin API token
    :param yearmonth: 指定標籤 (預設為當月的 'YYYYMM')
    :return: tag ID（str）
    """
    if yearmonth is None:
        yearmonth = datetime.now().strftime("%Y%m")

    # 1. 查詢是否已有此標籤
    res = requests.get(f"{api_base_url}/tags", params={'token': token})
    res.raise_for_status()
    tags = res.json().get('items', [])

    for tag in tags:
        if tag['title'] == yearmonth:
            print(f"Tag '{yearmonth}' already exists with ID: {tag['id']}")
            return tag['id']

    # 2. 若無，則建立新標籤
    res = requests.post(
        f"{api_base_url}/tags",
        json={"title": yearmonth}, 
        params={'token': token}
    )
    res.raise_for_status()
    tag = res.json()
    print(f"Created tag '{yearmonth}' with ID: {tag['id']}")
    return tag['id']


def apply_tag_to_note(api_base_url, token, tag_id, note_id):
    """
    將指定 tag 套用到指定的 note。

    :param api_base_url: Joplin API base URL，例如 http://localhost:41184
    :param token: Joplin API token
    :param tag_id: 要套用的 tag ID
    :param note_id: 要套用的 note ID
    """
    url = f"{api_base_url}/tags/{tag_id}/notes"
    payload = {
        "id": note_id
    }

    res = requests.post(url, json=payload, params={'token': token})
    
    if res.status_code == 200:
        print(f"Tag {tag_id} successfully applied to note {note_id}")
    elif res.status_code == 400 and 'already' in res.text:
        print(f"Note {note_id} already has tag {tag_id}")
    else:
        res.raise_for_status()


def add_to_readeck(bookmark_url, title=None, tags=[]):
    # API endpoint to create a new bookmark
    endpoint = f"{READECK_URL}/api/bookmarks"

    # Prepare headers and payload
    headers = {
        "Authorization": f"Bearer {READECK_TOKEN}",
        "Content-Type": "application/json",
    }

    tags.append(format_ym_week())

    payload = {
        "url": bookmark_url,
        "title": title,
        "labels": tags
    }
    #print (payload)

    # Send the request
    response = requests.post(endpoint, json=payload, headers=headers)

    # Handle the response
    if response.status_code == 202:
        return True
    else:
        return False


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

def publish_note(token, note_id):
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

    if res.status_code != 200:
        return False
    else:
        return True

def get_shares(token):
    url = f"{SERVER_URL}/api/shares"
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Accept': 'application/json',
        'X-Api-Auth': token
    }

    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        return None
    return res.json()['items']

def del_share(token, item):
    url = f"{SERVER_URL}/api/shares/{item['id']}"
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


def get_filtered_notes(
    api_base_url: str,
    token: str,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    notebook_id: Optional[str] = None,
    tag_id: Optional[str] = None,
    fields: str = 'id,title,created_time,parent_id'
) -> List[Dict]:
    """
    從 Joplin Data API 取得符合條件的筆記。

    Args:
        api_base_url (str): Joplin API URL，例如 http://localhost:41184
        token (str): API token
        created_after (datetime, optional): 過濾建立時間在此之後的筆記
        created_before (datetime, optional): 過濾建立時間在此之前的筆記
        notebook_id (str, optional): 指定 notebook ID（parent_id）
        tag_id (str, optional): 指定 tag ID，會只抓該標籤下的筆記
        fields (str): 取得哪些欄位（預設 id, title, created_time, parent_id）

    Returns:
        List[Dict]: 筆記 dict 清單
    """
    after_ts = int(created_after.timestamp() * 1000) if created_after else None
    before_ts = int(created_before.timestamp() * 1000) if created_before else None

    notes = []
    page = 1
    endpoint = f"{api_base_url}/tags/{tag_id}/notes" if tag_id else f"{api_base_url}/notes"

    while True:
        response = requests.get(endpoint, params={
            'token': token,
            'fields': fields,
            'order_by': 'created_time',
            'order_dir': 'ASC',
            'limit': 100,
            'page': page
        })
        response.raise_for_status()
        items = response.json().get('items', [])
        if not items:
            break

        for note in items:
            if notebook_id and note.get('parent_id') != notebook_id:
                continue
            if after_ts and note['created_time'] <= after_ts:
                continue
            if before_ts and note['created_time'] >= before_ts:
                continue
            notes.append(note)

        page += 1

    return notes


def get_notebook_id_by_name(
    api_base_url: str,
    token: str,
    notebook_name: str
) -> Optional[str]:
    """
    根據 notebook（folder）名稱取得其 ID。

    Args:
        api_base_url (str): Joplin API base URL，例如 http://localhost:41184
        token (str): Joplin API token
        notebook_name (str): 要查找的筆記本名稱（完全比對）

    Returns:
        Optional[str]: 找到的 notebook ID，如果沒找到則回傳 None
    """
    page = 1

    while True:
        response = requests.get(f"{api_base_url}/folders", params={
            'token': token,
            'limit': 100,
            'page': page
        })
        response.raise_for_status()
        items = response.json().get('items', [])
        if not items:
            break

        for folder in items:
            if folder['title'] == notebook_name:
                return folder['id']

        page += 1

    # 若不存在，建立一個新的 notebook
    create_response = requests.post(f"{api_base_url}/folders", json={ 'title': notebook_name }, params={'token': token})

    if create_response.status_code == 200:
        return create_response.json().get('id')
    else:
        print("建立 notebook 失敗:", create_response.status_code, create_response.text)
        return None

    return None


def get_tag_id_by_name(
    api_base_url: str,
    token: str,
    tag_name: str
) -> Optional[str]:
    """
    根據 tag 名稱取得其 ID。

    Args:
        api_base_url (str): Joplin API base URL，例如 http://localhost:41184
        token (str): Joplin API token
        tag_name (str): 要查找的 tag 名稱（完全比對）

    Returns:
        Optional[str]: 找到的 tag ID，如果沒找到則回傳 None
    """
    page = 1

    while True:
        response = requests.get(f"{api_base_url}/tags", params={
            'token': token,
            'limit': 100,
            'page': page
        })
        response.raise_for_status()
        items = response.json().get('items', [])
        if not items:
            break

        for tag in items:
            if tag['title'] == tag_name:
                return tag['id']

        page += 1

    return None



def move_note_to_notebook(
    api_base_url: str,
    token: str,
    note_id: str,
    new_notebook_id: str
) -> bool:
    """
    將指定的 note 移動到另一個 notebook（folder）。

    Args:
        api_base_url (str): Joplin API base URL
        token (str): Joplin API token
        note_id (str): 要移動的筆記 ID
        new_notebook_id (str): 目標 notebook 的 ID

    Returns:
        bool: 是否成功移動
    """
    headers = {'Authorization': token}
    url = f"{api_base_url}/notes/{note_id}"
    payload = {"parent_id": new_notebook_id}

    response = requests.put(url, json=payload, params={ 'token': token })
    if response.status_code == 200:
        return True
    else:
        print("移動失敗:", response.status_code, response.text)
        return False

def pub2readeck(session_id, items, dest_nb_id, fail_nb_id):
    for note in items:
        note_id = note['id']
        note_title = note['title']

        if publish_note(session_id, note_id):
            print (f"publish:\t {note_title}")
        else:
            print (f"publish fail:\t {note_title}")

        share_items = get_shares(session_id)
        for share_item in share_items:

            tag_id = ensure_yearmonth_tag(API_URL, API_TOKEN)
            apply_tag_to_note(API_URL, API_TOKEN, tag_id, note_id)

            if add_to_readeck(f"{SERVER_URL}/shares/{share_item['id']}", title = note_title):
                print (f"add url to readeck:\t{note_title}")
                if move_note_to_notebook(API_URL, API_TOKEN, note_id, dest_nb_id):
                    print (f"move to notebook {str_year}:\t {note_title}")
                    if del_share(session_id, share_item): 
                        print (f"remove share:\t {note_title} {share_item['id']}")
            else:
                print (f"add url fail:\t {note_title}")
                if move_note_to_notebook(API_URL, API_TOKEN, note_id, fail_nb_id):
                    print (f"move to notebook fail:\t {note_title}")
                    if del_share(session_id, share_item): 
                        print (f"remove share:\t {note_title} {share_item['id']}")


if __name__ == "__main__":
    session_id = get_session(USER, PASS)
    if session_id is None:
        print ('can\'t get session id')
        sys.exit()
    print (f"get session id  {session_id}")

    CREATED_AFTER = datetime.now() - timedelta(days=2048)

    fail_nb_id = get_notebook_id_by_name(API_URL, API_TOKEN, 'fail')
    nb_id = get_notebook_id_by_name(API_URL, API_TOKEN, 'inbox')
    str_year = datetime.now().strftime('%Y')
    dest_nb_id = get_notebook_id_by_name(API_URL, API_TOKEN, str_year)

    items = get_filtered_notes(API_URL, API_TOKEN, CREATED_AFTER, None, nb_id)
    pub2readeck(session_id, items, dest_nb_id, fail_nb_id)

    print ("\ndelete all share")
    items = get_shares(session_id)
    for item in items:
        if del_share(session_id, item): 
            print (f"remove sahre:\t {item['id']}")
