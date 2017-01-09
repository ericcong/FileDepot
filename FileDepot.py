import os
import decimal
import json
import time
import uuid
import hashlib
import boto3
from flask import Flask, request
from flask_restful import Resource, Api, abort
from S3sh import S3sh
from boto3.dynamodb.conditions import Key

# <Config>
session_expire_sec = 600
download_link_expires_in_sec = 600
bucket = "undergrad"
key_prefix = "FileDepot/"
table = "FileDepot"
salt = "OIT-FileDepot"
# </Config>

s3sh = S3sh(bucket, key_prefix)
db = boto3.resource("dynamodb").Table(table)
app = Flask(__name__)
api = Api(app)
sessions = dict()

def decimal_default(obj):
    if isinstance(obj, decimal.Decimal):
        return int(obj)
    raise TypeError

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

def get_session_id(request, **kwargs):
    try:
        if "querystring" in kwargs and kwargs["querystring"] is True:
            return request.args["session_id"]
        else:
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
        uid = get_uid(session_id)

        while True:
            locker_id = str(uuid.uuid4())
            locker_key = locker_id + "/"
            if not s3sh.has(locker_key):
                s3sh.touch(locker_key)
                break

        request_json = request.get_json(force=True)
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

        size = 5
        if "size" in request_json:
            size = request_json["size"]

        slots = dict()
        for i in range(0, size):
            slot_id = str(uuid.uuid4())
            slots[slot_id] = s3sh.presigned_post(locker_key + slot_id, **conditions)

        locker_entity = {
            "id": locker_id,
            "uid": uid,
            "expires": expires,
            "size": size,
            "space": size,
            "policy": conditions,
            "slots": slots,
            "files": dict()
        }

        db.put_item(Item = locker_entity)

        return locker_entity

    def get(self, locker_id=None):
        session_id = get_session_id(request, querystring = True)
        uid = get_uid(session_id)

        # GET /lockers
        if not locker_id:
            try:
                lockers = db.query(
                    IndexName='uid-expires-index',
                    KeyConditionExpression=Key('uid').eq(uid) & Key('expires').gte(int(request_json["from"])) & Key("expires").lte(int(request_json["to"]))
                )["Items"]
                return json.loads(json.dumps(lockers, default=decimal_default))
            except:
                abort(400)

        # GET /lockers/:id
        try:
            locker = db.query(
                IndexName='id-uid-index',
                KeyConditionExpression=Key('id').eq(locker_id) & Key('uid').eq(uid)
            )["Items"][0]


            locker = json.loads(json.dumps(locker, default=decimal_default))

            for item in s3sh.ls(locker["id"] + "/"):
                key = item["key"]
                if key not in locker["files"]:
                    locker["files"][key] = dict()
                locker["files"][key]["filename"] = item["filename"]
                locker["files"][key]["size"] = item["size"]
                locker["files"][key]["alive"] = True

                if "download_link" not in locker["files"][key] or locker["files"][key]["download_link_expires"] < int(time.time()):
                    locker["files"][key]["download_link_expires"] = int(time.time()) + download_link_expires_in_sec
                    locker["files"][key]["download_link"] = s3sh.presigned_url(key, expires_in_sec=download_link_expires_in_sec)

            for key in dict(locker["files"]):
                if "alive" not in locker["files"][key]:
                    del locker["files"][key]
            for key in dict(locker["files"]):
                del locker["files"][key]["alive"]

            db.put_item(Item = locker)

            return locker
        except:
            abort(404)

    def delete(self, locker_id):
        session_id = get_session_id(request)
        uid = get_uid(session_id)
        try:
            locker = db.query(
                IndexName='id-uid-index',
                KeyConditionExpression=Key('id').eq(locker_id) & Key('uid').eq(uid)
            )["Items"][0]
            s3sh.rm(locker["id"] + "/")
            db.delete_item(Key={"id": locker["id"]})
        except:
            abort(404)

    def put(self, locker_id):
        session_id = get_session_id(request)
        uid = get_uid(session_id)
        try:
            request_json = request.get_json(force=True)
            extension_in_sec = request_json["extension_in_sec"]
            locker = db.query(
                IndexName='id-uid-index',
                KeyConditionExpression=Key('id').eq(locker_id) & Key('uid').eq(uid)
            )["Items"][0]

            now = int(time.time())
            if ("force" in request_json and request_json["force"] is True) or (locker["expires"] < now):
                conditions = locker["policy"]
                conditions["expires_in_sec"] = extension_in_sec
                locker["upload_info"] = s3sh.presigned_post(locker_id + "/", **conditions)
                locker["policy"] = conditions
                locker["expires"] = now + extension_in_sec
                db.put_item(Item = locker)
            locker = json.loads(json.dumps(locker, default=decimal_default))
            return locker
        except:
            abort(400)

api.add_resource(Lockers, "/lockers", "/lockers/<locker_id>")
api.add_resource(Login, "/login")
api.add_resource(Logout, "/logout")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)