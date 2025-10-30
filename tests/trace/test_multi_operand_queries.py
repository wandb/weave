"""Integration tests for multi-operand queries and populate_by_name support."""

import pytest

import weave
from weave.trace_server import trace_server_interface as tsi


@pytest.fixture
def sample_data(client):
    """Create sample calls for testing."""
    test_id = "multi_operand_test"

    @weave.op()
    def test_op(a: str, b: str, c: str, d: str, test_id: str) -> dict:
        return {"concat": a + b + c + d, "test_id": test_id}

    # Create calls with different combinations of values (using strings to avoid type issues)
    test_op(a="1", b="2", c="3", d="4", test_id=test_id)
    test_op(a="5", b="2", c="3", d="4", test_id=test_id)
    test_op(a="1", b="6", c="3", d="4", test_id=test_id)
    test_op(a="1", b="2", c="7", d="4", test_id=test_id)
    test_op(a="1", b="2", c="3", d="8", test_id=test_id)
    test_op(a="10", b="20", c="30", d="40", test_id=test_id)

    return test_id


def test_multi_operand_and_with_three_conditions(client, sample_data):
    """Test AND operation with 3 conditions."""
    test_id = sample_data

    # Query for calls where a="1" AND b="2" AND c="3"
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {"$eq": [{"$getField": "inputs.a"}, {"$literal": "1"}]},
                    {"$eq": [{"$getField": "inputs.b"}, {"$literal": "2"}]},
                    {"$eq": [{"$getField": "inputs.c"}, {"$literal": "3"}]},
                ]
            }
        }
    )

    calls = list(client.get_calls(query=query))
    # Should match 2 calls: ("1","2","3","4") and ("1","2","3","8")
    assert len(calls) == 2
    for call in calls:
        assert call.inputs["a"] == "1"
        assert call.inputs["b"] == "2"
        assert call.inputs["c"] == "3"


def test_multi_operand_and_with_four_conditions(client, sample_data):
    """Test AND operation with 4 conditions."""
    test_id = sample_data

    # Query for calls where a="1" AND b="2" AND c="3" AND d="4"
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {"$eq": [{"$getField": "inputs.a"}, {"$literal": "1"}]},
                    {"$eq": [{"$getField": "inputs.b"}, {"$literal": "2"}]},
                    {"$eq": [{"$getField": "inputs.c"}, {"$literal": "3"}]},
                    {"$eq": [{"$getField": "inputs.d"}, {"$literal": "4"}]},
                ]
            }
        }
    )

    calls = list(client.get_calls(query=query))
    # Should match exactly 1 call: ("1","2","3","4")
    assert len(calls) == 1
    assert calls[0].inputs["a"] == "1"
    assert calls[0].inputs["b"] == "2"
    assert calls[0].inputs["c"] == "3"
    assert calls[0].inputs["d"] == "4"


def test_multi_operand_or_with_four_conditions(client, sample_data):
    """Test OR operation with 4 conditions."""
    test_id = sample_data

    # Query for calls where a="5" OR b="6" OR c="7" OR d="8"
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$or": [
                            {"$eq": [{"$getField": "inputs.a"}, {"$literal": "5"}]},
                            {"$eq": [{"$getField": "inputs.b"}, {"$literal": "6"}]},
                            {"$eq": [{"$getField": "inputs.c"}, {"$literal": "7"}]},
                            {"$eq": [{"$getField": "inputs.d"}, {"$literal": "8"}]},
                        ]
                    },
                ]
            }
        }
    )

    calls = list(client.get_calls(query=query))
    # Should match 4 calls: ("5","2","3","4"), ("1","6","3","4"), ("1","2","7","4"), ("1","2","3","8")
    assert len(calls) == 4
    for call in calls:
        # Each call should have at least one of these values
        assert (
            call.inputs["a"] == "5"
            or call.inputs["b"] == "6"
            or call.inputs["c"] == "7"
            or call.inputs["d"] == "8"
        )


