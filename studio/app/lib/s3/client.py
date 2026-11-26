from functools import lru_cache

import boto3
from botocore.client import BaseClient
from botocore.config import Config


@lru_cache
def s3_client(endpoint: str, access_key: str, secret_key: str) -> BaseClient:
    return boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                        region_name="us-east-1", config=Config(s3={"addressing_style": "path"}))
