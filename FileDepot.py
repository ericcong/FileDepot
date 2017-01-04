import os
import time
import uuid
import hashlib
import boto3
from flask import Flask, request
from flask_restful import Resource, Api, abort
from S3sh import S3sh

# Config
session_expire_sec = 600
s3sh = S3sh("undergrad", "FileDepot/")
db = boto3.resource("dynamodb").Table("FileDepot")

app = Flask(__name__)
api = Api(app)

sessions = dict()

def make_session(uid):
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "uid": uid,
        "expire_time": int(time.time()) + session_expire_sec
    }
    return session_id

def make_uid(request):
    try:
        json_data = request.get_json(force=True)
        return hashlib.sha256((json_data["type"] + json_data["cred"]["id"]).encode("utf-8")).hexdigest()
    except:
        abort(400)

def get_uid(session_id):
    if session_id not in sessions:
        abort(401)
    session = sessions[session_id]
    if session["expire_time"] <= int(time.time()):
        del sessions[session_id]
        abort(401)
    return session["uid"]

def delete_session(session_id):
    del sessions[session_id]

def get_session_id(request):
    try:
        return request.get_json(force=True)["session_id"]
    except:
        abort(400)

class Login(Resource):
    def post(self):
        uid = make_uid(request)
        return {"session_id": make_session(uid)}

class Logout(Resource):
    def post(self):
        delete_session(get_session_id(request))
        return {}

class Lockers(Resource):
    def post(self):
        session_id = get_session_id(request)
        request_json = request.get_json(force=True)
        uid = get_uid(session_id)

        while True:
            locker_id = str(uuid.uuid4())
            unlocked_locker_key = "unlocked/" + locker_id + "/"
            locked_locker_key = "locked/" + locker_id + "/"
            if not s3sh.has(unlocked_locker_key) and not s3sh.has(locked_locker_key):
                break

        s3sh.touch(unlocked_locker_key)

        conditions = dict()
        if "content_type" in request_json:
            conditions["content_type"] = request_json["content_type"]
        if "content_length_range" in request_json:
            conditions["content_length_range"] = request_json["content_length_range"]
        if "expires_in_sec" in request_json:
            conditions["expires_in_sec"] = request_json["expires_in_sec"]

        presigned_post = s3sh.presigned_post(unlocked_locker_key, **conditions)

        locker_entity = {
            "id": locker_id,
            "uid": uid,
            "policy": conditions,
            "locked": False,
            "endpoint": presigned_post
        }

        db.put_item(Item = locker_entity)

        return locker_entity

    def get(self):
        pass


class Locker(Resource):
    def get(self, locker_id):
        pass
    def put(self, locker_id):
        pass
    def delete(self, locker_id):
        pass

api.add_resource(Lockers, '/lockers')
api.add_resource(Locker, '/lockers/<locker_id>')
api.add_resource(Login, '/login')
api.add_resource(Logout, '/logout')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

#test = s3.Object("undergrad", "test.jpg")
#url = client.generate_presigned_url('get_object', Params={'Bucket': "undergrad", 'Key': "test.jpg"}, ExpiresIn=10)
#print(url)