def test_nested_multi_operand_and_or(client, sample_data):
    """Test nested multi-operand AND and OR operations."""
    test_id = sample_data

    # Query for: (a="1" AND b="2" AND c="3") OR (a="10" AND b="20")
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$or": [
                            {
                                "$and": [
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.a"},
                                            {"$literal": "1"},
                                        ]
                                    },
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.b"},
                                            {"$literal": "2"},
                                        ]
                                    },
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.c"},
                                            {"$literal": "3"},
                                        ]
                                    },
                                ]
                            },
                            {
                                "$and": [
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.a"},
                                            {"$literal": "10"},
                                        ]
                                    },
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.b"},
                                            {"$literal": "20"},
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                ]
            }
        }
    )

    calls = list(client.get_calls(query=query))
    # Should match 3 calls: ("1","2","3","4"), ("1","2","3","8"), ("10","20","30","40")
    assert len(calls) == 3
    for call in calls:
        condition1 = (
            call.inputs["a"] == "1"
            and call.inputs["b"] == "2"
            and call.inputs["c"] == "3"
        )
        condition2 = call.inputs["a"] == "10" and call.inputs["b"] == "20"
        assert condition1 or condition2


def test_query_with_field_name_instead_of_alias(client, sample_data):
    """Test that queries can use field names instead of aliases due to populate_by_name."""
    test_id = sample_data

    # Use field names (and_, eq_, literal_, get_field_) instead of aliases
    query = tsi.Query.model_validate(
        {
            "expr_": {
                "and_": [
                    {"eq_": [{"get_field_": "inputs.test_id"}, {"literal_": test_id}]},
                    {"eq_": [{"get_field_": "inputs.a"}, {"literal_": "1"}]},
                    {"eq_": [{"get_field_": "inputs.b"}, {"literal_": "2"}]},
                ]
            }
        }
    )

    calls = list(client.get_calls(query=query))
    # Should match 3 calls: ("1","2","3","4"), ("1","2","7","4"), ("1","2","3","8")
    assert len(calls) == 3
    for call in calls:
        assert call.inputs["a"] == "1"
        assert call.inputs["b"] == "2"


def test_single_operand_and(client, sample_data):
    """Test AND operation with a single operand (should work like no AND)."""
    test_id = sample_data

    # AND with single operand should just evaluate that operand
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$and": [
                            {"$eq": [{"$getField": "inputs.a"}, {"$literal": "1"}]},
                        ]
                    },
                ]
            }
        }
    )

    calls = list(client.get_calls(query=query))
    # Should match 4 calls where a="1"
    assert len(calls) == 4
    for call in calls:
        assert call.inputs["a"] == "1"


def test_single_operand_or(client, sample_data):
    """Test OR operation with a single operand (should work like no OR)."""
    test_id = sample_data

    # OR with single operand should just evaluate that operand
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$or": [
                            {"$eq": [{"$getField": "inputs.a"}, {"$literal": "10"}]},
                        ]
                    },
                ]
            }
        }
    )

    calls = list(client.get_calls(query=query))
    # Should match 1 call where a="10"
    assert len(calls) == 1
    assert calls[0].inputs["a"] == "10"


def test_complex_multi_level_nesting(client, sample_data):
    """Test deeply nested multi-operand operations."""
    test_id = sample_data

    # Complex query: (a="1" AND (b="2" OR b="6")) OR (a="10" AND b="20" AND c="30")
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {"$eq": [{"$getField": "inputs.test_id"}, {"$literal": test_id}]},
                    {
                        "$or": [
                            {
                                "$and": [
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.a"},
                                            {"$literal": "1"},
                                        ]
                                    },
                                    {
                                        "$or": [
                                            {
                                                "$eq": [
                                                    {"$getField": "inputs.b"},
                                                    {"$literal": "2"},
                                                ]
                                            },
                                            {
                                                "$eq": [
                                                    {"$getField": "inputs.b"},
                                                    {"$literal": "6"},
                                                ]
                                            },
                                        ]
                                    },
                                ]
                            },
                            {
                                "$and": [
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.a"},
                                            {"$literal": "10"},
                                        ]
                                    },
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.b"},
                                            {"$literal": "20"},
                                        ]
                                    },
                                    {
                                        "$eq": [
                                            {"$getField": "inputs.c"},
                                            {"$literal": "30"},
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                ]
            }
        }
    )

    calls = list(client.get_calls(query=query))
    # Should match 5 calls:
    # - ("1","2","3","4"): a="1" and b="2"
    # - ("1","6","3","4"): a="1" and b="6"
    # - ("1","2","7","4"): a="1" and b="2"
    # - ("1","2","3","8"): a="1" and b="2"
    # - ("10","20","30","40"): a="10" and b="20" and c="30"
    assert len(calls) == 5
    for call in calls:
        condition1 = call.inputs["a"] == "1" and call.inputs["b"] in ["2", "6"]
        condition2 = (
            call.inputs["a"] == "10"
            and call.inputs["b"] == "20"
            and call.inputs["c"] == "30"
        )
        assert condition1 or condition2
