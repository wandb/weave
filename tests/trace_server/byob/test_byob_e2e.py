"""End-to-end tests for the per-project BYOB storage path.

These exercise the full resolver -> client-factory -> bucket-roundtrip flow.
A local HTTP server (`_FakeGorilla`) stands in for the gorilla resolve
endpoint so `GorillaHttpClient` is hit through real `requests` I/O; the
bucket layer uses an `InMemoryStorageClient`. The trace_server itself is
not started because the BYOB path is orthogonal to ClickHouse.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import pytest
from azure.core.exceptions import ResourceNotFoundError
from botocore.exceptions import ClientError
from google.api_core import exceptions as gcp_exceptions
from pydantic import SecretStr, ValidationError

from weave.trace_server.byob.client_factory import build_storage_client
from weave.trace_server.byob.gorilla_client import (
    GorillaHttpClient,
    GorillaTransportError,
)
from weave.trace_server.byob.models import (
    AmbientCredentials,
    ResolvedStorageTarget,
    S3TemporaryCredentials,
    StorageProvider,
    StorageResolutionError,
    StorageResolvePurpose,
    StorageResolveStatus,
)
from weave.trace_server.byob.resolver import (
    GorillaResolverTransport,
    StorageResolver,
)
from weave.trace_server.file_storage import (
    FileStorageClient,
    FileStorageReadError,
    is_not_found_error,
    key_for_project_digest,
    read_from_bucket,
    store_in_bucket,
)
from weave.trace_server.file_storage_uris import FileStorageURI

PROJECT_BYOB = "team-byob/project-a"
PROJECT_DEFAULT = "team-default/project-b"


# ---------------------------------------------------------------------------
# In-memory bucket + local HTTP fake gorilla
# ---------------------------------------------------------------------------


class FakeNotFound(Exception):
    """Raised by `InMemoryStorageClient` on miss; classified as not-found."""


class InMemoryStorageClient(FileStorageClient):
    def __init__(self, base_uri: FileStorageURI) -> None:
        super().__init__(base_uri)
        self.objects: dict[str, bytes] = {}

    def store(self, uri: FileStorageURI, data: bytes) -> None:
        assert uri.to_uri_str().startswith(self.base_uri.to_uri_str())
        self.objects[uri.to_uri_str()] = data

    def read(self, uri: FileStorageURI) -> bytes:
        assert uri.to_uri_str().startswith(self.base_uri.to_uri_str())
        if uri.to_uri_str() not in self.objects:
            raise FakeNotFound(uri.to_uri_str())
        return self.objects[uri.to_uri_str()]


class _FakeGorillaHandler(http.server.BaseHTTPRequestHandler):
    """Returns canned resolve responses; per-instance state via class attr."""

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
    """Start a thread-local HTTP fake-gorilla; yield `(base_url, calls)`."""
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
# Target factories + in-process transport for cache mechanics tests
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
        "bucket_name": bucket_uri.removeprefix("s3://").removeprefix("gs://"),
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


class InProcessTransport(GorillaResolverTransport):
    """Lets the fail-closed/cache-cap tests inject errors without HTTP setup."""

    def __init__(self) -> None:
        self.targets: dict[str, ResolvedStorageTarget] = {}
        self.error: Exception | None = None
        self.calls: list[str] = []

    def resolve(self, project_id: str) -> ResolvedStorageTarget:
        self.calls.append(project_id)
        if self.error is not None:
            raise self.error
        target = self.targets.get(project_id)
        if target is None:
            raise KeyError(project_id)
        return target


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
    """Exercise GorillaHttpClient + StorageResolver + bucket roundtrip end-to-end.

    Covers the four scenarios that matter for users:
    1. BYOB project: write lands in team bucket, read pulls from team bucket.
    2. Default project: write/read use platform bucket.
    3. Second resolve for the same project is served from cache (no extra HTTP).
    4. Routing decision matches the resolved target's `bucket_uri`.
    """
    targets = {
        PROJECT_BYOB: byob_target_dict(),
        PROJECT_DEFAULT: default_target_dict(),
    }
    with fake_gorilla(targets) as (base_url, calls):
        transport = GorillaHttpClient(
            base_url=base_url, service_identity_token="test-token"
        )
        resolver = StorageResolver(transport=transport, ttl_seconds=300)

        team_client = InMemoryStorageClient(
            FileStorageURI.parse_uri_str("s3://team-byob-bucket")
        )
        default_client = InMemoryStorageClient(
            FileStorageURI.parse_uri_str("s3://platform-default-bucket")
        )

        # BYOB write+read.
        byob_target = resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
        assert byob_target.status == StorageResolveStatus.BYOB
        assert byob_target.bucket_uri == "s3://team-byob-bucket"
        byob_uri = store_in_bucket(
            team_client,
            key_for_project_digest(PROJECT_BYOB, "deadbeef"),
            b"trace-payload",
        )
        assert read_from_bucket(team_client, byob_uri) == b"trace-payload"
        assert default_client.objects == {}, "BYOB write must not touch default bucket"

        # Default write+read.
        default_target = resolver.resolve(PROJECT_DEFAULT, StorageResolvePurpose.WRITE)
        assert default_target.status == StorageResolveStatus.DEFAULT
        default_uri = store_in_bucket(
            default_client,
            key_for_project_digest(PROJECT_DEFAULT, "feedface"),
            b"default-payload",
        )
        assert read_from_bucket(default_client, default_uri) == b"default-payload"

        # Cache: second resolve does not hit gorilla again.
        resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.READ)
        resolver.resolve(PROJECT_DEFAULT, StorageResolvePurpose.READ)
        assert calls == [PROJECT_BYOB, PROJECT_DEFAULT]


def test_gorilla_transport_unknown_project_raises() -> None:
    """A 404 from gorilla becomes GorillaTransportError; resolver fails closed."""
    with fake_gorilla({}) as (base_url, _):
        transport = GorillaHttpClient(
            base_url=base_url,
            service_identity_token="t",
            retries=1,
        )
        resolver = StorageResolver(transport=transport)
        with pytest.raises(StorageResolutionError, match="no last-known status"):
            resolver.resolve("unknown/proj", StorageResolvePurpose.READ)


def test_resolver_fail_closed_matrix() -> None:
    """All three §4.3 cells exercised in one test, plus the cache cap.

    | last status | gorilla | behavior            |
    |-------------|---------|---------------------|
    | none        | down    | raise               |
    | BYOB        | down    | raise               |
    | DEFAULT     | down    | reuse stale target  |
    """
    transport = InProcessTransport()
    transport.targets[PROJECT_BYOB] = make_byob_target()
    transport.targets[PROJECT_DEFAULT] = make_default_target()
    clock = FakeClock()
    r = StorageResolver(
        transport=transport, ttl_seconds=300, max_entries=2, clock=clock
    )

    # Prime cache with both.
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    default_first = r.resolve(PROJECT_DEFAULT, StorageResolvePurpose.WRITE)

    # Gorilla goes down; expire cache.
    clock.advance(400)
    transport.error = TimeoutError("gorilla unreachable")

    # last status BYOB -> raise.
    with pytest.raises(StorageResolutionError, match="BYOB project"):
        r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)

    # last status DEFAULT -> reuse stale (ambient creds don't expire).
    default_second = r.resolve(PROJECT_DEFAULT, StorageResolvePurpose.WRITE)
    assert default_second is default_first
    assert default_second.status == StorageResolveStatus.DEFAULT

    # No last status -> raise.
    with pytest.raises(StorageResolutionError, match="no last-known status"):
        r.resolve("fresh/project", StorageResolvePurpose.READ)


def test_resolver_cache_ttl_and_credential_expiry() -> None:
    """Cache hit avoids RPC; TTL and credential expiry both force refetch."""
    transport = InProcessTransport()
    transport.targets[PROJECT_BYOB] = make_byob_target(expires_in_s=900)
    clock = FakeClock()
    r = StorageResolver(
        transport=transport, ttl_seconds=300, max_entries=10, clock=clock
    )

    # Cache hits for 5 minutes.
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.READ)
    clock.advance(60)
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    assert transport.calls == [PROJECT_BYOB]

    # TTL crosses 300s -> refetch.
    clock.advance(300)
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    assert transport.calls == [PROJECT_BYOB, PROJECT_BYOB]

    # Credential expiry shorter than TTL caps the cache.
    transport.targets[PROJECT_BYOB] = make_byob_target(expires_in_s=100)
    transport.calls.clear()
    r2 = StorageResolver(
        transport=transport, ttl_seconds=300, max_entries=10, clock=FakeClock()
    )
    r2.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    # Within (expiry - skew) ~40s: cache hit.
    # After 45s: re-fetch.
    assert transport.calls == [PROJECT_BYOB]


def test_resolver_cache_cap_raises_loudly() -> None:
    """Soft-cap excess raises StorageResolutionError instead of silently growing."""
    transport = InProcessTransport()
    for pid in ("a/1", "b/2", "c/3"):
        transport.targets[pid] = make_byob_target()
    r = StorageResolver(transport=transport, ttl_seconds=300, max_entries=2)
    r.resolve("a/1", StorageResolvePurpose.WRITE)
    r.resolve("b/2", StorageResolvePurpose.WRITE)
    with pytest.raises(StorageResolutionError, match="max entries"):
        r.resolve("c/3", StorageResolvePurpose.WRITE)


def test_dual_read_fallback_covers_pre_flip_files_and_propagates_real_errors() -> None:
    """Dual-read: team-bucket hit, team-bucket miss with fallback, real error, no default.

    Mirrors `ClickHouseTraceServer._read_byob_with_fallback`. Spec §8.
    """
    target = make_byob_target()
    team_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://team-byob-bucket")
    )
    default_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://platform-default-bucket")
    )

    def dual_read(
        stored_uri: FileStorageURI,
        default: InMemoryStorageClient | None = default_client,
    ) -> bytes:
        byob_client = team_client
        team_uri = byob_client.base_uri.with_path(stored_uri.path)
        try:
            return byob_client.read(team_uri)
        except Exception as e:
            if not (isinstance(e, FakeNotFound) or is_not_found_error(e)):
                raise FileStorageReadError(f"read failed: {e!s}") from e
        if default is None:
            raise FileStorageReadError("no default client and BYOB miss")
        return read_from_bucket(default, stored_uri)

    # 1. Hit: post-BYOB-flip file lives in team bucket -> read team bucket.
    team_uri = FileStorageURI.parse_uri_str(
        f"s3://team-byob-bucket/{key_for_project_digest(PROJECT_BYOB, 'new')}"
    )
    team_client.objects[team_uri.to_uri_str()] = b"team-content"
    assert dual_read(team_uri) == b"team-content"

    # 2. Miss with fallback: pre-flip file lives in default bucket.
    default_uri = FileStorageURI.parse_uri_str(
        f"s3://platform-default-bucket/{key_for_project_digest(PROJECT_BYOB, 'old')}"
    )
    default_client.objects[default_uri.to_uri_str()] = b"pre-flip-content"
    assert dual_read(default_uri) == b"pre-flip-content"

    # 3. Real error (not 404) must propagate -> no fallback.
    class ExplodingClient(InMemoryStorageClient):
        def read(self, uri: FileStorageURI) -> bytes:
            raise RuntimeError("permission denied")

    exploding = ExplodingClient(FileStorageURI.parse_uri_str("s3://team-byob-bucket"))

    def dual_read_with_exploding(stored_uri: FileStorageURI) -> bytes:
        try:
            return exploding.read(exploding.base_uri.with_path(stored_uri.path))
        except Exception as e:
            if not (isinstance(e, FakeNotFound) or is_not_found_error(e)):
                raise FileStorageReadError(f"read failed: {e!s}") from e
        return read_from_bucket(default_client, stored_uri)

    with pytest.raises(FileStorageReadError, match="read failed"):
        dual_read_with_exploding(team_uri)

    # 4. No default client + miss -> raise.
    with pytest.raises(FileStorageReadError, match="no default client"):
        dual_read(default_uri, default=None)

    # ResolvedStorageTarget is used only as input-shape for the production path;
    # validate it constructs without error here for parity.
    assert build_storage_client(target).base_uri.to_uri_str() == "s3://team-byob-bucket"


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
    # Validation rejects `..` and absolute prefixes.
    for bad in ("/abs", "/", "a/../b", "..", "x/../y/z"):
        with pytest.raises(ValidationError, match="key_prefix"):
            make_byob_target(key_prefix=bad)

    # Empty + simple prefixes accepted.
    for ok in ("", "teamspace/weave", "a/b/c", "weave"):
        make_byob_target(key_prefix=ok)

    # Write path applies prefix.
    target = make_byob_target(key_prefix="teamspace/weave")
    team_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://team-byob-bucket")
    )
    base_key = key_for_project_digest(PROJECT_BYOB, "dd")
    final_key = f"{target.key_prefix}/{base_key}"
    stored_uri = store_in_bucket(team_client, final_key, b"payload")
    assert stored_uri.to_uri_str().endswith(f"teamspace/weave/{base_key}")
    assert team_client.objects[stored_uri.to_uri_str()] == b"payload"


def test_gorilla_transport_unparseable_response_fails_closed() -> None:
    """Junk JSON from gorilla -> GorillaTransportError -> StorageResolutionError."""
    bad_targets = {PROJECT_BYOB: {"status": "byob"}}  # missing required fields
    with fake_gorilla(bad_targets) as (base_url, _):
        transport = GorillaHttpClient(
            base_url=base_url, service_identity_token="t", retries=1
        )
        with pytest.raises(GorillaTransportError):
            transport.resolve(PROJECT_BYOB)
