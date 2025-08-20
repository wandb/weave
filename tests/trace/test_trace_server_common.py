from weave.trace_server.trace_server_common import (
    DynamicBatchProcessor,
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


def test_dynamic_batch_processor():
    # Initialize processor with:
    # - initial batch size of 2
    # - max size of 8
    # - growth factor of 2
    processor = DynamicBatchProcessor(initial_size=2, max_size=8, growth_factor=2)

    test_data = range(15)

    batches = list(processor.make_batches(iter(test_data)))

    # Expected batch sizes: 2, 4, 8, 1
    assert batches[0] == [0, 1]
    assert batches[1] == [2, 3, 4, 5]
    assert batches[2] == [6, 7, 8, 9, 10, 11, 12, 13]
    assert batches[3] == [14]
    assert len(batches) == 4

    # Verify all items were processed
    flattened = [item for batch in batches for item in batch]
    assert flattened == list(range(15))
