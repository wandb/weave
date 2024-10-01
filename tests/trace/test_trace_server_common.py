import pytest

from weave.trace_server.trace_server_common import (
    LRUCache,
    get_nested_key,
    set_nested_key,
)


def test_get_nested_key():
    data = {"a": {"b": {"c": "d", "e": {}}}}
    assert get_nested_key(data, "a.b.c") == "d"
    assert get_nested_key(data, "a.b") == {"c": "d", "e": {}}
    assert get_nested_key(data, "a.b.e") == {}
    assert get_nested_key(data, "a.b.c.e") is None
    assert get_nested_key(data, "foobar") is None
    assert get_nested_key(data, "a.....") is None


def test_set_nested_key():
    data = {"a": {"b": "c", "j": {}}}
    set_nested_key(data, "a.b", "e")
    assert data == {"a": {"b": "e", "j": {}}}
    set_nested_key(data, "a.b.c", "d")
    assert data == {"a": {"b": {"c": "d"}, "j": {}}}
    set_nested_key(data, "a.b.c", {"e": "f"})
    assert data == {"a": {"b": {"c": {"e": "f"}}, "j": {}}}

    data = {}
    set_nested_key(data, "", "any")
    assert data == {}
    set_nested_key(data, ".....", "any")
    assert data == {}

    set_nested_key(data, "a.b.c", "d")
    assert data == {"a": {"b": {"c": "d"}}}


def test_lru_cache():
    cache = LRUCache(max_size=2)
    cache["a"] = 1
    cache["b"] = 2
    assert cache["a"] == 1
    assert cache["b"] == 2

    cache["c"] = 3
    assert "a" not in cache
    assert cache["b"] == 2
    assert cache["c"] == 3

    cache["d"] = 4
    assert "b" not in cache
    assert cache["c"] == 3
    assert cache["d"] == 4

    cache["c"] = 10
    assert cache["c"] == 10
    assert cache["d"] == 4
