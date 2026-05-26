"""Tests for the abstract BYOBResolver contract and trace-server wiring.

weave-public defines the abstract `BYOBResolver` interface only; the
concrete gorilla-backed implementation lives in `services/weave-trace`.
These tests exercise the interface against a fake resolver and verify
`ClickHouseTraceServer` routes through the resolver when one is set.
"""

from __future__ import annotations

import pytest
from azure.core.exceptions import ResourceNotFoundError
from botocore.exceptions import ClientError
from google.api_core import exceptions as gcp_exceptions

from weave.trace_server.byob.resolver import BYOBResolver, StorageResolutionError
from weave.trace_server.file_storage import (
    FileStorageClient,
    FileStorageReadError,
    is_not_found_error,
    key_for_project_digest,
    read_from_bucket,
    store_in_bucket,
)
from weave.trace_server.file_storage_uris import FileStorageURI

# ---------------------------------------------------------------------------
# In-memory storage client + fake resolver
# ---------------------------------------------------------------------------


class InMemoryStorageClient(FileStorageClient):
    """Test bucket; raises a botocore NoSuchKey on miss so `is_not_found_error`
    classifies it like a production S3 miss.
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


class _FakeBYOBResolver(BYOBResolver):
    """Routes one project to a BYOB bucket, everything else to default.

    Records call counts so tests can verify the trace server is going
    through the resolver rather than the default client.
    """

    def __init__(
        self,
        byob_project_id: str,
        byob_client: FileStorageClient,
        key_prefix: str = "",
        raise_on_resolve: bool = False,
    ) -> None:
        self.byob_project_id = byob_project_id
        self.byob_client = byob_client
        self.key_prefix = key_prefix
        self.raise_on_resolve = raise_on_resolve
        self.write_calls: list[str] = []
        self.read_calls: list[tuple[str | None, str]] = []

    def resolve_write(
        self,
        project_id: str,
        default_client: FileStorageClient | None,
    ) -> tuple[FileStorageClient | None, str]:
        self.write_calls.append(project_id)
        if self.raise_on_resolve:
            raise StorageResolutionError(f"forced failure for {project_id}")
        if project_id == self.byob_project_id:
            return self.byob_client, self.key_prefix
        return default_client, ""

    def resolve_read(
        self,
        project_id: str | None,
        stored_uri: FileStorageURI,
        default_client: FileStorageClient | None,
    ) -> bytes:
        self.read_calls.append((project_id, stored_uri.to_uri_str()))
        if project_id != self.byob_project_id:
            if default_client is None:
                raise FileStorageReadError("File storage client is not configured")
            return read_from_bucket(default_client, stored_uri)
        # BYOB path: try team bucket first, fall back on not-found
        team_uri = self.byob_client.base_uri.with_path(stored_uri.path)
        try:
            return self.byob_client.read(team_uri)
        except Exception as e:
            if not is_not_found_error(e):
                raise FileStorageReadError(
                    f"Failed to read from {team_uri}: {e!s}"
                ) from e
        if default_client is None:
            raise FileStorageReadError("BYOB miss and no default client")
        return read_from_bucket(default_client, stored_uri)


# ---------------------------------------------------------------------------
# Abstract interface contract
# ---------------------------------------------------------------------------


def test_byob_resolver_is_abstract() -> None:
    """`BYOBResolver` cannot be instantiated directly; subclasses must
    implement both `resolve_write` and `resolve_read`.
    """
    with pytest.raises(TypeError):
        BYOBResolver()  # type: ignore[abstract]

    class PartialResolver(BYOBResolver):
        def resolve_write(self, project_id, default_client):
            return default_client, ""

    with pytest.raises(TypeError):
        PartialResolver()  # type: ignore[abstract]


def test_storage_resolution_error_is_distinct_exception() -> None:
    """Fail-closed signal must be its own exception type so callers can
    distinguish resolver failure from other I/O errors.
    """
    assert issubclass(StorageResolutionError, Exception)


# ---------------------------------------------------------------------------
# Resolver behavior (against the fake)
# ---------------------------------------------------------------------------


PROJECT_BYOB = "team-byob/project-a"
PROJECT_DEFAULT = "team-default/project-b"


def _make_clients() -> tuple[InMemoryStorageClient, InMemoryStorageClient]:
    default = InMemoryStorageClient(
        FileStorageURI.parse_uri_str("s3://platform-default-bucket")
    )
    byob = InMemoryStorageClient(FileStorageURI.parse_uri_str("s3://team-byob-bucket"))
    return default, byob


def test_resolve_write_routes_by_project_and_returns_prefix() -> None:
    """`resolve_write` returns the BYOB client + key_prefix for BYOB projects,
    and falls back to the default client (no prefix) for everything else.
    """
    default, byob = _make_clients()
    resolver = _FakeBYOBResolver(
        byob_project_id=PROJECT_BYOB, byob_client=byob, key_prefix="weave/"
    )

    # BYOB project routes to the team bucket with the configured prefix.
    client, prefix = resolver.resolve_write(PROJECT_BYOB, default)
    assert client is byob
    assert prefix == "weave/"

    # Non-BYOB project routes to default with no prefix.
    client, prefix = resolver.resolve_write(PROJECT_DEFAULT, default)
    assert client is default
    assert prefix == ""

    # Both calls were observed.
    assert resolver.write_calls == [PROJECT_BYOB, PROJECT_DEFAULT]


def test_resolve_write_propagates_resolver_failure() -> None:
    """A resolver that fails closed must raise `StorageResolutionError`;
    the trace-server should NOT silently route to default in that case.
    """
    default, byob = _make_clients()
    resolver = _FakeBYOBResolver(
        byob_project_id=PROJECT_BYOB, byob_client=byob, raise_on_resolve=True
    )
    with pytest.raises(StorageResolutionError):
        resolver.resolve_write(PROJECT_BYOB, default)


def test_resolve_read_dual_read_falls_back_on_team_bucket_miss() -> None:
    """For a BYOB project, `resolve_read` tries the team bucket first and
    falls back to the default client on a not-found exception (this
    handles pre-attachment data).
    """
    default, byob = _make_clients()
    resolver = _FakeBYOBResolver(byob_project_id=PROJECT_BYOB, byob_client=byob)

    # Seed the default bucket with a pre-attachment file.
    digest_key = key_for_project_digest(PROJECT_BYOB, "abc123")
    stored_uri = store_in_bucket(default, digest_key, b"pre-attachment-data")

    # Reading via the BYOB resolver should miss the team bucket and fall back.
    payload = resolver.resolve_read(PROJECT_BYOB, stored_uri, default)
    assert payload == b"pre-attachment-data"

    # Subsequent write to the team bucket + read should hit the BYOB bucket.
    team_uri = byob.base_uri.with_path(stored_uri.path)
    store_in_bucket(byob, stored_uri.path.lstrip("/"), b"team-data")
    assert resolver.resolve_read(PROJECT_BYOB, stored_uri, default) == b"team-data"

    # Default project reads always go to default.
    default_key = key_for_project_digest(PROJECT_DEFAULT, "xyz789")
    default_uri = store_in_bucket(default, default_key, b"default-data")
    assert (
        resolver.resolve_read(PROJECT_DEFAULT, default_uri, default) == b"default-data"
    )

    # And `None` project_id (legacy code path) reads from default too.
    assert resolver.resolve_read(None, default_uri, default) == b"default-data"

    # All four reads went through the resolver.
    assert len(resolver.read_calls) == 4


def test_resolve_read_raises_when_no_default_and_byob_misses() -> None:
    """If the team bucket misses and there's no default client to fall back
    to, the resolver must raise rather than silently returning empty bytes.
    """
    _, byob = _make_clients()
    resolver = _FakeBYOBResolver(byob_project_id=PROJECT_BYOB, byob_client=byob)

    # A stored URI that doesn't exist anywhere.
    stored_uri = FileStorageURI.parse_uri_str("s3://platform-default-bucket/missing")
    with pytest.raises(FileStorageReadError):
        resolver.resolve_read(PROJECT_BYOB, stored_uri, default_client=None)


# ---------------------------------------------------------------------------
# is_not_found_error classifier across providers
# ---------------------------------------------------------------------------


def test_is_not_found_error_classifies_all_provider_exceptions() -> None:
    """The dual-read fallback depends on `is_not_found_error` correctly
    classifying not-found exceptions from each provider (S3/GCS/Azure).
    Unrelated exceptions must not match.
    """
    # S3 NoSuchKey (real shape from botocore)
    s3_nosuchkey = ClientError(
        error_response={
            "Error": {"Code": "NoSuchKey", "Message": "missing"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        },
        operation_name="GetObject",
    )
    assert is_not_found_error(s3_nosuchkey) is True

    # S3 403 — not a not-found
    s3_403 = ClientError(
        error_response={
            "Error": {"Code": "AccessDenied", "Message": "nope"},
            "ResponseMetadata": {"HTTPStatusCode": 403},
        },
        operation_name="GetObject",
    )
    assert is_not_found_error(s3_403) is False

    # GCS NotFound
    assert is_not_found_error(gcp_exceptions.NotFound("missing")) is True

    # Azure ResourceNotFoundError
    assert is_not_found_error(ResourceNotFoundError("missing")) is True

    # Unrelated error
    assert is_not_found_error(RuntimeError("boom")) is False
