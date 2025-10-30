"""Tests for the query interface models, particularly testing populate_by_name and multi-operand operations."""

import pytest
from pydantic import ValidationError

from weave.trace_server.interface import query as tsi_query


class TestPopulateByName:
    """Test that all query operation models can be populated using both field names and aliases."""

    def test_literal_operation_with_alias(self):
        """Test LiteralOperation can be created using alias."""
        op = tsi_query.LiteralOperation.model_validate({"$literal": "test"})
        assert op.literal_ == "test"

    def test_literal_operation_with_field_name(self):
        """Test LiteralOperation can be created using field name."""
        op = tsi_query.LiteralOperation.model_validate({"literal_": "test"})
        assert op.literal_ == "test"

    def test_get_field_operator_with_alias(self):
        """Test GetFieldOperator can be created using alias."""
        op = tsi_query.GetFieldOperator.model_validate({"$getField": "inputs.value"})
        assert op.get_field_ == "inputs.value"

    def test_get_field_operator_with_field_name(self):
        """Test GetFieldOperator can be created using field name."""
        op = tsi_query.GetFieldOperator.model_validate({"get_field_": "inputs.value"})
        assert op.get_field_ == "inputs.value"

    def test_convert_operation_with_alias(self):
        """Test ConvertOperation can be created using alias."""
        op = tsi_query.ConvertOperation.model_validate(
            {
                "$convert": {
                    "input": {"$getField": "inputs.value"},
                    "to": "string",
                }
            }
        )
        assert op.convert_.to == "string"

    def test_convert_operation_with_field_name(self):
        """Test ConvertOperation can be created using field name."""
        op = tsi_query.ConvertOperation.model_validate(
            {
                "convert_": {
                    "input": {"$getField": "inputs.value"},
                    "to": "string",
                }
            }
        )
        assert op.convert_.to == "string"

    def test_and_operation_with_alias(self):
        """Test AndOperation can be created using alias."""
        op = tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {"$eq": [{"$getField": "a"}, {"$literal": 1}]},
                    {"$eq": [{"$getField": "b"}, {"$literal": 2}]},
                ]
            }
        )
        assert len(op.and_) == 2

    def test_and_operation_with_field_name(self):
        """Test AndOperation can be created using field name."""
        op = tsi_query.AndOperation.model_validate(
            {
                "and_": [
                    {"$eq": [{"$getField": "a"}, {"$literal": 1}]},
                    {"$eq": [{"$getField": "b"}, {"$literal": 2}]},
                ]
            }
        )
        assert len(op.and_) == 2

    def test_or_operation_with_alias(self):
        """Test OrOperation can be created using alias."""
        op = tsi_query.OrOperation.model_validate(
            {
                "$or": [
                    {"$eq": [{"$getField": "a"}, {"$literal": 1}]},
                    {"$eq": [{"$getField": "b"}, {"$literal": 2}]},
                ]
            }
        )
        assert len(op.or_) == 2

    def test_or_operation_with_field_name(self):
        """Test OrOperation can be created using field name."""
        op = tsi_query.OrOperation.model_validate(
            {
                "or_": [
                    {"$eq": [{"$getField": "a"}, {"$literal": 1}]},
                    {"$eq": [{"$getField": "b"}, {"$literal": 2}]},
                ]
            }
        )
        assert len(op.or_) == 2

    def test_not_operation_with_alias(self):
        """Test NotOperation can be created using alias."""
        op = tsi_query.NotOperation.model_validate(
            {"$not": [{"$eq": [{"$getField": "a"}, {"$literal": 1}]}]}
        )
        assert len(op.not_) == 1

    def test_not_operation_with_field_name(self):
        """Test NotOperation can be created using field name."""
        op = tsi_query.NotOperation.model_validate(
            {"not_": [{"$eq": [{"$getField": "a"}, {"$literal": 1}]}]}
        )
        assert len(op.not_) == 1

    def test_eq_operation_with_alias(self):
        """Test EqOperation can be created using alias."""
        op = tsi_query.EqOperation.model_validate(
            {"$eq": [{"$getField": "a"}, {"$literal": 1}]}
        )
        assert len(op.eq_) == 2

    def test_eq_operation_with_field_name(self):
        """Test EqOperation can be created using field name."""
        op = tsi_query.EqOperation.model_validate(
            {"eq_": [{"$getField": "a"}, {"$literal": 1}]}
        )
        assert len(op.eq_) == 2

    def test_gt_operation_with_alias(self):
        """Test GtOperation can be created using alias."""
        op = tsi_query.GtOperation.model_validate(
            {"$gt": [{"$getField": "a"}, {"$literal": 1}]}
        )
        assert len(op.gt_) == 2

    def test_gt_operation_with_field_name(self):
        """Test GtOperation can be created using field name."""
        op = tsi_query.GtOperation.model_validate(
            {"gt_": [{"$getField": "a"}, {"$literal": 1}]}
        )
        assert len(op.gt_) == 2

    def test_gte_operation_with_alias(self):
        """Test GteOperation can be created using alias."""
        op = tsi_query.GteOperation.model_validate(
            {"$gte": [{"$getField": "a"}, {"$literal": 1}]}
        )
        assert len(op.gte_) == 2

    def test_gte_operation_with_field_name(self):
        """Test GteOperation can be created using field name."""
        op = tsi_query.GteOperation.model_validate(
            {"gte_": [{"$getField": "a"}, {"$literal": 1}]}
        )
        assert len(op.gte_) == 2

    def test_in_operation_with_alias(self):
        """Test InOperation can be created using alias."""
        op = tsi_query.InOperation.model_validate(
            {
                "$in": [
                    {"$getField": "a"},
                    [{"$literal": 1}, {"$literal": 2}, {"$literal": 3}],
                ]
            }
        )
        assert len(op.in_) == 2

    def test_in_operation_with_field_name(self):
        """Test InOperation can be created using field name."""
        op = tsi_query.InOperation.model_validate(
            {
                "in_": [
                    {"$getField": "a"},
                    [{"$literal": 1}, {"$literal": 2}, {"$literal": 3}],
                ]
            }
        )
        assert len(op.in_) == 2

    def test_contains_operation_with_alias(self):
        """Test ContainsOperation can be created using alias."""
        op = tsi_query.ContainsOperation.model_validate(
            {
                "$contains": {
                    "input": {"$getField": "inputs.message"},
                    "substr": {"$literal": "test"},
                    "case_insensitive": True,
                }
            }
        )
        assert op.contains_.case_insensitive is True

    def test_contains_operation_with_field_name(self):
        """Test ContainsOperation can be created using field name."""
        op = tsi_query.ContainsOperation.model_validate(
            {
                "contains_": {
                    "input": {"$getField": "inputs.message"},
                    "substr": {"$literal": "test"},
                    "case_insensitive": True,
                }
            }
        )
        assert op.contains_.case_insensitive is True

    def test_query_with_alias(self):
        """Test Query can be created using alias."""
        query = tsi_query.Query.model_validate(
            {"$expr": {"$eq": [{"$getField": "a"}, {"$literal": 1}]}}
        )
        assert query.expr_ is not None

    def test_query_with_field_name(self):
        """Test Query can be created using field name."""
        query = tsi_query.Query.model_validate(
            {"expr_": {"$eq": [{"$getField": "a"}, {"$literal": 1}]}}
        )
        assert query.expr_ is not None


