import requests
import time
import json

root = "http://0.0.0.0:5000/"

def log(case, output=None):
    if output:
        print(case + "\n\n" + json.dumps(output, sort_keys = True, indent = 2) + "\n\n============")
    else:
        print(case + "\n\n============")

# <login>
# Login
login_response = requests.post(root + "login", data = json.dumps({"type": "CAS", "cred": {"id": "ccong"}})).json()
session_id = login_response["session_id"]
log("Login: POST /login", session_id)
# </login>

# <create: Create a locker via POST /lockers>
locker_entity = requests.post(root + "lockers", data = json.dumps({"session_id": session_id, "notes": "A locker for testing", "packages": [{"name": "test_payload.txt", "type": "text/plain"}]})).json()
locker_id = locker_entity["id"]
log("Create locker: POST /lockers", locker_entity)
# </create>

# <upload: Upload a file to the locker>
requests.post(
        locker_entity["packages"][0]["upload_url"],
        files = {"file": ("test_payload.txt", "test payload\n")},
        data = locker_entity["packages"][0]["upload_fields"])
# </upload>

# <show: Show the locker entity>
log("Locker entity after uploading: GET /lockers/:id",
        requests.get(root + "lockers/" + locker_id,
                params={"session_id": session_id}).json())
# </show>

# <update: Extend the expiration time of the locker, and add two packages>
updated_locker_entity = requests.put(root + "lockers/" + locker_id, data = json.dumps({"session_id": session_id, "notes": "Updated locker", "extension_in_sec": 1000, "packages": [{"name": "File1.jpg", "type": "image/jpeg"}, {"name": "File2.jpg", "size_range": [5, 100]}]})).json()
log("Locker entity after updating: PUT /lockers/:id",
        updated_locker_entity)
# </update>

# <delete: Delete the locker>
requests.delete(root + "lockers/" + locker_id, data=json.dumps({"session_id": session_id}))
# </delete>