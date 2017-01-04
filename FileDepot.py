import os
import time
import boto3
import botocore
import uuid
import hashlib
from flask import Flask, request
from flask_restful import Resource, Api

# Config
bucket = "undergrad"
key_prefix = "FileDepot/"
session_expire_sec = 600

app = Flask(__name__)
api = Api(app)

s3 = boto3.resource("s3")
client = boto3.client("s3")

sessions = dict()

def make_session(uid):
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "uid": uid,
        "expire_time": int(time.time()) + session_expire_sec
    }
    return session_id

def get_uid(session_id):
    if session_id not in sessions:
        return None
    session = sessions[session_id]
    if session["expire_time"] <= int(time.time()):
        del sessions[session_id]
        return None
    return session["uid"]

def delete_session(session_id):
    del sessions[session_id]

def get_session_id(request):
    return request.get_json(force=True)["session_id"]

def has_key(key):
    result = False
    try:
        s3.Object(bucket, key_prefix + key).load()
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            result = False
        else:
            raise
    else:
        result = True
    return result

def touch(key):
    return client.put_object(
        Bucket = bucket,
        Body = "",
        Key = key_prefix + key
    )

class Login(Resource):
    def post(self):
        json_data = request.get_json(force=True)
        uid = hashlib.sha256((json_data["type"] + json_data["cred"]["id"]).encode("utf-8")).hexdigest()
        for i in ["locked/", "unlocked/"]:
            dir_key = i + uid + "/"
            if not has_key(dir_key):
                touch(dir_key)
        return {"session_id": make_session(uid)}

class Logout(Resource):
    def post(self):
        delete_session(get_session_id(request))
        return {}

class Lockers(Resource):
    def get(self):
        session_id = get_session_id(request)
        return {'uid': get_uid(session_id)}

    def post(self):
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