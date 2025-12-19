"""Tests for serialization and deserialization of primitive types.

This module tests the round-trip serialization of primitive Python types:
- int, float, bool, None, str
- list, tuple, dict

These types should be fully reversible (except tuple -> list).
"""

from __future__ import annotations

import math

import pytest

from weave.trace.serialization.serialize import from_json, to_json


class TestPrimitiveSerialization:
    """Tests for primitive type serialization round-trips."""

    @pytest.mark.parametrize(
        "value",
        [
            # Integers
            0,
            1,
            -1,
            42,
            -42,
            2**31 - 1,  # Max 32-bit signed
            -(2**31),  # Min 32-bit signed
            2**63 - 1,  # Max 64-bit signed
            10**100,  # Very large int
            # Floats
            0.0,
            1.0,
            -1.0,
            3.14159265358979,
            -2.718,
            1e-10,
            1e10,
            1.7976931348623157e308,  # Near max float
            # Booleans
            True,
            False,
            # None
            None,
            # Strings
            "",
            "a",
            "hello world",
            "Hello, World!",
            "unicode: 日本語",
            "emoji: 🎉🚀",
            "special: \t\n\r",
            'tab:\t newline:\n quote:" backslash:\\',
            "quotes: \"'`",
            "backslash: \\",
            " " * 100,
            "a" * 100,
            """Line 1
Line 2
Line 3""",
        ],
    )
    def test_primitive_round_trip(self, client, value) -> None:
        """Test that primitives serialize and deserialize correctly."""
        project_id = client._project_id()
        serialized = to_json(value, project_id, client)
        deserialized = from_json(serialized, project_id, client.server)
        assert deserialized == value
        assert type(deserialized) is type(value)

    @pytest.mark.parametrize(
        "value",
        [
            float("inf"),
            float("-inf"),
        ],
    )
    def test_infinity_serialization(self, client, value: float) -> None:
        """Test infinity values serialize (behavior may vary with JSON)."""
        project_id = client._project_id()
        serialized = to_json(value, project_id, client)
        # Infinity may be kept as float or converted to string depending on JSON handling
        assert serialized == value or isinstance(serialized, str)

    def test_nan_serialization(self, client) -> None:
        """Test NaN serialization (NaN != NaN so needs special handling)."""
        project_id = client._project_id()
        value = float("nan")
        serialized = to_json(value, project_id, client)
        if isinstance(serialized, float):
            assert math.isnan(serialized)


class TestListSerialization:
    """Tests for list serialization."""

    @pytest.mark.parametrize(
        "value",
        [
            [],
            [1, 2, 3, 4, 5],
            [1, "two", 3.0, True, None],
            [[1, 2], [3, 4], [5, [6, 7]]],
        ],
    )
    def test_list_round_trip(self, client, value: list) -> None:
        """Test that lists serialize and deserialize correctly."""
        project_id = client._project_id()
        serialized = to_json(value, project_id, client)
        assert serialized == value
        assert isinstance(serialized, list)

        deserialized = from_json(serialized, project_id, client.server)
        assert deserialized == value
        assert isinstance(deserialized, list)


class TestTupleSerialization:
    """Tests for tuple serialization.

    Note: Tuples are serialized as lists and deserialized back as lists.
    This is a known limitation - tuple type info is lost.
    """

    @pytest.mark.parametrize(
        "value,expected",
        [
            ((), []),
            ((1, 2, 3), [1, 2, 3]),
            ((1, "two", 3.0), [1, "two", 3.0]),
            (((1, 2), (3, 4)), [[1, 2], [3, 4]]),
        ],
    )
    def test_tuple_becomes_list(self, client, value: tuple, expected: list) -> None:
        """Test that tuples serialize to lists (type info lost)."""
        project_id = client._project_id()
        serialized = to_json(value, project_id, client)
        assert serialized == expected
        assert isinstance(serialized, list)

        deserialized = from_json(serialized, project_id, client.server)
        assert deserialized == expected
        assert isinstance(deserialized, list)  # Not tuple


class TestDictSerialization:
    """Tests for dict serialization."""

    @pytest.mark.parametrize(
        "value",
        [
            {},
            {"a": 1, "b": 2, "c": 3},
            {
                "int": 42,
                "float": 3.14,
                "str": "hello",
                "bool": True,
                "none": None,
                "list": [1, 2, 3],
            },
            {"level1": {"level2": {"level3": {"value": 42}}}},
            {"items": [1, 2, 3], "nested": [[1], [2], [3]]},
        ],
    )
    def test_dict_round_trip(self, client, value: dict) -> None:
        """Test that dicts serialize and deserialize correctly."""
        project_id = client._project_id()
        serialized = to_json(value, project_id, client)
        assert serialized == value
        assert isinstance(serialized, dict)

        deserialized = from_json(serialized, project_id, client.server)
        assert deserialized == value
        assert isinstance(deserialized, dict)
