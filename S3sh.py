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