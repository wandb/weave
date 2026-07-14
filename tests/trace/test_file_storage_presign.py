"""Functional tests for FileStorageClient.presign_read (self-signed download).

Uses moto's in-process S3 so a presigned GET is fetched over real HTTP with no
ClickHouse or AWS credentials, mirroring the customer download path. IAM-policy
negative controls (a leaked GET presign cannot write, cannot read outside
`exports/*`) are enforced by the bucket identity and were proven against MinIO
in the local de-risk harness; they are not re-exercised here (moto does not
enforce bucket policies).
"""

import boto3
import pytest
import requests
from moto import mock_aws

from weave.trace_server import file_storage
from weave.trace_server.file_storage_uris import S3FileStorageURI

BUCKET = "weave-exports"


def _creds() -> dict:
    return {
        "access_key_id": "test-key",
        "secret_access_key": "test-secret",
        "session_token": None,
        "region": "us-east-1",
        "kms_key": None,
    }


@mock_aws
def test_s3_presign_read_round_trips_one_object_and_honors_ttl():
    base = S3FileStorageURI.parse_uri_str(f"s3://{BUCKET}")
    client = file_storage.S3StorageClient(base, _creds())
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)

    calls = S3FileStorageURI.parse_uri_str(
        f"s3://{BUCKET}/exports/p/j/calls/data.parquet"
    )
    objects = S3FileStorageURI.parse_uri_str(
        f"s3://{BUCKET}/exports/p/j/objects/data.parquet"
    )
    client.store(calls, b"PAR1-calls")
    client.store(objects, b"PAR1-objects")

    url = client.presign_read(calls, ttl=3600)
    resp = requests.get(url, timeout=5)
    assert resp.status_code == 200
    assert resp.content == b"PAR1-calls"

    # The presign is bound to exactly one key: signing another object yields a
    # different URL that returns only that object's bytes (no cross-object read).
    other_url = client.presign_read(objects, ttl=3600)
    assert other_url != url
    assert requests.get(other_url, timeout=5).content == b"PAR1-objects"

    # ttl is threaded into the signature: a different lifetime is a different URL.
    assert client.presign_read(calls, ttl=60) != url


@mock_aws
def test_s3_presign_read_rejects_out_of_prefix_object():
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
    scoped = file_storage.S3StorageClient(
        S3FileStorageURI.parse_uri_str(f"s3://{BUCKET}/exports"), _creds()
    )
    with pytest.raises(AssertionError):
        scoped.presign_read(
            S3FileStorageURI.parse_uri_str(f"s3://{BUCKET}/secret.txt"), ttl=3600
        )
