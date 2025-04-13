import requests
from dotenv import load_dotenv

load_dotenv()

POCKET_CONSUMER_KEY = os.getenv("POCKET_CONSUMER_KEY")
REDIRECT_URI = ''  # can be anything

def get_request_token():
    url = 'https://getpocket.com/v3/oauth/request'
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Accept': 'application/json'
    }
    data = {
        'consumer_key': POCKET_CONSUMER_KEY,
        'redirect_uri': REDIRECT_URI
    }

    res = requests.post(url, json=data, headers=headers)
    print(res.json())  # gives request_token
    return res.json()['code']

request_token = get_request_token()
print('Go to this URL:')
print(f'https://getpocket.com/auth/authorize?request_token={request_token}&redirect_uri={REDIRECT_URI}')

input("Press Enter to continue...")

def get_access_token(request_token):
    url = 'https://getpocket.com/v3/oauth/authorize'
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Accept': 'application/json'
    }
    data = {
        'consumer_key': POCKET_CONSUMER_KEY,
        'code': request_token
    }

    res = requests.post(url, json=data, headers=headers)
    print(res.json())  # {'access_token': 'xxx', 'username': 'xxx'}
    return res.json()['access_token']

access_token = get_access_token(request_token)
print('Your Pocket Access Token:', access_token)

