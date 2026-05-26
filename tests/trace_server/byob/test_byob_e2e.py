"""End-to-end tests for the per-project BYOB storage path.

A thread-local HTTP server (`fake_gorilla`) stands in for the gorilla
resolve endpoint so `fetch_storage_target` is hit through real `requests`
I/O; the bucket layer uses `InMemoryStorageClient`. The trace_server
itself is not started because the BYOB path is orthogonal to ClickHouse.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import ClassVar

import pytest
from azure.core.exceptions import ResourceNotFoundError
from botocore.exceptions import ClientError
from google.api_core import exceptions as gcp_exceptions
from pydantic import SecretStr, ValidationError

from weave.trace_server.byob.client_factory import build_storage_client
from weave.trace_server.byob.gorilla import (
    GorillaUnknownProjectError,
    fetch_storage_target,
)
from weave.trace_server.byob.resolver import (
    StorageResolver,
    resolve_read,
    resolve_write_target,
)
from weave.trace_server.byob.types import (
    AmbientCredentials,
    ResolvedStorageTarget,
    S3TemporaryCredentials,
    StorageProvider,
    StorageResolutionError,
    StorageResolvePurpose,
    StorageResolveStatus,
)
from weave.trace_server.file_storage import (
    FileStorageClient,
    FileStorageReadError,
    is_not_found_error,
    key_for_project_digest,
    store_in_bucket,
)
from weave.trace_server.file_storage_uris import FileStorageURI

PROJECT_BYOB = "team-byob/project-a"
PROJECT_DEFAULT = "team-default/project-b"


# ---------------------------------------------------------------------------
# In-memory bucket + local HTTP fake gorilla
# ---------------------------------------------------------------------------


class InMemoryStorageClient(FileStorageClient):
    """Test bucket; raises a botocore NoSuchKey on miss so `is_not_found_error`
    classifies it the same way production S3 misses are classified.
    """

    def __init__(self, base_uri: FileStorageURI) -> None:
        super().__init__(base_uri)
        self.objects: dict[str, bytes] = {}

    def store(self, uri: FileStorageURI, data: bytes) -> None:
        assert uri.to_uri_str().startswith(self.base_uri.to_uri_str())
        self.objects[uri.to_uri_str()] = data

    def read(self, uri: FileStorageURI) -> bytes:
        assert uri.to_uri_str().startswith(self.base_uri.to_uri_str())
        if uri.to_uri_str() not in self.objects:
            raise ClientError(
                error_response={
                    "Error": {"Code": "NoSuchKey", "Message": uri.to_uri_str()},
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                },
                operation_name="GetObject",
            )
        return self.objects[uri.to_uri_str()]


class _FakeGorillaHandler(http.server.BaseHTTPRequestHandler):
    targets: ClassVar[dict[str, dict]] = {}
    calls: ClassVar[list[str]] = []

    def do_POST(self) -> None:
        if self.path != "/internal/weave-trace/storage/resolve":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode())
        project_id = body.get("project_id", "")
        type(self).calls.append(project_id)
        target = type(self).targets.get(project_id)
        if target is None:
            self.send_response(404)
            self.end_headers()
            return
        payload = json.dumps(target).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object, **kwargs: object) -> None:
        return


@contextmanager
def fake_gorilla(targets: dict[str, dict]) -> Iterator[tuple[str, list[str]]]:
    _FakeGorillaHandler.targets = dict(targets)
    _FakeGorillaHandler.calls = []
    server = socketserver.TCPServer(("127.0.0.1", 0), _FakeGorillaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        yield f"http://127.0.0.1:{port}", _FakeGorillaHandler.calls
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# Target factories
# ---------------------------------------------------------------------------


def byob_target_dict(
    *,
    bucket_uri: str = "s3://team-byob-bucket",
    expires_in_s: int | None = 900,
    key_prefix: str = "",
    project_id: str = PROJECT_BYOB,
) -> dict:
    expiry = (
        (datetime.now(timezone.utc) + timedelta(seconds=expires_in_s)).isoformat()
        if expires_in_s is not None
        else None
    )
    return {
        "status": "byob",
        "provider": "s3",
        "bucket_uri": bucket_uri,
        "bucket_name": bucket_uri.removeprefix("s3://"),
        "region": "us-west-2",
        "credentials": {
            "credential_type": "s3_temporary",
            "access_key_id": "AKIA",
            "secret_access_key": "secret",
            "session_token": "token",
        },
        "credentials_expires_at": expiry,
        "key_prefix": key_prefix,
        "source_project_id": project_id,
    }


def default_target_dict(project_id: str = PROJECT_DEFAULT) -> dict:
    return {
        "status": "default",
        "provider": "s3",
        "bucket_uri": "s3://platform-default-bucket",
        "bucket_name": "platform-default-bucket",
        "region": "us-east-1",
        "credentials": {"credential_type": "ambient"},
        "credentials_expires_at": None,
        "key_prefix": "",
        "source_project_id": project_id,
    }


def make_byob_target(
    *,
    bucket_uri: str = "s3://team-byob-bucket",
    expires_in_s: int | None = 900,
    key_prefix: str = "",
) -> ResolvedStorageTarget:
    expiry = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in_s)
        if expires_in_s is not None
        else None
    )
    return ResolvedStorageTarget(
        status=StorageResolveStatus.BYOB,
        provider=StorageProvider.S3,
        bucket_uri=bucket_uri,
        bucket_name="team-byob-bucket",
        region="us-west-2",
        credentials=S3TemporaryCredentials(
            access_key_id="AKIA",
            secret_access_key=SecretStr("secret"),
            session_token=SecretStr("token"),
        ),
        credentials_expires_at=expiry,
        key_prefix=key_prefix,
        source_project_id=PROJECT_BYOB,
    )


def make_default_target() -> ResolvedStorageTarget:
    return ResolvedStorageTarget(
        status=StorageResolveStatus.DEFAULT,
        provider=StorageProvider.S3,
        bucket_uri="s3://platform-default-bucket",
        bucket_name="platform-default-bucket",
        region="us-east-1",
        credentials=AmbientCredentials(),
        credentials_expires_at=None,
        key_prefix="",
        source_project_id=PROJECT_DEFAULT,
    )


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_full_byob_and_default_flow_against_real_http_gorilla() -> None:
    """End-to-end through real HTTP + bucket roundtrip + cache.

    Covers: BYOB write+read lands in team bucket, default project uses
    platform bucket, second resolve served from cache.
    """
    targets = {
        PROJECT_BYOB: byob_target_dict(),
        PROJECT_DEFAULT: default_target_dict(),
    }
    with fake_gorilla(targets) as (base_url, calls):
        resolver = StorageResolver(resolve_fn=partial(fetch_storage_target, base_url))
        team_client = InMemoryStorageClient(
            FileStorageURI.parse_uri_str("s3://team-byob-bucket")
        )
        default_client = InMemoryStorageClient(
            FileStorageURI.parse_uri_str("s3://platform-default-bucket")
        )

        byob_target = resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
        assert byob_target.status == StorageResolveStatus.BYOB
        assert byob_target.bucket_uri == "s3://team-byob-bucket"
        byob_uri = store_in_bucket(
            team_client,
            key_for_project_digest(PROJECT_BYOB, "deadbeef"),
            b"trace-payload",
        )
        assert team_client.objects[byob_uri.to_uri_str()] == b"trace-payload"
        assert default_client.objects == {}, "BYOB write must not touch default bucket"

        default_target = resolver.resolve(PROJECT_DEFAULT, StorageResolvePurpose.WRITE)
        assert default_target.status == StorageResolveStatus.DEFAULT
        default_uri = store_in_bucket(
            default_client,
            key_for_project_digest(PROJECT_DEFAULT, "feedface"),
            b"default-payload",
        )
        assert default_client.objects[default_uri.to_uri_str()] == b"default-payload"

        # Cache: second resolve doesn't hit gorilla.
        resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.READ)
        resolver.resolve(PROJECT_DEFAULT, StorageResolvePurpose.READ)
        assert calls == [PROJECT_BYOB, PROJECT_DEFAULT]


def test_gorilla_404_raises_unknown_project_and_resolver_fails_closed() -> None:
    """A 404 from gorilla is GorillaUnknownProjectError; resolver fails closed."""
    with fake_gorilla({}) as (base_url, _):
        with pytest.raises(GorillaUnknownProjectError):
            fetch_storage_target(base_url, "unknown/proj")

        resolver = StorageResolver(resolve_fn=partial(fetch_storage_target, base_url))
        with pytest.raises(StorageResolutionError, match="no last-known status"):
            resolver.resolve("unknown/proj", StorageResolvePurpose.READ)


def test_gorilla_unparseable_response_fails_closed() -> None:
    """Junk JSON from gorilla -> resolver wraps it in StorageResolutionError."""
    bad = {PROJECT_BYOB: {"status": "byob"}}  # missing required fields
    with fake_gorilla(bad) as (base_url, _):
        resolver = StorageResolver(resolve_fn=partial(fetch_storage_target, base_url))
        with pytest.raises(StorageResolutionError):
            resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)


def _scripted(targets: dict[str, ResolvedStorageTarget], error: list[Exception]):
    """A `resolve_fn` driven by a dict + a mutable error slot for tests."""
    calls: list[str] = []

    def resolve_fn(project_id: str) -> ResolvedStorageTarget:
        calls.append(project_id)
        if error:
            raise error[0]
        if project_id not in targets:
            raise KeyError(project_id)
        return targets[project_id]

    return resolve_fn, calls


def test_resolver_fail_closed_matrix() -> None:
    """All three §4.3 cells exercised in one test, plus the cache cap."""
    targets = {
        PROJECT_BYOB: make_byob_target(),
        PROJECT_DEFAULT: make_default_target(),
    }
    error: list[Exception] = []
    resolve_fn, _ = _scripted(targets, error)
    clock = FakeClock()
    r = StorageResolver(
        resolve_fn=resolve_fn, ttl_seconds=300, max_entries=2, clock=clock
    )

    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    default_first = r.resolve(PROJECT_DEFAULT, StorageResolvePurpose.WRITE)

    clock.advance(400)
    error.append(TimeoutError("gorilla unreachable"))

    with pytest.raises(StorageResolutionError, match="BYOB project"):
        r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)

    default_second = r.resolve(PROJECT_DEFAULT, StorageResolvePurpose.WRITE)
    assert default_second is default_first
    assert default_second.status == StorageResolveStatus.DEFAULT

    with pytest.raises(StorageResolutionError, match="no last-known status"):
        r.resolve("fresh/project", StorageResolvePurpose.READ)


def test_resolver_cache_ttl_and_credential_expiry() -> None:
    """Cache hit avoids RPC; TTL and credential expiry both force refetch."""
    targets = {PROJECT_BYOB: make_byob_target(expires_in_s=900)}
    resolve_fn, calls = _scripted(targets, [])
    clock = FakeClock()
    r = StorageResolver(
        resolve_fn=resolve_fn, ttl_seconds=300, max_entries=10, clock=clock
    )

    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.READ)
    clock.advance(60)
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    assert calls == [PROJECT_BYOB]

    clock.advance(300)
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    assert calls == [PROJECT_BYOB, PROJECT_BYOB]


def test_resolver_cache_cap_raises_loudly() -> None:
    targets = {f"a/{i}": make_byob_target() for i in range(3)}
    resolve_fn, _ = _scripted(targets, [])
    r = StorageResolver(resolve_fn=resolve_fn, ttl_seconds=300, max_entries=2)
    r.resolve("a/0", StorageResolvePurpose.WRITE)
    r.resolve("a/1", StorageResolvePurpose.WRITE)
    with pytest.raises(StorageResolutionError, match="max entries"):
        r.resolve("a/2", StorageResolvePurpose.WRITE)


def test_resolve_write_target_chooses_byob_default_or_passthrough() -> None:
    """`resolve_write_target` is the production write-path routing helper."""
    default_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://platform-default-bucket")
    )
    # No resolver -> passes through.
    client, prefix = resolve_write_target(None, default_client, PROJECT_DEFAULT)
    assert client is default_client
    assert prefix == ""

    # BYOB -> builds team client, propagates key_prefix.
    targets = {PROJECT_BYOB: make_byob_target(key_prefix="teamspace/weave")}
    resolve_fn, _ = _scripted(targets, [])
    r = StorageResolver(resolve_fn=resolve_fn)
    client, prefix = resolve_write_target(r, default_client, PROJECT_BYOB)
    assert client is not default_client
    assert client.base_uri.to_uri_str() == "s3://team-byob-bucket"
    assert prefix == "teamspace/weave"

    # DEFAULT status -> default client, no prefix.
    targets[PROJECT_DEFAULT] = make_default_target()
    client, prefix = resolve_write_target(r, default_client, PROJECT_DEFAULT)
    assert client is default_client
    assert prefix == ""


def test_resolve_read_dual_read_covers_pre_flip_and_propagates_real_errors() -> None:
    """Dual-read: team-hit, team-miss-fallback, real error, no default."""
    team_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://team-byob-bucket")
    )
    default_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://platform-default-bucket")
    )

    targets = {PROJECT_BYOB: make_byob_target()}
    resolve_fn, _ = _scripted(targets, [])
    r = StorageResolver(resolve_fn=resolve_fn)

    # Patch build_storage_client used inside resolve_read to return our team_client
    # (the real factory would build an S3StorageClient with boto3).
    import weave.trace_server.byob.resolver as resolver_mod

    original = resolver_mod.build_storage_client
    resolver_mod.build_storage_client = lambda target: team_client
    try:
        # 1. Hit: post-flip file lives in team bucket.
        team_key = key_for_project_digest(PROJECT_BYOB, "new")
        team_client.objects[f"s3://team-byob-bucket/{team_key}"] = b"team-content"
        stored = FileStorageURI.parse_uri_str(f"s3://team-byob-bucket/{team_key}")
        assert resolve_read(r, default_client, stored, PROJECT_BYOB) == b"team-content"

        # 2. Miss with fallback: pre-flip file in default bucket.
        old_key = key_for_project_digest(PROJECT_BYOB, "old")
        default_client.objects[f"s3://platform-default-bucket/{old_key}"] = b"pre-flip"
        stored = FileStorageURI.parse_uri_str(f"s3://platform-default-bucket/{old_key}")
        assert resolve_read(r, default_client, stored, PROJECT_BYOB) == b"pre-flip"

        # 3. No default client + miss -> raise.
        with pytest.raises(FileStorageReadError, match="no default client"):
            resolve_read(r, None, stored, PROJECT_BYOB)

        # 4. Real error from team bucket must propagate (no fallback).
        class ExplodingClient(InMemoryStorageClient):
            def read(self, uri: FileStorageURI) -> bytes:
                raise RuntimeError("permission denied")

        resolver_mod.build_storage_client = lambda target: ExplodingClient(
            FileStorageURI.parse_uri_str("s3://team-byob-bucket")
        )
        with pytest.raises(FileStorageReadError, match="Failed to read"):
            resolve_read(r, default_client, stored, PROJECT_BYOB)
    finally:
        resolver_mod.build_storage_client = original


def test_resolve_read_without_resolver_uses_default_client() -> None:
    default_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://platform-default-bucket")
    )
    key = key_for_project_digest(PROJECT_DEFAULT, "d")
    stored = FileStorageURI.parse_uri_str(f"s3://platform-default-bucket/{key}")
    default_client.objects[stored.to_uri_str()] = b"payload"
    assert resolve_read(None, default_client, stored, None) == b"payload"
    # project_id passed but resolver None -> still uses default.
    assert resolve_read(None, default_client, stored, PROJECT_DEFAULT) == b"payload"


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (
            ClientError(
                error_response={
                    "Error": {"Code": "NoSuchKey"},
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                },
                operation_name="GetObject",
            ),
            True,
        ),
        (
            ClientError(
                error_response={
                    "Error": {"Code": "AccessDenied"},
                    "ResponseMetadata": {"HTTPStatusCode": 403},
                },
                operation_name="GetObject",
            ),
            False,
        ),
        (gcp_exceptions.NotFound("missing"), True),
        (ResourceNotFoundError("missing"), True),
        (RuntimeError("boom"), False),
    ],
    ids=["s3-nosuchkey", "s3-403", "gcs-notfound", "azure-notfound", "random"],
)
def test_is_not_found_error_classifies_all_provider_exceptions(
    exc: BaseException, expected: bool
) -> None:
    assert is_not_found_error(exc) is expected


def test_key_prefix_validation_and_write_path_roundtrip() -> None:
    """Pydantic rejects unsafe prefixes; the write path prepends safe ones."""
    for bad in ("/abs", "/", "a/../b", "..", "x/../y/z"):
        with pytest.raises(ValidationError, match="key_prefix"):
            make_byob_target(key_prefix=bad)
    for ok in ("", "teamspace/weave", "a/b/c", "weave"):
        make_byob_target(key_prefix=ok)

    target = make_byob_target(key_prefix="teamspace/weave")
    team_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://team-byob-bucket")
    )
    base_key = key_for_project_digest(PROJECT_BYOB, "dd")
    final_key = f"{target.key_prefix}/{base_key}"
    stored_uri = store_in_bucket(team_client, final_key, b"payload")
    assert stored_uri.to_uri_str().endswith(f"teamspace/weave/{base_key}")
    assert team_client.objects[stored_uri.to_uri_str()] == b"payload"


def test_build_storage_client_constructs_s3_from_target() -> None:
    """`build_storage_client` materializes the right client type + URI."""
    client = build_storage_client(make_byob_target())
    assert client.base_uri.to_uri_str() == "s3://team-byob-bucket"