class TestMultiOperandAndOperation:
    """Test that AndOperation supports multiple operands (not just 2)."""

    def test_and_with_two_operands(self):
        """Test AndOperation with exactly 2 operands (backward compatibility)."""
        op = tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {"$eq": [{"$getField": "a"}, {"$literal": 1}]},
                    {"$eq": [{"$getField": "b"}, {"$literal": 2}]},
                ]
            }
        )
        assert len(op.and_) == 2

    def test_and_with_three_operands(self):
        """Test AndOperation with 3 operands."""
        op = tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {"$eq": [{"$getField": "a"}, {"$literal": 1}]},
                    {"$eq": [{"$getField": "b"}, {"$literal": 2}]},
                    {"$eq": [{"$getField": "c"}, {"$literal": 3}]},
                ]
            }
        )
        assert len(op.and_) == 3

    def test_and_with_many_operands(self):
        """Test AndOperation with many operands."""
        conditions = [
            {"$eq": [{"$getField": f"field_{i}"}, {"$literal": i}]}
            for i in range(10)
        ]
        op = tsi_query.AndOperation.model_validate({"$and": conditions})
        assert len(op.and_) == 10

    def test_and_with_one_operand(self):
        """Test AndOperation with a single operand."""
        op = tsi_query.AndOperation.model_validate(
            {"$and": [{"$eq": [{"$getField": "a"}, {"$literal": 1}]}]}
        )
        assert len(op.and_) == 1

    def test_and_with_nested_and(self):
        """Test AndOperation with nested AND operations."""
        op = tsi_query.AndOperation.model_validate(
            {
                "$and": [
                    {"$eq": [{"$getField": "a"}, {"$literal": 1}]},
                    {
                        "$and": [
                            {"$eq": [{"$getField": "b"}, {"$literal": 2}]},
                            {"$eq": [{"$getField": "c"}, {"$literal": 3}]},
                        ]
                    },
                    {"$eq": [{"$getField": "d"}, {"$literal": 4}]},
                ]
            }
        )
        assert len(op.and_) == 3


