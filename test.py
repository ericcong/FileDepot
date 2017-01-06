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

session_id = login("CAS", "ccong")["session_id"]

# POST /lockers
#locker = requests.post(root + "lockers", data=json.dumps({"session_id": session_id})).json()
#locker_id = locker["id"]
#print("Created locker: " + locker_id)

# GET /lockers/:id
locker_id = "55a5dacd-9f6e-4fb2-b7ac-f5bf77f35cc8"
queried_locker = requests.get(root + "lockers/" + locker_id, params={"session_id": session_id}).json()
print("Queried locker: " + json.dumps(queried_locker))