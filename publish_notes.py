import os
import requests
import click
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("JOPLIN_DATA_API_URL")
API_TOKEN = os.getenv("JOPLIN_DATA_API_TOKEN")
SERVER_URL = os.getenv("JOPLIN_SERVER_URL")
USER = os.getenv("JOPLIN_USERNAME")
PASS = os.getenv("JOPLN_PASSWORD")
CONSUMER_KEY = os.getenv("POCKET_CONSUMER_KEY")
ACCESS_TOKEN = os.getenv("POCKET_ACCESS_TOKEN")

def add_to_pocket(url, title=None, tags=None):
    api_url = 'https://getpocket.com/v3/add'
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Accept': 'application/json'
    }
    data = {
        'consumer_key': CONSUMER_KEY,
        'access_token': ACCESS_TOKEN,
        'url': url,
    }
    if title:
        data['title'] = title
    if tags:
        data['tags'] = tags  # comma-separated string

    response = requests.post(api_url, json=data, headers=headers)
    if response.status_code == 200:
        return True
    else:
        print('Error:', response.status_code, response.text)
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

if __name__ == "__main__":
    r = requests.get(f'{API_URL}/notes', params={'token': API_TOKEN, 'limit': 10})
    if r.status_code != 200:
        print ('can\'t get session id')
        exit 
    print(r.json()['items'][2])
    note_id = r.json()['items'][2]['id']
    note_title = r.json()['items'][2]['title']

    session_id = get_session(USER, PASS)
    if session_id is None:
        print ('can\'t get session id')
        exit
    print (f"get session id  {session_id}")

    if publish_note(session_id, note_id):
        print (f"publish {note_id}")
    else:
        print (f"publish fail")

    print ('list all share')
    items = get_shares(session_id)
    for item in items:
        print (item)

    print ('add url to pocket')
    for item in items:
        if add_to_pocket(f"{SERVER_URL}/shares/{item['id']}", title = note_title, tags='python,api'):
            print (f"add {item} to pocket url")

    print ('delete all share')
    for item in items:
        if del_share(session_id, item): 
            print (f"del {item['id']}")