class TestMultiOperandOrOperation:
    """Test that OrOperation supports multiple operands (not just 2)."""

    def test_or_with_two_operands(self):
        """Test OrOperation with exactly 2 operands (backward compatibility)."""
        op = tsi_query.OrOperation.model_validate(
            {
                "$or": [
                    {"$eq": [{"$getField": "a"}, {"$literal": 1}]},
                    {"$eq": [{"$getField": "b"}, {"$literal": 2}]},
                ]
            }
        )
        assert len(op.or_) == 2

    def test_or_with_three_operands(self):
        """Test OrOperation with 3 operands."""
        op = tsi_query.OrOperation.model_validate(
            {
                "$or": [
                    {"$eq": [{"$getField": "a"}, {"$literal": 1}]},
                    {"$eq": [{"$getField": "b"}, {"$literal": 2}]},
                    {"$eq": [{"$getField": "c"}, {"$literal": 3}]},
                ]
            }
        )
        assert len(op.or_) == 3

    def test_or_with_many_operands(self):
        """Test OrOperation with many operands."""
        conditions = [
            {"$eq": [{"$getField": f"field_{i}"}, {"$literal": i}]}
            for i in range(10)
        ]
        op = tsi_query.OrOperation.model_validate({"$or": conditions})
        assert len(op.or_) == 10

    def test_or_with_one_operand(self):
        """Test OrOperation with a single operand."""
        op = tsi_query.OrOperation.model_validate(
            {"$or": [{"$eq": [{"$getField": "a"}, {"$literal": 1}]}]}
        )
        assert len(op.or_) == 1

    def test_or_with_nested_or(self):
        """Test OrOperation with nested OR operations."""
        op = tsi_query.OrOperation.model_validate(
            {
                "$or": [
                    {"$eq": [{"$getField": "a"}, {"$literal": 1}]},
                    {
                        "$or": [
                            {"$eq": [{"$getField": "b"}, {"$literal": 2}]},
                            {"$eq": [{"$getField": "c"}, {"$literal": 3}]},
                        ]
                    },
                    {"$eq": [{"$getField": "d"}, {"$literal": 4}]},
                ]
            }
        )
        assert len(op.or_) == 3


class TestComplexQueryValidation:
    """Test complex queries combining multiple features."""

    def test_complex_query_with_field_names_and_aliases_mixed(self):
        """Test that we can mix field names and aliases in a complex query."""
        # This tests that populate_by_name works at all levels
        query = tsi_query.Query.model_validate(
            {
                "$expr": {
                    "and_": [  # Using field name here
                        {"$eq": [{"$getField": "a"}, {"literal_": 1}]},  # Mixed
                        {
                            "or_": [  # Using field name
                                {"$eq": [{"get_field_": "b"}, {"$literal": 2}]},
                                {"$gt": [{"$getField": "c"}, {"$literal": 3}]},
                            ]
                        },
                    ]
                }
            }
        )
        assert query.expr_ is not None

    def test_multi_operand_and_or_combination(self):
        """Test combining multi-operand AND and OR operations."""
        query = tsi_query.Query.model_validate(
            {
                "$expr": {
                    "$and": [
                        {"$eq": [{"$getField": "field1"}, {"$literal": "value1"}]},
                        {"$eq": [{"$getField": "field2"}, {"$literal": "value2"}]},
                        {"$eq": [{"$getField": "field3"}, {"$literal": "value3"}]},
                        {
                            "$or": [
                                {
                                    "$eq": [
                                        {"$getField": "field4"},
                                        {"$literal": "value4"},
                                    ]
                                },
                                {
                                    "$eq": [
                                        {"$getField": "field5"},
                                        {"$literal": "value5"},
                                    ]
                                },
                                {
                                    "$eq": [
                                        {"$getField": "field6"},
                                        {"$literal": "value6"},
                                    ]
                                },
                                {
                                    "$eq": [
                                        {"$getField": "field7"},
                                        {"$literal": "value7"},
                                    ]
                                },
                            ]
                        },
                    ]
                }
            }
        )
        assert query.expr_ is not None
        # Verify structure
        assert isinstance(query.expr_, tsi_query.AndOperation)
        assert len(query.expr_.and_) == 4  # 3 eq operations + 1 or operation

