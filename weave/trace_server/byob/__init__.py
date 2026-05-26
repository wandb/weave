"""Per-project (team-level) BYOB storage resolver for mtsaas.

Two storage paths now exist in weave-trace; operators pick one:

1. `WF_FILE_STORAGE_URI` (existing, single bucket per server). Right for
   single-tenant self-hosted clusters - leave `WF_BYOB_RESOLVER_ENABLED` off.
2. `WF_BYOB_RESOLVER_ENABLED` (this module, additive). Resolves
   `project_id -> team-owned bucket` via gorilla, with dual-read fallback to
   `WF_FILE_STORAGE_URI` for pre-flip files. Right for mtsaas.

Fails closed when gorilla is unreachable for a project whose last known
status was BYOB or unknown (spec §4.3).
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
