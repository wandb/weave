from weave.utils.dict_utils import sum_dict_leaves


def test_sum_dict_leaves_list_of_dicts(client):
    """Test that sum_dict_leaves correctly handles lists of dictionaries."""
    dicts = [
        {"a": 1, "b": "hello", "c": 2},
        {"a": 3, "b": "world", "c": 4},
        {"a": 5, "b": "!", "c": 6},
    ]
    result = sum_dict_leaves(dicts)
    assert result == {"a": 9, "b": ["hello", "world", "!"], "c": 12}

    # Test with nested dictionaries in the list
    dicts = [
        {"a": {"x": 1, "y": 2}, "b": 3},
        {"a": {"x": 4, "y": 5}, "b": 6},
        {"a": {"x": 7, "y": 8}, "b": 9},
    ]
    result = sum_dict_leaves(dicts)
    assert result == {"a": {"x": 12, "y": 15}, "b": 18}

    # Test with empty list
    assert sum_dict_leaves([]) == {}

    # Test with list containing empty dictionaries
    assert sum_dict_leaves([{}]) == {}

    # Test with None values
    dicts = [
        {"a": 1, "b": None, "c": 2},
        {"a": 3, "b": None, "c": 4},
        {"a": 5, "b": None, "c": 6},
    ]
    result = sum_dict_leaves(dicts)
    assert result == {"a": 9, "c": 12}


def test_sum_dict_leaves_mixed_types(client):
    """Test that sum_dict_leaves correctly handles dictionaries where the same key has different types."""
    dicts = [
        {"a": 1, "b": "hello", "c": 2},
        {"a": "world", "b": 3, "c": 4},
        {"a": 5, "b": "!", "c": "test"},
    ]
    result = sum_dict_leaves(dicts)
    # When a key has mixed types, all values should be collected in a list
    assert result == {"a": [1, "world", 5], "b": ["hello", 3, "!"], "c": [2, 4, "test"]}

    # Test with nested dictionaries having mixed types
    dicts = [
        {"a": {"x": 1, "y": "hello"}, "b": 3},
        {"a": {"x": "world", "y": 2}, "b": "test"},
        {"a": {"x": 5, "y": 3}, "b": 6},
    ]
    result = sum_dict_leaves(dicts)
    assert result == {
        "a": {"x": [1, "world", 5], "y": ["hello", 2, 3]},
        "b": [3, "test", 6],
    }


def test_sum_dict_leaves_deep_nested(client):
    """Test that sum_dict_leaves correctly handles deeply nested dictionaries (2 levels) with mixed types."""
    dicts = [
        {
            "level1": {"level2": {"a": 1, "b": "hello", "c": {"x": 2, "y": "world"}}},
            "top": 10,
        },
        {
            "level1": {"level2": {"a": "test", "b": 3, "c": {"x": "deep", "y": 4}}},
            "top": "mixed",
        },
        {
            "level1": {"level2": {"a": 5, "b": "!", "c": {"x": 6, "y": "nested"}}},
            "top": 20,
        },
    ]
    result = sum_dict_leaves(dicts)
    assert result == {
        "level1": {
            "level2": {
                "a": [1, "test", 5],
                "b": ["hello", 3, "!"],
                "c": {"x": [2, "deep", 6], "y": ["world", 4, "nested"]},
            }
        },
        "top": [10, "mixed", 20],
    }
