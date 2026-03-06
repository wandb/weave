from __future__ import annotations

import logging

import diskcache

logger = logging.getLogger(__name__)


class DiskCache:
    """Wrapper around diskcache.Cache to conform to CacheProtocol."""

    def __init__(self, cache_dir: str, size_limit: int = 1_000_000_000):
        """Initialize disk cache.

        Args:
            cache_dir: Directory path for disk cache storage
            size_limit: Maximum size in bytes for disk cache (default 1GB)
        """
        self._cache: diskcache.Cache[str, str | bytes] = diskcache.Cache(
            cache_dir, size_limit=size_limit
        )

    def get(self, key: str) -> str | bytes | None:
        """Get a value by key. Returns None on error."""
        try:
            return self._cache.get(key)
        except Exception as e:
            logger.debug(f"Error reading from disk cache for key '{key}': {e}")
            return None

    def put(self, key: str, value: str | bytes) -> None:
        """Put a key-value pair. Silent on errors."""
        try:
            self._cache.set(key, value)
        except Exception as e:
            logger.debug(f"Error writing to disk cache for key '{key}': {e}")

    def delete(self, key: str) -> None:
        """Delete a key from the cache. Silent on errors."""
        try:
            del self._cache[key]
        except (KeyError, Exception) as e:
            # Silent on both KeyError (key doesn't exist) and other errors
            logger.debug(f"Error deleting from disk cache for key '{key}': {e}")

    def keys(self) -> set[str]:
        """Return all keys in the disk cache. Returns empty set on errors."""
        try:
            return set(self._cache.iterkeys())
        except Exception as e:
            logger.debug(f"Error getting keys from disk cache: {e}")
            return set()

    def close(self) -> None:
        """Cleanup resources."""
        try:
            self._cache.close()
        except Exception:
            logger.exception("Error closing disk cache")

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache. Returns False on errors."""
        try:
            return key in self._cache
        except Exception as e:
            logger.debug(f"Error checking disk cache for key '{key}': {e}")
            return False
