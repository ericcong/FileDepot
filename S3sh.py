import boto3
import botocore

s3 = boto3.resource("s3")
client = boto3.client("s3")

class S3sh(object):
    def __init__(self, bucket, key_prefix):
        self.bucket = bucket
        self.key_prefix = key_prefix

    def has(self, key):
        result = False
        try:
            s3.Object(self.bucket, self.key_prefix + key).load()
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                result = False
            else:
                raise
        else:
            result = True
        return result

    def touch(self, key):
        return client.put_object(
            Bucket = self.bucket,
            Body = "",
            Key = self.key_prefix + key
        )

    def presigned_post(self, key, **kwargs):
        conditions = list()
        expires_in_sec = 3600
        if "content_length_range" in kwargs:
            conditions.append(["content-length-range", kwargs["content_length_range"][0], kwargs["content_length_range"][1]])
        if "content_type" in kwargs:
            conditions.append(["starts-with", "$Content-Type", kwargs["content_type"]])
        if "expires_in_sec" in kwargs:
            expires_in_sec = kwargs["expires_in_sec"]
        return client.generate_presigned_post(
            Bucket = self.bucket,
            Key = self.key_prefix + key,
            Conditions = conditions,
            ExpiresIn = expires_in_sec
        )

    def presigned_url(self, key, **kwargs):
        expires_in_sec = 300
        if "expires_in_sec" in kwargs:
            expires_in_sec = kwargs["expires_in_sec"]
        return client.generate_presigned_url("get_object", Params={
            "Bucket": self.bucket,
            "Key": self.key_prefix + key,
        }, ExpiresIn=expires_in_sec)

    def ls(self, key):
        bucket = s3.Bucket(self.bucket)
        prefix = self.key_prefix + key
        for item in bucket.objects.filter(Prefix = prefix):
            if item.key == prefix:
                continue
            yield {
                "key": item.key[len(prefix) : ],
                "filename": item.key[len(prefix) : ],
                "size": item.size
            }

    def rm(self, *keys):
        bucket = s3.Bucket(self.bucket)
        objects = list()
        for key in keys:
            objects.append({"Key": self.key_prefix + key})
        if objects:
            return bucket.delete_objects(Delete = {
                "Objects": objects
            })