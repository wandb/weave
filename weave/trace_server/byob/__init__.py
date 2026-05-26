"""BYOB (Bring Your Own Bucket) storage resolver.

Routes weave-trace file writes/reads to a team-owned bucket when the team
has BYOB configured in gorilla, falling back to the platform default bucket
otherwise. Gated by `WF_BYOB_RESOLVER_ENABLED`.
"""

from weave.trace_server.byob.client_factory import build_storage_client
from weave.trace_server.byob.gorilla_client import (
    DEFAULT_GORILLA_RESOLVE_TIMEOUT_MS,
    GORILLA_RPC_RETRY_ATTEMPTS,
    GorillaHttpClient,
    GorillaTransportError,
)
from weave.trace_server.byob.models import (
    AmbientCredentials,
    AzureSasCredentials,
    GCSAccessTokenCredentials,
    ResolvedStorageTarget,
    S3TemporaryCredentials,
    StorageCredentials,
    StorageProvider,
    StorageResolutionError,
    StorageResolvePurpose,
    StorageResolveStatus,
)
from weave.trace_server.byob.resolver import (
    BYOB_RESOLVER_CACHE_MAX_ENTRIES,
    BYOB_RESOLVER_TTL_SECONDS,
    CREDENTIAL_EXPIRY_SKEW_SECONDS,
    GorillaResolverTransport,
    StorageResolver,
)

__all__ = [
    "BYOB_RESOLVER_CACHE_MAX_ENTRIES",
    "BYOB_RESOLVER_TTL_SECONDS",
    "CREDENTIAL_EXPIRY_SKEW_SECONDS",
    "DEFAULT_GORILLA_RESOLVE_TIMEOUT_MS",
    "GORILLA_RPC_RETRY_ATTEMPTS",
    "AmbientCredentials",
    "AzureSasCredentials",
    "GCSAccessTokenCredentials",
    "GorillaHttpClient",
    "GorillaResolverTransport",
    "GorillaTransportError",
    "ResolvedStorageTarget",
    "S3TemporaryCredentials",
    "StorageCredentials",
    "StorageProvider",
    "StorageResolutionError",
    "StorageResolvePurpose",
    "StorageResolveStatus",
    "StorageResolver",
    "build_storage_client",
]
