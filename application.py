import os
import json
import time
import uuid
import boto3
import requests
from hashlib import sha256
from base64 import b64decode
from flask import Flask, request
from flask_restful import Resource, Api, abort
from flask_cors import CORS
from S3sh import S3sh
from boto3.dynamodb.conditions import Key, Attr
from functools import reduce
from jwt import JWT, jwk_from_dict
from FileDepot_helpers import *

# <config: Configurations>
session_expire_sec = 600
download_link_expires_in_sec = 600
default_locker_expires_in_sec = 3600
salt = "OIT-FileDepot"
# </config>

bucket = os.environ["FILEDEPOT_BUCKET"]
key_prefix = os.environ["FILEDEPOT_KEY_PREFIX"]
table_name = os.environ["FILEDEPOT_TABLE_NAME"]
jwt_issuer = os.environ["FILEDEPOT_JWT_ISSUER"]

s3sh = S3sh(bucket, key_prefix)
db = boto3.resource("dynamodb").Table(table_name)
application = Flask(__name__)
CORS(application)
api = Api(application)

jwt_lib = JWT()
jwks = dict()
for jwk_dict in requests.get(jwt_issuer + "/.well-known/jwks.json").json()["keys"]:
    jwks[(jwk_dict["kid"], jwk_dict["alg"])] = jwk_from_dict(jwk_dict)

def get_uid(request):
    try:
        jwt_string = request.headers["FileDepot-jwt"]
        key_info = json.loads(b64decode(jwt_string.split(".")[0] + "="))
        jwk = jwks[(key_info["kid"], key_info["alg"])]
        jwt_object = jwt_lib.decode(jwt_string, jwk)
    except:
        abort(400)
    if (jwt_object 
            and jwt_object["exp"] > time.time()
            and jwt_object["iss"] == jwt_issuer):
        return sha256((jwt_object["cognito:username"] + salt).encode("utf-8")).hexdigest()
    else:
        abort(401)

class Lockers(Resource):
    def post(self):
        uid = get_uid(request)
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
                "attributes": request_json.get("attributes", None),
                "packages": generate_packages(s3sh, locker_key, expires_in_sec, request_json["packages"])
            }
            db.put_item(Item = locker_entity)
            return locker_entity
        except:
            abort(400)

    def get(self, locker_id=None):
        uid = get_uid(request)

        # <list: GET /lockers>
        if not locker_id:
            try:
                filters = list()
                request_args = request.args.to_dict(flat=False)
                if "min_expires" in request_args:
                    for e in request_args["min_expires"]:
                        filters.append(Attr("expires").gte(int(e)))
                if "max_expires" in request_args:
                    for e in request_args["max_expires"]:
                        filters.append(Attr("expires").lte(int(e)))
                if "with_attributes" in request_args:
                    for attr in request_args["with_attributes"]:
                        filters.append(Attr("attributes").contains(attr))
                if "without_attributes" in request_args:
                    for attr in request_args["without_attributes"]:
                        filters.append(~Attr("attributes").contains(attr))
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
        uid = get_uid(request)
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
        uid = get_uid(request)
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
                locker["packages"] += generate_packages(s3sh, locker_id + "/", locker["expires"] - now, request_json["packages"])

            if "attributes" in request_json:
                locker["attributes"] = request_json["attributes"]

            db.put_item(Item = locker)
            locker = json.loads(json.dumps(locker, default=decimal_default))
            return locker
        except:
            abort(400)

api.add_resource(Lockers, "/lockers", "/lockers/<locker_id>")

if __name__ == '__main__':
    application.run(host="0.0.0.0", port=5000)