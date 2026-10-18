"""Adaptador de storage sobre S3 (boto3): atende AWS S3, S3Mock e LocalStack só trocando `S3_ENDPOINT`."""
import boto3
from botocore.exceptions import ClientError


class S3Storage:
    def __init__(self, bucket, endpoint=None, access_key=None, secret_key=None, region="us-east-1"):
        self.bucket = bucket
        self.client = boto3.client(
            "s3", endpoint_url=endpoint, aws_access_key_id=access_key,
            aws_secret_access_key=secret_key, region_name=region,
        )

    def put(self, key, data):
        """Escrita condicional (If-None-Match): nunca sobrescreve; FileExistsError se a chave existe."""
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, IfNoneMatch="*")
        except ClientError as e:
            if e.response["Error"]["Code"] in ("PreconditionFailed", "ConditionalRequestConflict"):
                raise FileExistsError(key) from e
            raise

    def get(self, key):
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise FileNotFoundError(key) from e
            raise
