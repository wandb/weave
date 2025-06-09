from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Generic, TypeVar

import diskcache

logger = logging.getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


class ThreadSafeLRUCache(Generic[K, V]):
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
        self.max_size = max_size
        self._cache: OrderedDict[K, V] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: K) -> V | None:
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

    def __setitem__(self, key: K, value: V) -> None:
        """Set value for key, with LRU eviction if needed.

        Args:
            key: The key to set
            value: The value to store
        """
        with self._lock:
            if key in self._cache:
                # Update existing key, move to end
                self._cache[key] = value
                self._cache.move_to_end(key)
            else:
                # Add new key
                if self.max_size > 0 and len(self._cache) >= self.max_size:
                    # Remove least recently used (first item)
                    self._cache.popitem(last=False)
                self._cache[key] = value

    def __delitem__(self, key: K) -> None:
        """Delete key from cache.

        Args:
            key: The key to delete

        Raises:
            KeyError: If key not found
        """
        with self._lock:
            del self._cache[key]

    def __contains__(self, key: K) -> bool:
        """Check if key exists in cache.

        Args:
            key: The key to check

        Returns:
            True if key exists, False otherwise
        """
        with self._lock:
            return key in self._cache

    def keys(self) -> list[K]:
        """Return a view of cache keys.

        Returns:
            A view of the cache keys
        """
        with self._lock:
            return list(self._cache.keys())

    def clear(self) -> None:
        """Clear all items from cache."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        """Return number of items in cache."""
        with self._lock:
            return len(self._cache)


class MemCacheWithDiskCacheBackend:
    """
    A multi-stage cache with a quick memory cache and a slower disk cache.

    This implementation provides:
    1. Fast memory cache for recent data using thread-safe LRU eviction
    2. Persistent disk cache for long-term storage
    3. Background disk I/O to avoid blocking the main thread
    4. Proper error handling and recovery from cache failures
    5. Memory cache population from disk cache hits for better performance
    6. Thread-safe operations with proper cleanup

    Design decisions:
    - Disk I/O is backgrounded to prevent blocking, with the assumption that
      items with the same key have the same value for the program duration
    - Memory cache is immediately updated on writes for fast subsequent reads
    - Disk cache errors don't fail the operation, they just log warnings
    - Pending disk writes are tracked to avoid duplicate writes and enable cancellation
    - Proper cleanup ensures all background operations complete on shutdown

    Thread Safety:
    - Memory cache operations are protected by locks
    - Disk operations are handled by a single background thread
    - Pending writes tracking is protected by a separate lock
    """

    def __init__(self, cache_dir: str, size_limit: int = 1_000_000_000):
        """Initialize the multi-stage cache.

        Args:
            cache_dir: Directory path for disk cache storage
            size_limit: Maximum size in bytes for disk cache (default 1GB)
        """
        self._disk_cache: diskcache.Cache[str, str | bytes] = diskcache.Cache(
            cache_dir, size_limit=size_limit
        )
        self._mem_cache: ThreadSafeLRUCache[str, str | bytes] = ThreadSafeLRUCache(
            max_size=1000
        )
        self._disk_cache_thread_pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="weave-cache-disk-writer"
        )
        self._pending_disk_writes: dict[str, Any] = {}
        self._pending_lock = threading.Lock()

    def close(self, wait: bool = False) -> None:
        """Cleanup resources, ensuring pending disk writes complete."""
        try:
            # Wait for pending disk operations to complete
            self._disk_cache_thread_pool.shutdown(wait=wait)
        except Exception as e:
            logger.warning(f"Error waiting for disk cache operations to complete: {e}")

        try:
            self._disk_cache.close()
        except Exception as e:
            logger.exception(f"Error closing disk cache: {e}")

    def get(self, key: str) -> str | bytes | None:
        """Get value from cache, checking memory first, then disk.

        Args:
            key: The cache key to look up

        Returns:
            The cached value if found, None otherwise
        """
        # First check memory cache
        res = self._mem_cache.get(key)
        if res is not None:
            return res

        # Then check disk cache
        try:
            res = self._disk_cache.get(key)
            if res is not None:
                # Populate memory cache with disk result for faster future access
                self._mem_cache[key] = res
                return res
        except Exception as e:
            logger.exception(f"Error reading from disk cache: {e}")

        return None

    def set(self, key: str, value: str | bytes) -> None:
        """Set value in cache, updating memory immediately and disk in background.

        Args:
            key: The cache key
            value: The value to cache
        """
        # Immediately set in memory cache
        self._mem_cache[key] = value

        # Check if we already have a pending write for this key
        with self._pending_lock:
            if key in self._pending_disk_writes:
                # Cancel the previous write since we have a newer value
                try:
                    self._pending_disk_writes[key].cancel()
                except Exception:
                    pass  # Future might already be running

        # Background the disk write
        future = self._disk_cache_thread_pool.submit(self._safe_disk_set, key, value)

        with self._pending_lock:
            self._pending_disk_writes[key] = future

        # Clean up completed futures
        future.add_done_callback(lambda f: self._cleanup_pending_write(key))

    def _safe_disk_set(self, key: str, value: str | bytes) -> None:
        """Safely write to disk cache with error handling.

        Args:
            key: The cache key
            value: The value to write
        """
        try:
            self._disk_cache.set(key, value)
        except Exception as e:
            logger.exception(f"Error writing to disk cache for key '{key}': {e}")

    def _cleanup_pending_write(self, key: str) -> None:
        """Remove completed write from pending writes dict.

        Args:
            key: The cache key that finished writing
        """
        with self._pending_lock:
            self._pending_disk_writes.pop(key, None)

    def delete(self, key: str) -> None:
        """Delete key from both memory and disk cache.

        Args:
            key: The cache key to delete
        """
        # Remove from memory cache
        try:
            del self._mem_cache[key]
        except KeyError:
            pass

        # Cancel any pending disk write
        with self._pending_lock:
            pending_future = self._pending_disk_writes.pop(key, None)
            if pending_future:
                try:
                    pending_future.cancel()
                except Exception:
                    pass

        # Remove from disk cache (backgrounded)
        self._disk_cache_thread_pool.submit(self._safe_disk_delete, key)

    def _safe_disk_delete(self, key: str) -> None:
        """Safely delete from disk cache with error handling.

        Args:
            key: The cache key to delete
        """
        try:
            self._disk_cache.delete(key)
        except Exception as e:
            logger.exception(f"Error deleting from disk cache for key '{key}': {e}")

    def __contains__(self, key: str) -> bool:
        """Check if key exists in either memory or disk cache.

        Args:
            key: The cache key to check

        Returns:
            True if key exists in either cache, False otherwise
        """
        if key in self._mem_cache:
            return True
        try:
            return key in self._disk_cache
        except Exception as e:
            logger.exception(f"Error checking disk cache for key '{key}': {e}")
            return False

    def delete_keys_with_prefix(self, prefix: str) -> None:
        """Delete all cached entries that start with the given prefix.

        Args:
            prefix: The prefix to match for deletion
        """
        try:
            # Get keys from memory cache
            mem_keys_to_delete = [
                key for key in self._mem_cache.keys() if key.startswith(prefix)
            ]

            # Delete from memory cache
            for key in mem_keys_to_delete:
                try:
                    del self._mem_cache[key]
                except KeyError:
                    pass

            # Delete from disk cache (this is more expensive, so we do it in background)
            def delete_disk_keys_with_prefix() -> None:
                try:
                    disk_keys_to_delete = [
                        key for key in self._disk_cache if key.startswith(prefix)
                    ]
                    for key in disk_keys_to_delete:
                        try:
                            self._disk_cache.delete(key)
                        except Exception as e:
                            logger.exception(
                                f"Error deleting disk cache key '{key}': {e}"
                            )
                except Exception as e:
                    logger.exception(
                        f"Error scanning disk cache for prefix '{prefix}': {e}"
                    )

            # Submit disk cleanup as background task
            self._disk_cache_thread_pool.submit(delete_disk_keys_with_prefix)

        except Exception as e:
            logger.exception(
                f"Error deleting cached values with prefix '{prefix}': {e}"
            )
