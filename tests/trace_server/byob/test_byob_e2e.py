"""End-to-end test for the BYOB MVP.

Drives the full resolver -> client-factory -> bucket-roundtrip flow with an
in-memory `FileStorageClient` and a fake gorilla transport. Covers the cases
called out by the spec:

- BYOB project: write + read roundtrip lands in the team bucket.
- Default project: write + read roundtrip lands in the platform bucket.
- Cache hit: second resolve does not re-call gorilla.
- TTL expiry: third resolve re-calls gorilla.
- Fail-closed (4.3): missing+unreachable -> StorageResolutionError.
- Fail-closed (4.3): expired+last-byob+unreachable -> StorageResolutionError.
- Fail-closed (4.3): expired+last-default+unreachable -> reuse stale default.
- Cache cap: raises StorageResolutionError loudly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import SecretStr

from weave.trace_server.byob import (
    AmbientCredentials,
    GorillaResolverTransport,
    ResolvedStorageTarget,
    S3TemporaryCredentials,
    StorageProvider,
    StorageResolutionError,
    StorageResolvePurpose,
    StorageResolver,
    StorageResolveStatus,
    build_storage_client,
)
from weave.trace_server.file_storage import (
    FileStorageClient,
    key_for_project_digest,
    read_from_bucket,
    store_in_bucket,
)
from weave.trace_server.file_storage_uris import FileStorageURI

PROJECT_BYOB = "team-byob/project-a"
PROJECT_DEFAULT = "team-default/project-b"


class InMemoryStorageClient(FileStorageClient):
    """Bucket-shaped dict for tests; verifies object lands at the right URI."""

    def __init__(self, base_uri: FileStorageURI) -> None:
        super().__init__(base_uri)
        self.objects: dict[str, bytes] = {}

    def store(self, uri: FileStorageURI, data: bytes) -> None:
        assert uri.to_uri_str().startswith(self.base_uri.to_uri_str())
        self.objects[uri.to_uri_str()] = data

    def read(self, uri: FileStorageURI) -> bytes:
        assert uri.to_uri_str().startswith(self.base_uri.to_uri_str())
        return self.objects[uri.to_uri_str()]


class FakeGorillaTransport(GorillaResolverTransport):
    """Records calls and returns canned `ResolvedStorageTarget`s."""

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
            raise KeyError(f"no canned target for {project_id}")
        return target


def make_byob_target(
    bucket_uri: str = "s3://team-byob-bucket",
    expires_in_s: int | None = 900,
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
        key_prefix="",
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
    """Monotonic clock under test control."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def transport() -> FakeGorillaTransport:
    t = FakeGorillaTransport()
    t.targets[PROJECT_BYOB] = make_byob_target()
    t.targets[PROJECT_DEFAULT] = make_default_target()
    return t


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def resolver(transport: FakeGorillaTransport, clock: FakeClock) -> StorageResolver:
    return StorageResolver(
        transport=transport, ttl_seconds=300, max_entries=2, clock=clock
    )


def route_client(
    resolver: StorageResolver,
    default_client: InMemoryStorageClient,
    byob_clients: dict[str, InMemoryStorageClient],
    project_id: str,
    purpose: StorageResolvePurpose,
) -> FileStorageClient:
    """Mirrors `ClickHouseTraceServer._resolve_client_for_project`.

    Routes between the default platform client and a BYOB client built from
    the resolver target. The test sets up `byob_clients` keyed by bucket_uri
    so we can substitute our `InMemoryStorageClient` instead of the real S3
    client built by `build_storage_client`.
    """
    target = resolver.resolve(project_id, purpose)
    if target.status == StorageResolveStatus.BYOB:
        client = byob_clients.get(target.bucket_uri)
        if client is None:
            # Exercise the real factory at least once for type-shape verification.
            return build_storage_client(target)
        return client
    if target.status == StorageResolveStatus.DEFAULT:
        return default_client
    raise AssertionError(f"unhandled status {target.status!r}")


