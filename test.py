import requests
import json

root = "http://0.0.0.0:5000/"

def login(type, user_id):
    login_payload = {
        "type": type,
        "cred": {
            "id": user_id
        }
    }
    return requests.post(root + "login", data=json.dumps(login_payload)).json()

def create_locker():
    session_id = login("CAS", "ccong")["session_id"]
    print(requests.post(root + "lockers", data=json.dumps({"session_id": session_id})).json())

create_locker()