import requests
import base64

def send_to_inbox(recipient_inbox_url, payload, username, password):
    """
    Sending Outgoing Objects with Valid Credentials
    : local node sends out objects (likes, comments, posts) to remote nodes
    """
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {encoded_credentials}"
    }
    response = requests.post(recipient_inbox_url, json=payload, headers=headers)
    return response