def test_byob_write_then_read_lands_in_team_bucket(
    resolver: StorageResolver, transport: FakeGorillaTransport
) -> None:
    default_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://platform-default-bucket")
    )
    team_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://team-byob-bucket")
    )
    byob_clients = {"s3://team-byob-bucket": team_client}

    digest = "deadbeef"
    content = b"trace payload"

    write_client = route_client(
        resolver, default_client, byob_clients, PROJECT_BYOB, StorageResolvePurpose.WRITE
    )
    stored_uri = store_in_bucket(
        write_client, key_for_project_digest(PROJECT_BYOB, digest), content
    )

    assert stored_uri.to_uri_str().startswith("s3://team-byob-bucket/")
    assert team_client.objects[stored_uri.to_uri_str()] == content
    assert default_client.objects == {}

    read_client = route_client(
        resolver, default_client, byob_clients, PROJECT_BYOB, StorageResolvePurpose.READ
    )
    assert read_from_bucket(read_client, stored_uri) == content
    # Single resolve call should have served both write and read.
    assert transport.calls == [PROJECT_BYOB]


def test_default_project_uses_platform_bucket(
    resolver: StorageResolver, transport: FakeGorillaTransport
) -> None:
    default_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://platform-default-bucket")
    )
    team_client = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://team-byob-bucket")
    )
    byob_clients = {"s3://team-byob-bucket": team_client}

    write_client = route_client(
        resolver,
        default_client,
        byob_clients,
        PROJECT_DEFAULT,
        StorageResolvePurpose.WRITE,
    )
    stored_uri = store_in_bucket(
        write_client,
        key_for_project_digest(PROJECT_DEFAULT, "abc"),
        b"hello",
    )
    assert stored_uri.to_uri_str().startswith("s3://platform-default-bucket/")
    assert default_client.objects[stored_uri.to_uri_str()] == b"hello"
    assert team_client.objects == {}


def test_cache_hit_skips_transport(
    resolver: StorageResolver, transport: FakeGorillaTransport, clock: FakeClock
) -> None:
    resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.READ)
    clock.advance(60)
    resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    assert transport.calls == [PROJECT_BYOB]


def test_ttl_expiry_refetches(
    resolver: StorageResolver, transport: FakeGorillaTransport, clock: FakeClock
) -> None:
    resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    clock.advance(301)
    resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    assert transport.calls == [PROJECT_BYOB, PROJECT_BYOB]


def test_credential_expiry_caps_ttl(transport: FakeGorillaTransport) -> None:
    # credentials expire in 100s; ttl is 300s. Cache must expire at ~40s
    # (100s - 60s skew).
    transport.targets[PROJECT_BYOB] = make_byob_target(expires_in_s=100)
    clock = FakeClock()
    r = StorageResolver(
        transport=transport, ttl_seconds=300, max_entries=10, clock=clock
    )
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    clock.advance(45)
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    assert transport.calls == [PROJECT_BYOB, PROJECT_BYOB]


def test_fail_closed_no_last_status(transport: FakeGorillaTransport) -> None:
    transport.error = TimeoutError("gorilla unreachable")
    r = StorageResolver(transport=transport, max_entries=10)
    with pytest.raises(StorageResolutionError, match="no last-known status"):
        r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)


def test_fail_closed_last_byob(
    resolver: StorageResolver, transport: FakeGorillaTransport, clock: FakeClock
) -> None:
    resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    clock.advance(400)
    transport.error = TimeoutError("gorilla unreachable")
    with pytest.raises(StorageResolutionError, match="BYOB project"):
        resolver.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)


def test_fail_closed_last_default_reuses_stale(
    resolver: StorageResolver, transport: FakeGorillaTransport, clock: FakeClock
) -> None:
    first = resolver.resolve(PROJECT_DEFAULT, StorageResolvePurpose.WRITE)
    clock.advance(400)
    transport.error = TimeoutError("gorilla unreachable")
    second = resolver.resolve(PROJECT_DEFAULT, StorageResolvePurpose.WRITE)
    assert second is first
    assert second.status == StorageResolveStatus.DEFAULT


def test_cache_cap_raises(transport: FakeGorillaTransport) -> None:
    # max_entries=2, fixture already has BYOB+DEFAULT canned. Add a third
    # project to trigger the cap.
    transport.targets["t3/p3"] = make_byob_target()
    r = StorageResolver(transport=transport, ttl_seconds=300, max_entries=2)
    r.resolve(PROJECT_BYOB, StorageResolvePurpose.WRITE)
    r.resolve(PROJECT_DEFAULT, StorageResolvePurpose.WRITE)
    with pytest.raises(StorageResolutionError, match="max entries"):
        r.resolve("t3/p3", StorageResolvePurpose.WRITE)


def test_build_storage_client_constructs_s3() -> None:
    target = make_byob_target()
    client = build_storage_client(target)
    # Verify the right URI was bound; do not exercise the boto client itself.
    assert client.base_uri.to_uri_str() == "s3://team-byob-bucket"
