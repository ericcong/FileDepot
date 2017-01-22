import os
from flask import render_template, request, Flask, redirect
from contextlib import contextmanager
import requests
import json

FileDepot = "http://lowcost-env.rsgwu3uhma.us-east-1.elasticbeanstalk.com/"
login_type = "CAS"
login_id = "demo-python"

application = Flask(__name__)

@contextmanager
def FileDepotSession():
    session_id = requests.post(FileDepot + "login", data=json.dumps({"type": login_type, "cred": {"id": login_id}})).json()["session_id"]
    yield session_id
    requests.post(FileDepot + "logout", data=json.dumps({"session_id": session_id}))

@application.route("/", methods=["GET"])
def list_lockers():
    with FileDepotSession() as session_id:
        locker_ids = requests.get(FileDepot + "lockers", params={"session_id": session_id, "with_attributes": ["sealed"]}).json()
    return render_template("list_lockers.html", locker_ids = locker_ids)

@application.route("/locker/<locker_id>", methods=["GET"])
def show_locker(locker_id):
    with FileDepotSession() as session_id:
        locker = requests.get(FileDepot + "lockers/" + locker_id, params={"session_id": session_id}).json()
    return render_template("show_locker.html", locker = locker)

@application.route("/upload", methods=["GET"])
def upload_form():
    return render_template("upload.html")

@application.route("/preview", methods=["POST"])
def preview():
    files = request.files.to_dict(flat=False)["file"]
    package_request = list()
    file_streams = dict()
    for f in files:
        package_request.append({"name": f.filename, "type": f.mimetype})
        file_streams[f.filename] = f.stream
    with FileDepotSession() as session_id:
        locker = requests.post(FileDepot + "lockers", data=json.dumps({"session_id": session_id, "attributes": "pending", "packages": package_request})).json()
        for p in locker["packages"]:
            requests.post(p["upload_url"], files = {"file": file_streams[p["name"]]}, data = p["upload_fields"])
        locker = requests.get(FileDepot + "lockers/" + locker["id"], params={"session_id": session_id}).json()
    return render_template("preview.html", locker = locker)

@application.route("/submit/<locker_id>", methods=["GET"])
def submit(locker_id):
    with FileDepotSession() as session_id:
        requests.put(FileDepot + "lockers/" + locker_id, data=json.dumps({"session_id": session_id, "attributes": "sealed"}))
    return redirect("/")

@application.route("/delete/<locker_id>", methods=["GET"])
def delete(locker_id):
    with FileDepotSession() as session_id:
        requests.delete(FileDepot + "lockers/" + locker_id, data=json.dumps({"session_id": session_id}))
    return redirect("/")

@application.route("/download/<locker_id>/<package_name>", methods=["GET"])
def download(locker_id, package_name):
    with FileDepotSession() as session_id:
        locker = requests.get(FileDepot + "lockers/" + locker_id, params={"session_id": session_id}).json()
    for p in locker["packages"]:
        if p["name"] == package_name:
            return redirect(p["download_url"])
    abort(404)

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5000)