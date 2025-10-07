"""Tests for cache implementations."""

import asyncio

import pytest

from weave.trace_server.caching.memory_cache import MemoryCache


@pytest.mark.asyncio
async def test_basic_operations():
    """Test basic cache operations: get, set, delete, clear."""
    cache = MemoryCache()

    # Get nonexistent key
    assert await cache.get("nonexistent") is None

    # Set and get
    await cache.set("key1", "value1")
    assert await cache.get("key1") == "value1"

    # Overwrite value
    await cache.set("key1", "value2")
    assert await cache.get("key1") == "value2"

    # Set multiple values
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")
    assert await cache.get("key2") == "value2"
    assert await cache.get("key3") == "value3"

    # Delete
    await cache.delete("key1")
    assert await cache.get("key1") is None
    assert await cache.get("key2") == "value2"  # Others still exist

    # Delete nonexistent key (should not raise)
    await cache.delete("nonexistent")

    # Clear all
    await cache.clear()
    assert await cache.get("key2") is None
    assert await cache.get("key3") is None


@pytest.mark.asyncio
async def test_ttl():
    """Test TTL functionality including expiration and overwriting."""
    cache = MemoryCache()

    # Set value without TTL - should never expire
    await cache.set("permanent", "value")
    await asyncio.sleep(0.05)
    assert await cache.get("permanent") == "value"

    # Set value with TTL
    await cache.set("ttl_key", "ttl_value", ttl=1)
    assert await cache.get("ttl_key") == "ttl_value"

    # After 0.05s, should still exist
    await asyncio.sleep(0.05)
    assert await cache.get("ttl_key") == "ttl_value"

    # After expiration, should be gone
    await asyncio.sleep(1)
    assert await cache.get("ttl_key") is None

    # Overwrite with new TTL
    await cache.set("key", "value1", ttl=1)
    await cache.set("key", "value2", ttl=10)
    await asyncio.sleep(1.05)
    assert await cache.get("key") == "value2"  # Should still exist with new TTL


@pytest.mark.asyncio
async def test_concurrent_access():
    """Test concurrent access to the cache."""
    cache = MemoryCache()

    async def set_values(start: int, count: int):
        for i in range(start, start + count):
            await cache.set(f"key{i}", f"value{i}")

    # Set values concurrently
    await asyncio.gather(
        set_values(0, 100),
        set_values(100, 100),
        set_values(200, 100),
    )

    # Verify all values are present
    for i in range(300):
        result = await cache.get(f"key{i}")
        assert result == f"value{i}"
