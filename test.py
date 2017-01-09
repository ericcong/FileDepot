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

# <trivial: create a locker, upload a file, retrieve the locker entity, delete the locker>

create_response = requests.post(root + "lockers", data = json.dumps({"session_id": session_id})).json()
locker_id = create_response["id"]
log("Create locker: POST /lockers", create_response)

slot = create_response["slots"][list(create_response["slots"].keys())[0]]
upload_url = slot["url"]
upload_fields = slot["fields"]
files = {"file": ("test_payload.txt", "test payload\n")}
upload_response = requests.post(upload_url, files=files, data=upload_fields)

get_response = requests.get(root + "lockers/" + locker_id, params={"session_id": session_id}).json()
log("Locker entity after uploading: GET /lockers/:id", get_response)

requests.delete(root + "lockers/" + locker_id, data=json.dumps({"session_id": session_id}))
# </trivial>

# <limited_content_size: create a locker with limited size, upload a larger file, delete it>
create_response = requests.post(root + "lockers", data = json.dumps({"session_id": session_id, "content_length_range": [0,5]})).json()
locker_id = create_response["id"]

slot = create_response["slots"][list(create_response["slots"].keys())[0]]
upload_url = slot["url"]
upload_fields = slot["fields"]
files = {"file": ("test_payload.txt", "test payload\n")}
upload_response = requests.post(upload_url, files=files, data=upload_fields)

get_response = requests.get(root + "lockers/" + locker_id, params={"session_id": session_id}).json()

log("limited_content_size", len(get_response["files"]) == 0)

requests.delete(root + "lockers/" + locker_id, data=json.dumps({"session_id": session_id}))
# </limited_content_size>

# <update_locker: create a locker, then update its size and expires>
create_response = requests.post(root + "lockers", data = json.dumps({"session_id": session_id, "size": 3, "expires_in_sec": 6000})).json()
locker_id = create_response["id"]

log("Create locker", create_response)

requests.put(root + "lockers/" + locker_id, data=json.dumps({"session_id": session_id, "expires": {"force": True, "extension_in_sec": 600}, "size": {"force": True, "extension": 10}}))

locker_entity = requests.get(root + "lockers/" + locker_id, params={"session_id": session_id}).json()
log("Updated locker", locker_entity)
# </update_locker>

# Create 10 lockers, with different expires and size
create_responses = list()
for i in range(0, 10):
    create_responses.append(requests.post(root + "lockers", data = json.dumps({"session_id": session_id, "size": i + 1, "expires_in_sec": i * 60})).json())
log("Create 10 lockers")

# Query the lockers with space between 3 and 7
query_responses = requests.get(root + "lockers", params={"session_id": session_id, "min_space": 3, "max_space": 7}).json()
log("Query lockers with space between 3 and 7: GET /lockers", query_responses)

# Query the lockers with space between 3 and 10, and size greater than 5, and expire time is after 100 seconds from now
query_responses = requests.get(root + "lockers", params={"session_id": session_id, "min_size": 3, "max_size": 10, "min_size": 5, "min_expires": int(time.time()) + 100}).json()
log("Complex query", query_responses)

# Delete the lockers
for locker in create_responses:
    requests.delete(root + "lockers/" + locker["id"], data=json.dumps({"session_id": session_id}))
log("Delete lockers")

# POST /logout
logout_response = requests.post(root + "logout", data = json.dumps({"session_id": session_id}))