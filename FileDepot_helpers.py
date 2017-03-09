import uuid
import decimal

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

def generate_packages(s3sh, locker_key, expires_in_sec, package_requests):
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