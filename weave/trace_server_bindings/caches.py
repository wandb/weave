from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Generic, Protocol, TypeVar

import diskcache

logger = logging.getLogger(__name__)

K = TypeVar("K")
V = TypeVar("V")


class CacheProtocol(Protocol[K, V]):
    """Protocol defining the interface for all cache implementations."""

    def get(self, key: K) -> V | None:
        """Get a value by key. Returns None if not found or on error."""
        ...

    def put(self, key: K, value: V) -> None:
        """Put a key-value pair. Silent on errors."""
        ...

    def delete(self, key: K) -> None:
        """Delete a key. Silent if key doesn't exist or on errors."""
        ...

    def keys(self) -> set[K]:
        """Return all keys in this cache layer. Returns empty set on errors."""
        ...

    def __contains__(self, key: K) -> bool:
        """Check if key exists in cache. Returns False on errors."""
        ...

    def close(self) -> None:
        """Cleanup resources."""
        ...


class LRUCache(Generic[K, V]):
    """Thread-safe LRU cache implementation using OrderedDict."""

    def __init__(self, max_size: int = 1000):
        """Initialize LRU cache with maximum size.

        Args:
            max_size: Maximum number of items to store
        """
        self._max_size = max_size
        self._cache: OrderedDict[K, V] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: K) -> V | None:
        """Get value by key, moving it to end (most recent). Returns None on error."""
        try:
            with self._lock:
                if key not in self._cache:
                    return None
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                return self._cache[key]
        except Exception as e:
            logger.debug(f"Error getting key '{key}' from memory cache: {e}")
            return None

    def put(self, key: K, value: V) -> None:
        """Put a key-value pair, evicting oldest if necessary. Silent on errors."""
        try:
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
        except Exception as e:
            logger.debug(f"Error setting key '{key}' in memory cache: {e}")

    def delete(self, key: K) -> None:
        """Delete a key from the cache. Silent on errors."""
        try:
            with self._lock:
                del self._cache[key]
        except (KeyError, Exception) as e:
            # Silent on both KeyError (key doesn't exist) and other errors
            logger.debug(f"Error deleting key '{key}' from memory cache: {e}")

    def keys(self) -> set[K]:
        """Return all keys in the cache. Returns empty set on errors."""
        try:
            with self._lock:
                return set(self._cache.keys())
        except Exception as e:
            logger.debug(f"Error getting keys from memory cache: {e}")
            return set()

    def clear(self) -> None:
        """Clear all items from the cache."""
        try:
            with self._lock:
                self._cache.clear()
        except Exception as e:
            logger.debug(f"Error clearing memory cache: {e}")

    def __contains__(self, key: K) -> bool:
        """Check if key exists in cache. Returns False on errors."""
        try:
            with self._lock:
                return key in self._cache
        except Exception as e:
            logger.debug(f"Error checking memory cache for key '{key}': {e}")
            return False

    def close(self) -> None:
        """Cleanup resources."""
        self.clear()

    def __len__(self) -> int:
        """Return the number of items in the cache."""
        try:
            with self._lock:
                return len(self._cache)
        except Exception:
            return 0


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
        except Exception as e:
            logger.exception(f"Error closing disk cache: {e}")

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache. Returns False on errors."""
        try:
            return key in self._cache
        except Exception as e:
            logger.debug(f"Error checking disk cache for key '{key}': {e}")
            return False


class StackedCache:
    """A cache that stacks multiple cache layers with configurable strategies.

    This implementation provides a general way to combine multiple cache layers:
    - Fast layers (like memory) are checked first
    - Writes can go to all layers or specific layers
    - Cache hits in slower layers populate faster layers
    """

    def __init__(
        self,
        layers: list[CacheProtocol[str, str | bytes]],
        populate_on_hit: bool = True,
        existence_check_optimization: bool = False,
    ):
        """Initialize stacked cache.

        Args:
            layers: List of cache layers, ordered from fastest to slowest
            populate_on_hit: Whether to populate faster layers on slower layer hits
            existence_check_optimization: Whether to check existence in slowest layer
                before writing (useful when same key always has same value)
        """
        if not layers:
            raise ValueError("At least one cache layer is required")

        self._layers = layers
        self._populate_on_hit = populate_on_hit
        self._existence_check_optimization = existence_check_optimization

    def get(self, key: str) -> str | bytes | None:
        """Get a value from the cache, checking layers from fastest to slowest."""
        for i, layer in enumerate(self._layers):
            value = layer.get(key)
            if value is not None:
                # Populate faster layers if this was a hit in a slower layer
                if self._populate_on_hit and i > 0:
                    for faster_layer in self._layers[:i]:
                        faster_layer.put(key, value)
                return value
        return None

    def put(self, key: str, value: str | bytes) -> None:
        """Put a value in all cache layers."""
        for layer in self._layers:
            should_write = True

            # Check if key exists - if so, we know it has the same value
            if self._existence_check_optimization and key in layer:
                should_write = False

            if should_write:
                layer.put(key, value)

    def delete(self, key: str) -> None:
        """Delete a key from all cache layers."""
        for layer in self._layers:
            layer.delete(key)

    def keys(self) -> set[str]:
        """Return union of all keys across all cache layers."""
        all_keys: set[str] = set()
        for layer in self._layers:
            try:
                layer_keys = layer.keys()
                all_keys.update(layer_keys)
            except Exception as e:
                logger.debug(f"Error getting keys from cache layer: {e}")
                # Continue with other layers
        return all_keys

    def __contains__(self, key: str) -> bool:
        """Check if key exists in any cache layer."""
        for layer in self._layers:
            try:
                if key in layer:
                    return True
            except Exception as e:
                logger.debug(f"Error checking cache layer for key '{key}': {e}")
                # Continue with other layers
        return False

    def close(self) -> None:
        """Close all cache layers."""
        for layer in self._layers:
            layer.close()

    @property
    def layers(self) -> list[CacheProtocol[str, str | bytes]]:
        """Access to the underlying cache layers."""
        return self._layers
