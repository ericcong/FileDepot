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


# Configurations
session_expire_sec = 600
download_link_expires_in_sec = 600
default_locker_expires_in_sec = 3600


# Accept arguments from envionment variable
BUCKET = os.environ["FILEDEPOT_BUCKET_NAME"]
KEY_PREFIX = os.environ["FILEDEPOT_KEY_PREFIX"]
TABLE_NAME = os.environ["FILEDEPOT_TABLE_NAME"]
JWT_ISSUER = os.environ["FILEDEPOT_JWT_ISSUER"]
PORT = os.environ.get("FILEDEPOT_PORT", 5000)
SALT = os.environ.get("FILEDEPOT_SALT", "OIT-FileDepot")


# Initilization of necessary tools
s3sh = S3sh(BUCKET, KEY_PREFIX)
db = boto3.resource("dynamodb").Table(TABLE_NAME)
application = Flask(__name__)
CORS(application)
api = Api(application)
jwt_lib = JWT()


# Retrieve JWKs of our designated issuer from the issuer's "well-known URL".
jwks = dict()
for jwk_dict in requests.get(JWT_ISSUER + "/.well-known/jwks.json").json()["keys"]:
    jwks[(jwk_dict["kid"], jwk_dict["alg"])] = jwk_from_dict(jwk_dict)


# This function is used for extracting UID from the request, with the following steps:
# (1) It extracts the JWT string from the "FileDepot-jwt" field of the request header.
#       If the field doesn't exist, then responds with error 400: Bad request.
# (2) If the JWT is issued by our designated issuer, and is not expired, then 
#       extract the username from "cognito:username".
#       Otherwise responds with error 401: Unauthorized.
# (3) Salt the username, then return its hash as the UID.
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
            and jwt_object["iss"] == JWT_ISSUER):
        return sha256((jwt_object["cognito:username"] + SALT).encode("utf-8")).hexdigest()
    else:
        abort(401)


# Main router.
class Lockers(Resource):

    # POST /lockers - create a locker, and return the JSON representation of the locker.
    # If anything wrong happens, responds with error 400: Bad request.
    #       This can be improved so that different exceptions have different error codes.
    def post(self):
        uid = get_uid(request)
        try:
            # Generate a UUID as locker ID, and create the corresponding object in S3.
            # The while loop is for ensuring no existing locker has the same ID.
            while True:
                locker_id = str(uuid.uuid4())
                locker_key = locker_id + "/"
                if not s3sh.has(locker_key):
                    s3sh.touch(locker_key)
                    break

            # Create the JSON representation of the locker, and store it in DynamoDB.
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

        # GET /lockers - query the current user's lockers with conditions. 
        # If anything wrong happens, responds with error 404: Not found.
        #       This can be improved so that different exceptions have different error codes.
        if not locker_id:
            try:
                # Construct the DynamoDB query according to the request.
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
                    # If there is no query condition, then return all lockers.
                    lockers = db.query(
                            IndexName='uid-index',
                            KeyConditionExpression=Key('uid').eq(uid),
                            ProjectionExpression = "id"
                    )["Items"]

                # Returns the IDs of the satisfying lockers.
                return list(map(lambda a: a["id"], json.loads(json.dumps(lockers, default=decimal_default))))
            except:
                abort(400)

        # GET /lockers/:id - get the information of a specific locker.
        # If anything wrong happens, responds with error 404: Not found.
        #       This can be improved so that different exceptions have different error codes.
        try:
            # Query the locker from DynamoDB.
            # The locker must belong to the current user.
            locker = db.query(
                    IndexName='id-uid-index',
                    KeyConditionExpression=Key('id').eq(locker_id) & Key('uid').eq(uid)
            )["Items"][0]
            locker = json.loads(json.dumps(locker, default=decimal_default))

            # Create a "filename to index" mapping, so that given a file name, we can know where to find its
            #       metadata in locker["packages"].
            package_dict = { locker["packages"][i]["name"] : i for i in range(0, len(locker["packages"])) }

            # Enumerate all existing files in the current locker's S3 virtual directory.
            # Ignore the files without metadata, because this implies that these files are not uploaded
            #       throught FileDepot API.
            # Generate a download URL for each valid file, then construct response with these URLs.
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

    # DELETE /lockers/:id - delete a locker.
    # If anything wrong happens, responds with error 404: Not found.
    #       This can be improved so that different exceptions have different error codes.
    def delete(self, locker_id):
        uid = get_uid(request)
        try:
            # Find the locker
            locker = db.query(
                    IndexName='id-uid-index',
                    KeyConditionExpression=Key('id').eq(locker_id) & Key('uid').eq(uid)
            )["Items"][0]

            # Construct the keys to its contents
            keys = [ locker["id"] + "/" + package["name"] for package in locker["packages"] ]

            # Remove the files and the virtual directory from S3.
            s3sh.rm(*keys)
            s3sh.rm(locker["id"] + "/")

            # Remove its record from DynamoDB.
            db.delete_item(Key={"id": locker["id"]})
        except:
            abort(404)

    # PUT /lockers/:id - update a locker.
    # If anything wrong happens, responds with error 404: Not found.
    #       This can be improved so that different exceptions have different error codes.
    def put(self, locker_id):
        uid = get_uid(request)
        try:
            # Find the locker
            request_json = request.get_json(force=True)
            locker = db.query(
                    IndexName='id-uid-index',
                    KeyConditionExpression=Key('id').eq(locker_id) & Key('uid').eq(uid)
            )["Items"][0]

            now = int(time.time())

            # Create new presigned-POST URLs for the files according to the extension time.
            if "extension_in_sec" in request_json:
                extension_in_sec = request_json["extension_in_sec"]
                locker["expires"] += extension_in_sec
                for i in range(0, len(locker["packages"])):
                    upload_info = s3sh.presigned_post(
                            locker["id"] + "/" + locker["packages"][i]["name"],
                            **generate_conditions(locker["expires"] - now, locker["packages"][i]))
                    locker["packages"][i]["upload_url"] = upload_info["url"]
                    locker["packages"][i]["upload_field"] = upload_info["fields"]

            # Add new packages to the current locker.
            if "packages" in request_json:
                locker["packages"] += generate_packages(s3sh, locker_id + "/", locker["expires"] - now, request_json["packages"])

            # Update the locker's attribtues.
            if "attributes" in request_json:
                locker["attributes"] = request_json["attributes"]

            db.put_item(Item = locker)
            locker = json.loads(json.dumps(locker, default=decimal_default))
            return locker
        except:
            abort(400)

api.add_resource(Lockers, "/lockers", "/lockers/<locker_id>")

if __name__ == '__main__':
    application.run(host="0.0.0.0", port=PORT)