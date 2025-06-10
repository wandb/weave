from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Generic, TypeVar

import diskcache

logger = logging.getLogger(__name__)

V = TypeVar("V")


class ThreadSafeLRUCache(Generic[V]):
    """Thread-safe LRU cache implementation using OrderedDict.

    This implementation provides:
    - Thread-safe operations with proper locking
    - LRU eviction when max_size is exceeded
    - Move-to-end behavior on access to maintain LRU order
    """

    def __init__(self, max_size: int = 1000):
        """Initialize LRU cache with maximum size.

        Args:
            max_size: Maximum number of items to store. If 0, unlimited size.
        """
        self._max_size = max_size
        self._cache: OrderedDict[str, V] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> V | None:
        """Get value by key, moving it to end (most recently used).

        Args:
            key: The key to look up

        Returns:
            The value if found, None otherwise
        """
        with self._lock:
            if key not in self._cache:
                return None
            # Move to end to maintain LRU order
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value: V) -> None:
        """Set a key-value pair, evicting oldest if necessary.

        Args:
            key: The key to set
            value: The value to store
        """
        with self._lock:
            if key in self._cache:
                # Update existing key and move to end
                self._cache[key] = value
                self._cache.move_to_end(key)
            else:
                # Add new key
                self._cache[key] = value
                # Evict oldest if over capacity
                if len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)  # Remove oldest (first item)

    def delete(self, key: str) -> bool:
        """Delete a key from the cache.

        Args:
            key: The key to delete

        Returns:
            True if key existed and was deleted, False otherwise
        """
        with self._lock:
            try:
                del self._cache[key]
            except KeyError:
                return False
        return True

    def delete_keys_with_prefix(self, prefix: str) -> int:
        """Delete all keys that start with the given prefix.

        Args:
            prefix: The prefix to match

        Returns:
            Number of keys deleted
        """
        with self._lock:
            keys_to_delete = [
                key
                for key in self._cache.keys()
                if isinstance(key, str) and key.startswith(prefix)
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    def clear(self) -> None:
        """Clear all items from the cache."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        """Return the number of items in the cache."""
        with self._lock:
            return len(self._cache)


class MemCacheWithDiskCacheBackend:
    """
    A simple 2-layer cache with thread-safe memory cache and persistent disk cache.

    This implementation provides:
    1. Fast thread-safe memory cache for recent data using LRU eviction
    2. Persistent disk cache for cross-process storage
    3. Synchronous operations for consistency
    4. Simple and reliable error handling

    Design decisions:
    - All operations are synchronous to avoid consistency issues
    - Memory cache is checked first for speed
    - Disk cache provides persistence across processes
    - Memory cache is populated from disk hits for better performance
    - No background threading to avoid WAL consistency issues
    """

    def __init__(self, cache_dir: str, size_limit: int = 1_000_000_000):
        """Initialize the 2-layer cache.

        Args:
            cache_dir: Directory path for disk cache storage
            size_limit: Maximum size in bytes for disk cache (default 1GB)
        """
        self._disk_cache: diskcache.Cache[str, str | bytes] = diskcache.Cache(
            cache_dir, size_limit=size_limit
        )
        self._mem_cache: ThreadSafeLRUCache[str | bytes] = ThreadSafeLRUCache(
            max_size=1000
        )

    def get(self, key: str) -> str | bytes | None:
        """Get a value from the cache, checking memory first, then disk.

        Args:
            key: The cache key to look up

        Returns:
            The cached value if found, None otherwise
        """
        # First check memory cache (fast)
        value = self._mem_cache.get(key)
        if value is not None:
            return value

        # Check disk cache (slower)
        try:
            value = self._disk_cache.get(key)
            if value is not None:
                # Populate memory cache for future hits
                self._mem_cache.set(key, value)
                return value
        except Exception as e:
            logger.debug(f"Error reading from disk cache for key '{key}': {e}")

        return None

    def set(self, key: str, value: str | bytes) -> None:
        """Set a value in both memory and disk cache.

        Args:
            key: The cache key
            value: The value to store

        Note:
            This implementation assumes that the same key will ALWAYS have the same value,
            even after deletes. This allows us to optimize by checking disk cache existence
            before writing - if the key exists, we know it has the correct value already.
        """
        # Always update memory cache first (fast)
        self._mem_cache.set(key, value)

        # Check if key already exists in disk cache to avoid unnecessary write
        # Since same keys always have same values, existence check is sufficient
        try:
            if key in self._disk_cache:
                # Key exists, so it must have the same value - skip write
                return
        except Exception as e:
            logger.debug(f"Error checking disk cache existence for key '{key}': {e}")
            # Fall through to attempt write anyway

        # Key doesn't exist in disk cache, so write it
        try:
            self._disk_cache.set(key, value)
        except Exception as e:
            logger.warning(f"Error writing to disk cache for key '{key}': {e}")

    def delete(self, key: str) -> None:
        """Delete a key from both memory and disk cache.

        Args:
            key: The cache key to delete
        """
        # Delete from memory cache
        self._mem_cache.delete(key)

        # Delete from disk cache
        try:
            del self._disk_cache[key]
        except KeyError:
            pass  # Key didn't exist, that's fine
        except Exception as e:
            logger.warning(f"Error deleting from disk cache for key '{key}': {e}")

    def delete_keys_with_prefix(self, prefix: str) -> None:
        """Delete all keys that start with the given prefix from both caches.

        Args:
            prefix: The prefix to match for deletion
        """
        # Delete from memory cache
        deleted_count = self._mem_cache.delete_keys_with_prefix(prefix)
        logger.debug(
            f"Deleted {deleted_count} keys from memory cache with prefix '{prefix}'"
        )

        # Delete from disk cache
        try:
            deleted_count = 0
            # Get all keys with the prefix
            for key in list(self._disk_cache.iterkeys()):
                if key.startswith(prefix):
                    try:
                        del self._disk_cache[key]
                        deleted_count += 1
                    except KeyError:
                        pass  # Key was already deleted
            logger.debug(
                f"Deleted {deleted_count} keys from disk cache with prefix '{prefix}'"
            )
        except Exception as e:
            logger.warning(
                f"Error deleting keys with prefix '{prefix}' from disk cache: {e}"
            )

    def close(self) -> None:
        """Cleanup resources. Synchronous to ensure WAL is properly flushed."""
        try:
            # Clear memory cache
            self._mem_cache.clear()

            # Close disk cache - this should flush all pending operations
            self._disk_cache.close()
        except Exception as e:
            logger.exception(f"Error closing cache: {e}")
