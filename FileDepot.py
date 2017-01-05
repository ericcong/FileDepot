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
salt = "OIT-FileDepot"

app = Flask(__name__)
api = Api(app)

sessions = dict()

def make_session(uid):
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "uid": uid,
        "expires": int(time.time()) + session_expire_sec
    }
    return session_id

def make_uid(request):
    try:
        json_data = request.get_json(force=True)
        return hashlib.sha256((json_data["type"] + json_data["cred"]["id"] + salt).encode("utf-8")).hexdigest()
    except:
        abort(400)

def get_uid(session_id):
    if session_id not in sessions:
        abort(401)
    session = sessions[session_id]
    if session["expires"] <= int(time.time()):
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
            locker_key = locker_id + "/"
            if not s3sh.has(locker_key):
                s3sh.touch(locker_key)
                break

        expires_in_sec = 3600
        if "expires_in_sec" in request_json:
            expires_in_sec = request_json["expires_in_sec"]
        expires = int(time.time()) + expires_in_sec

        conditions = {
            "expires_in_sec": expires_in_sec
        }
        if "content_type" in request_json:
            conditions["content_type"] = request_json["content_type"]
        if "content_length_range" in request_json:
            conditions["content_length_range"] = request_json["content_length_range"]

        presigned_post = s3sh.presigned_post(locker_key, **conditions)

        locker_entity = {
            "id": locker_id,
            "uid": uid,
            "expires": expires,
            "policy": conditions,
            "upload_info": presigned_post,
            "content": []
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
