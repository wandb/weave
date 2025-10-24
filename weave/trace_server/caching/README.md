# Cache Service

A simple, backend-agnostic caching service for the trace server with support for both in-memory and Redis implementations.

## Features

- **Backend Agnostic**: Switch between different cache implementations via a common protocol
- **TTL Support**: Set time-to-live for cache entries
- **Async/Await**: Fully async interface for high performance
- **Thread-Safe**: In-memory cache uses async locks for safe concurrent access
- **Type-Safe**: Full type hints for better IDE support

## Implementations

### In-Memory Cache

A simple in-memory cache backed by a Python dictionary. Perfect for:
- Testing
- Development environments
- Single-instance deployments
- Non-distributed applications

```python
from weave.trace_server.caching.memory_cache import MemoryCache

# Create cache instance
cache = MemoryCache()

# Set a value (no expiration)
await cache.set("user:123", "John Doe")

# Set a value with TTL (expires after 60 seconds)
await cache.set("session:abc", "active", ttl=60)

# Get a value
user = await cache.get("user:123")

# Delete a value
await cache.delete("user:123")

# Clear all entries
await cache.clear()
```

### Redis Cache

A distributed cache implementation using Redis. Perfect for:
- Production environments
- Multi-instance deployments
- Shared cache across services
- Persistent caching needs

```python
from weave.trace_server.caching.redis_cache import RedisCache

# Create cache instance
cache = RedisCache(
    host="localhost",
    port=6379,
    db=0,
    password="your-password"  # optional
)

# Same API as MemoryCache
await cache.set("user:123", "John Doe")
await cache.set("session:abc", "active", ttl=60)
user = await cache.get("user:123")
await cache.delete("user:123")

# Close connection when done
await cache.close()
```

## Protocol

Both implementations conform to the `CacheProtocol`, which defines:

- `async get(key: str) -> Optional[str]`: Retrieve a value
- `async set(key: str, value: str, ttl: Optional[int] = None) -> None`: Store a value
- `async delete(key: str) -> None`: Remove a value
- `async clear() -> None`: Clear all entries

## Usage Example

Here's how to use the cache in a backend-agnostic way:

```python
from weave.trace_server.caching.memory_cache import MemoryCache
from weave.trace_server.caching.protocol import CacheProtocol
from weave.trace_server.caching.redis_cache import RedisCache


def get_cache(use_redis: bool = False) -> CacheProtocol:
    """Factory function to get cache implementation."""
    if use_redis:
        return RedisCache(host="localhost", port=6379)
    return MemoryCache()

# Use the cache
cache = get_cache(use_redis=True)
await cache.set("key", "value", ttl=300)
value = await cache.get("key")
```

## Testing

Tests are located in `tests/trace/test_cache.py`. Run with:

```bash
pytest tests/trace/test_cache.py -v
```

## Requirements

The in-memory cache has no external dependencies. The Redis cache requires the `redis` package, which is included in the trace server dependencies (`requirements.txt`).
