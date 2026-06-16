"""Shared fixtures for trace tests."""

from __future__ import annotations

import base64
import os
import threading
import time
from dataclasses import dataclass, field
from unittest import mock

import pytest
from google.api_core import exceptions as gcp_exceptions
from google.auth.credentials import AnonymousCredentials

from tests.trace.test_utils import FailingSaveType, failing_load, failing_save
from weave.trace.serialization import serializer

# Pinned to the project id of the standard `client` fixture (shawn/test-project).
TEST_BUCKET = "test-bucket"
_TEST_PROJECT_ID_B64 = base64.b64encode(b"shawn/test-project").decode()


@pytest.fixture
def failing_serializer():
    """Register a serializer that always fails, and clean up after the test."""
    serializer.register_serializer(FailingSaveType, failing_save, failing_load)
    yield FailingSaveType
    serializer.SERIALIZERS[:] = [
        s for s in serializer.SERIALIZERS if s.target_class is not FailingSaveType
    ]


# ---------------------------------------------------------------------------
# GCS bucket-storage mocking
#
# Lifted from tests/trace/test_server_file_storage.py so other tests in
# tests/trace/ can drive the bucket write path without copy-pasting fixture
# code. The mock patches at the SDK boundary (`google.cloud.storage.Client`)
# so the real `GCSStorageClient.store` runs end-to-end, exercising URI
# handling, retry decorators, and the `if_generation_match=0` skip path.
# ---------------------------------------------------------------------------

# Safety net so a barrier never deadlocks if fewer uploads arrive than expected.
_BARRIER_TIMEOUT_SECONDS = 30.0


@dataclass
class GCSMockState:
    """Observable + configurable state attached to the gcs fixture.

    Test-side knobs:
      `fail_paths` - inject `PreconditionFailed`-style failures by GCS path.
      `delay`      - sleep inside upload_from_string so parallel tests can
                     assert wall-time savings + concurrent peak.
      `expected_concurrency` - when set, uploads block on a barrier until this
                     many are simultaneously in-flight, making `concurrent_peak`
                     deterministic instead of dependent on scheduler timing.

    Read-back:
      `blob_data`        - the in-memory backing store, keyed by full path.
      `upload_count`     - total successful uploads (skips not counted).
      `concurrent_peak`  - max in-flight uploads observed across threads.
    """

    blob_data: dict[str, bytes] = field(default_factory=dict)
    upload_count: int = 0
    concurrent_peak: int = 0
    fail_paths: set[str] = field(default_factory=set)
    delay: float = 0.0
    expected_concurrency: int | None = None


@pytest.fixture
def mock_gcp_credentials():
    """Mock GCP credentials so the real GCS client construction skips auth."""
    with mock.patch(
        "google.oauth2.service_account.Credentials.from_service_account_info"
    ) as mock_creds:
        mock_creds.return_value = AnonymousCredentials()
        yield


@pytest.fixture
def gcp_storage_env():
    """Enable the bucket write path for the standard test project."""
    with mock.patch.dict(
        os.environ,
        {
            "WF_FILE_STORAGE_GCP_CREDENTIALS_JSON_B64": base64.b64encode(
                b"""{
                "type": "service_account",
                "project_id": "test-project",
                "private_key_id": "test-key-id",
                "private_key": "test-key",
                "client_email": "test@test-project.iam.gserviceaccount.com",
                "client_id": "test-client-id",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test@test-project.iam.gserviceaccount.com"
            }"""
            ).decode(),
            "WF_FILE_STORAGE_URI": f"gs://{TEST_BUCKET}",
            "WF_FILE_STORAGE_PROJECT_ALLOW_LIST": _TEST_PROJECT_ID_B64,
        },
    ):
        yield


@pytest.fixture
def gcs():
    """In-memory google.cloud.storage.Client mock with per-path tracking.

    Each `bucket.blob(path)` call returns a fresh blob mock whose
    upload/download sides effects close over `path`, so distinct uploads in
    the same test are observable (unlike a single shared mock_blob whose
    `.name` is a constant). The dedup contract still holds because uploads
    use `if_generation_match=0` and the backing store is keyed by path.
    """
    state = GCSMockState()
    state_lock = threading.Lock()
    inflight = {"n": 0}
    barrier: dict[str, threading.Barrier | None] = {"b": None}

    def make_blob(path: str):
        blob = mock.MagicMock()
        blob.name = path

        def upload_from_string(data, timeout=None, if_generation_match=None, **kwargs):
            if if_generation_match == 0 and path in state.blob_data:
                raise gcp_exceptions.PreconditionFailed("Object already exists")
            if path in state.fail_paths:
                raise gcp_exceptions.InternalServerError(f"injected failure for {path}")
            with state_lock:
                inflight["n"] += 1
                state.concurrent_peak = max(state.concurrent_peak, inflight["n"])
                if state.expected_concurrency and barrier["b"] is None:
                    barrier["b"] = threading.Barrier(state.expected_concurrency)
            try:
                # Block until expected_concurrency uploads are in-flight so the
                # peak is deterministic; timeout avoids hanging on under-count.
                if barrier["b"] is not None:
                    try:
                        barrier["b"].wait(timeout=_BARRIER_TIMEOUT_SECONDS)
                    except threading.BrokenBarrierError:
                        pass
                if state.delay:
                    time.sleep(state.delay)
                with state_lock:
                    state.blob_data[path] = data
                    state.upload_count += 1
            finally:
                with state_lock:
                    inflight["n"] -= 1

        def download_as_bytes(timeout=None, **kwargs):
            return state.blob_data.get(path, b"")

        blob.upload_from_string.side_effect = upload_from_string
        blob.download_as_bytes.side_effect = download_as_bytes
        return blob

    mock_storage_client = mock.MagicMock()
    mock_bucket = mock.MagicMock()
    mock_storage_client.bucket.return_value = mock_bucket
    mock_bucket.blob.side_effect = make_blob
    # Expose the state object on the mock client so tests can access it
    # without juggling two fixture return values.
    mock_storage_client.state = state

    with mock.patch("google.cloud.storage.Client", return_value=mock_storage_client):
        yield mock_storage_client
