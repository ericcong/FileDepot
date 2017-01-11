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
from functools import reduce

# <config: Configurations>
session_expire_sec = 600
download_link_expires_in_sec = 600
default_locker_expires_in_sec = 3600
bucket = "undergrad"
key_prefix = "FileDepot/"
table = "FileDepot"
salt = "OIT-FileDepot"
# </config>

s3sh = S3sh(bucket, key_prefix)
db = boto3.resource("dynamodb").Table(table)
app = Flask(__name__)
api = Api(app)
sessions = dict()

def decimal_default(obj):
    if isinstance(obj, decimal.Decimal):
        return int(obj)
    raise TypeError

def generate_conditions(expires_in_sec, package_request):
    conditions = {"expires_in_sec": expires_in_sec}
    if "type" in package_request and package_request["type"] is not None:
        conditions["content_type"] = package_request["type"]
    if "size_range" in package_request and package_request["size_range"] is not None:
        conditions["content_length_range"] = package_request["size_range"]
    return conditions

def generate_packages(locker_key, expires_in_sec, package_requests):
    packages = list()
    for package_request in package_requests:
        name = package_request.get("name", str(uuid.uuid4()))
        upload_info = s3sh.presigned_post(
                locker_key + name,
                **generate_conditions(expires_in_sec, package_request))
        upload_fields = upload_info["fields"]

        if "type" in package_request:
            upload_fields["Content-Type"] = package_request["type"]

        packages.append({
            "name": name,
            "size": 0,
            "type": package_request.get("type", None),
            "size_range": package_request.get("size_range", None),
            "download_url": None,
            "download_url_expires": None,
            "upload_url": upload_info["url"],
            "upload_fields": upload_fields
        })
    return packages

def make_session(uid):
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "uid": uid,
        "expires": int(time.time()) + session_expire_sec
    }
    return session_id

def make_uid(request):
    try:
        request_json = request.get_json(force=True)
        return hashlib.sha256((request_json["type"] + request_json["cred"]["id"] + salt).encode("utf-8")).hexdigest()
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
        try:
            while True:
                locker_id = str(uuid.uuid4())
                locker_key = locker_id + "/"
                if not s3sh.has(locker_key):
                    s3sh.touch(locker_key)
                    break
            request_json = request.get_json(force=True)
            expires_in_sec = request_json.get("expires_in_sec", default_locker_expires_in_sec)
            locker_entity = {
                "id": locker_id,
                "uid": uid,
                "expires": int(time.time()) + expires_in_sec,
                "notes": request_json.get("notes", None),
                "packages": generate_packages(locker_key, expires_in_sec, request_json["packages"])
            }
            db.put_item(Item = locker_entity)
            return locker_entity
        except:
            abort(400)

    def get(self, locker_id=None):
        session_id = get_session_id(request, querystring = True)
        uid = get_uid(session_id)

        # <list: GET /lockers>
        if not locker_id:
            try:
                filters = list()
                if "min_expires" in request.args:
                    filters.append(Key("expires").gte(int(request.args["min_expires"])))
                if "max_expires" in request.args:
                    filters.append(Key("expires").lte(int(request.args["max_expires"])))
                if filters:
                    lockers = db.query(
                            IndexName='uid-index',
                            KeyConditionExpression=Key('uid').eq(uid),
                            ProjectionExpression = "id",
                            FilterExpression = reduce(lambda a, b: a & b, filters)
                    )["Items"]
                else:
                    lockers = db.query(
                            IndexName='uid-index',
                            KeyConditionExpression=Key('uid').eq(uid),
                            ProjectionExpression = "id"
                    )["Items"]
                return list(map(lambda a: a["id"], json.loads(json.dumps(lockers, default=decimal_default))))
            except:
                abort(400)
        # </list>

        # <show: GET /lockers/:id>
        try:
            locker = db.query(
                    IndexName='id-uid-index',
                    KeyConditionExpression=Key('id').eq(locker_id) & Key('uid').eq(uid)
            )["Items"][0]
            locker = json.loads(json.dumps(locker, default=decimal_default))

            package_dict = { locker["packages"][i]["name"] : i for i in range(0, len(locker["packages"])) }

            for item in s3sh.ls(locker["id"] + "/"):
                fid = item["filename"]
                if fid in package_dict:
                    package = locker["packages"][package_dict[fid]]
                    locker["packages"][package_dict[fid]]["size"] = item["size"]
                    if package["download_url"] is None or package["download_url_expires"] < (int(time.time()) + download_link_expires_in_sec):
                        locker["packages"][package_dict[fid]]["download_url"] = s3sh.presigned_url(item["key"], expires_in_sec=download_link_expires_in_sec)
                        locker["packages"][package_dict[fid]]["download_url_expires"] = int(time.time()) + download_link_expires_in_sec

            db.put_item(Item = locker)
            return locker
        except:
            abort(404)
        # </show>

    def delete(self, locker_id):
        session_id = get_session_id(request)
        uid = get_uid(session_id)
        try:
            locker = db.query(
                    IndexName='id-uid-index',
                    KeyConditionExpression=Key('id').eq(locker_id) & Key('uid').eq(uid)
            )["Items"][0]
            keys = [ locker["id"] + "/" + package["name"] for package in locker["packages"] ]
            s3sh.rm(*keys)
            s3sh.rm(locker["id"] + "/")
            db.delete_item(Key={"id": locker["id"]})
        except:
            abort(404)

    def put(self, locker_id):
        session_id = get_session_id(request)
        uid = get_uid(session_id)
        try:
            request_json = request.get_json(force=True)
            locker = db.query(
                    IndexName='id-uid-index',
                    KeyConditionExpression=Key('id').eq(locker_id) & Key('uid').eq(uid)
            )["Items"][0]

            now = int(time.time())

            if "extension_in_sec" in request_json:
                extension_in_sec = request_json["extension_in_sec"]
                locker["expires"] += extension_in_sec
                for i in range(0, len(locker["packages"])):
                    upload_info = s3sh.presigned_post(
                            locker["id"] + "/" + locker["packages"][i]["name"],
                            **generate_conditions(locker["expires"] - now, locker["packages"][i]))
                    locker["packages"][i]["upload_url"] = upload_info["url"]
                    locker["packages"][i]["upload_field"] = upload_info["fields"]

            if "packages" in request_json:
                locker["packages"] += generate_packages(locker_id + "/", locker["expires"] - now, request_json["packages"])

            if "notes" in request_json:
                locker["notes"] = request_json["notes"]

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