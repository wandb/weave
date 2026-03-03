"""In-memory cache for op name -> op ref URI mappings.

Eliminates redundant ClickHouse reads on the OTel ingest hot path.
At steady state (all ops already created), this cache resolves all op
references without any ClickHouse queries.

Thread-safe via a single lock. Cache entries expire after a configurable
TTL (default 5 minutes). When at capacity, the oldest 10% of entries
are evicted.
"""

import threading
import time

_OP_CACHE_TTL_SECONDS = 86_400  # 24 hours
_OP_CACHE_MAX_SIZE = 50_000  # ~10 MB at ~200 bytes per entry


class OpRefCache:
    """Thread-safe TTL cache mapping (project_id, op_name) -> op_ref_uri."""

    def __init__(
        self,
        ttl_seconds: float = _OP_CACHE_TTL_SECONDS,
        max_size: int = _OP_CACHE_MAX_SIZE,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._lock = threading.Lock()
        # key: (project_id, op_name) -> value: (op_ref_uri, expiry_monotonic)
        self._cache: dict[tuple[str, str], tuple[str, float]] = {}

    def get_many(self, project_id: str, op_names: set[str]) -> dict[str, str]:
        """Look up cached op ref URIs for a set of op names.

        Returns a dict of {op_name: op_ref_uri} for cache hits only.
        """
        now = time.monotonic()
        hits: dict[str, str] = {}
        expired_keys: list[tuple[str, str]] = []

        with self._lock:
            for op_name in op_names:
                key = (project_id, op_name)
                entry = self._cache.get(key)
                if entry is None:
                    continue
                uri, expiry = entry
                if now >= expiry:
                    expired_keys.append(key)
                else:
                    hits[op_name] = uri

            for key in expired_keys:
                del self._cache[key]

        return hits

    def put_many(self, project_id: str, mappings: dict[str, str]) -> None:
        """Cache multiple op_name -> op_ref_uri mappings.

        Args:
            project_id: The project these ops belong to.
            mappings: Dict of {op_name: op_ref_uri} to cache.
        """
        if not mappings:
            return

        expiry = time.monotonic() + self._ttl
        with self._lock:
            for op_name, uri in mappings.items():
                self._cache[project_id, op_name] = (uri, expiry)
            self._maybe_evict()

    def _maybe_evict(self) -> None:
        """Drop the oldest 10% of entries if at capacity. Caller must hold lock."""
        if len(self._cache) <= self._max_size:
            return
        # Sort by expiry (oldest first) and drop 10%
        n_to_drop = max(1, len(self._cache) // 10)
        oldest_keys = sorted(self._cache, key=lambda k: self._cache[k][1])[:n_to_drop]
        for key in oldest_keys:
            del self._cache[key]
