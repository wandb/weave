"""
This file contains the interface definition for the Trace Server Query model. It
is heavily inspired by the MongoDB query language, but is a subset of the full
MongoDB query language. In particular, we have made the following
simplifications:

* We only support the "aggregation" operators, not the "query" operators. This is
    purely for simplicity and because the "aggregation" operators are more powerful.
    The Mongo docs language has evolved over time and the primary query language
    is column-oriented. However, the more expressive aggregation language can be
    used for both direct queries, but also for column comparison and
    calculations. We can add support for the "query" operators in the future if
    needed.

* We only support a subset of the operators / shorthand forms for now. We can add
    more operators in the future as needed.

    * One notable omission here is the lack of support for "$field" as a shorthand for
        the "getField"  operator.

* We have _added_ a `$contains` operator which is not in the MongoDB query
    language. This is a simple substring match operator.
"""

import typing

from pydantic import BaseModel, Field

# Operations: all operations have the form of a single property
# with the name of the operation suffixed with an underscore.
# Subset of Mongo _Aggregation_ Operators: https://www.mongodb.com/docs/manual/reference/operator/aggregation/
# Starting with these operators for now since they are the most common and with negation
# can cover most of the other operators.


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/literal/
# Can be any standard json-able value
class LiteralOperation(BaseModel):
    """
    Represents a constant value in the query language.

    This can be any standard JSON-serializable value.

    Example:
        ```
        {"$literal": "predict"}
        ```
    """

    literal_: typing.Union[
        str,
        int,
        float,
        bool,
        dict[str, "LiteralOperation"],
        list["LiteralOperation"],
        None,
    ] = Field(alias="$literal")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/getField/
# Note: currently only the shorthand form is supported.
# Field should be a key of `CallSchema`. For dictionary fields (`attributes`,
# `inputs`, `outputs`, `summary`), the field can be dot-separated.
# Here we support "dot notation" for accessing nested fields:
# https://www.mongodb.com/docs/manual/core/document/#dot-notation
class GetFieldOperator(BaseModel):
    # Tim: We will likely want to revisit this before making it public. Here are some concerns:
    # 1. Mongo explicitly says that `getField` is used to access fields without dot notation - this
    #    is not how we are handling it here - we are using dot notation - this could be resolved by
    #    supporting the `$field.with.path` shorthand.
    # 2. As Jamie pointed out, the parsing of this field is not very robust and susceptible to issues when:
    #    - The field part name contains a dot
    #    - The field part name is a valid integer (currently interpreted as a list index)
    #    - The field part name contains a double quote (will result in failed lookup - see `_quote_json_path` in `clickhouse_trace_server_batched.py`)
    #    These issues could be resolved by using an alternative syntax (perhaps backticks, square brackets, etc.). However
    #    this would diverge from the current Mongo syntax.
    """
    Access a field on the traced call.

    Supports dot notation for nested access, e.g. `summary.usage.tokens`.

    Only works on fields present in the `CallSchema`, including:
    - Top-level fields like `op_name`, `trace_id`, `started_at`
    - Nested fields like `inputs.input_name`, `summary.usage.tokens`, etc.

    Example:
        ```
        {"$getField": "op_name"}
        ```
    """

    get_field_: str = Field(alias="$getField")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/convert/
class ConvertOperation(BaseModel):
    """
    Convert the input value to a specific type (e.g., `int`, `bool`, `string`).

    Example:
        ```
        {
            "$convert": {
                "input": {"$getField": "inputs.value"},
                "to": "int"
            }
        }
        ```
    """

    convert_: "ConvertSpec" = Field(alias="$convert")


CastTo = typing.Literal["double", "string", "int", "bool", "exists"]


class ConvertSpec(BaseModel):
    """
    Specifies conversion details for `$convert`.

    - `input`: The operand to convert.
    - `to`: The type to convert to.
    """

    input: "Operand"
    # Subset of https://www.mongodb.com/docs/manual/reference/bson-types/#std-label-bson-types
    to: CastTo


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/and/
class AndOperation(BaseModel):
    """
    Logical AND. All conditions must evaluate to true.

    Example:
        ```
        {
            "$and": [
                {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]},
                {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]}
            ]
        }
        ```
    """

    and_: list["Operand"] = Field(alias="$and")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/or/
class OrOperation(BaseModel):
    """
    Logical OR. At least one condition must be true.

    Example:
        ```
        {
            "$or": [
                {"$eq": [{"$getField": "op_name"}, {"$literal": "a"}]},
                {"$eq": [{"$getField": "op_name"}, {"$literal": "b"}]}
            ]
        }
        ```
    """

    or_: list["Operand"] = Field(alias="$or")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/not/
class NotOperation(BaseModel):
    """
    Logical NOT. Inverts the condition.

    Example:
        ```
        {
            "$not": [
                {"$eq": [{"$getField": "op_name"}, {"$literal": "debug"}]}
            ]
        }
        ```
    """

    not_: tuple["Operand"] = Field(alias="$not")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/eq/
class EqOperation(BaseModel):
    """
    Equality check between two operands.

    Example:
        ```
        {
            "$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]
        }
        ```
    """

    eq_: tuple["Operand", "Operand"] = Field(alias="$eq")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/gt/
class GtOperation(BaseModel):
    """
    Greater than comparison.

    Example:
        ```
        {
            "$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
        }
        ```
    """

    gt_: tuple["Operand", "Operand"] = Field(alias="$gt")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/gte/
class GteOperation(BaseModel):
    """
    Greater than or equal comparison.

    Example:
        ```
        {
            "$gte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
        }
        ```
    """

    gte_: tuple["Operand", "Operand"] = Field(alias="$gte")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/in/
class InOperation(BaseModel):
    """
    Membership check.

    Returns true if the left operand is in the list provided as the second operand.

    Example:
        ```
        {
            "$in": [
                {"$getField": "op_name"},
                [{"$literal": "predict"}, {"$literal": "generate"}]
            ]
        }
        ```
    """

    in_: tuple["Operand", list["Operand"]] = Field(alias="$in")


# This is not technically in the Mongo spec. Mongo has:
# https://www.mongodb.com/docs/manual/reference/operator/aggregation/regexMatch/,
# however, rather than support a full regex match right now, we will
# support a substring match. We can add regex support later if needed.
class ContainsOperation(BaseModel):
    """
    Case-insensitive substring match.

    Not part of MongoDB. Weave-specific addition.

    Example:
        ```
        {
            "$contains": {
                "input": {"$getField": "display_name"},
                "substr": {"$literal": "llm"},
                "case_insensitive": true
            }
        }
        ```
    """

    contains_: "ContainsSpec" = Field(alias="$contains")


class ContainsSpec(BaseModel):
    """
    Specification for the `$contains` operation.

    - `input`: The string to search.
    - `substr`: The substring to search for.
    - `case_insensitive`: If true, match is case-insensitive.
    """

    input: "Operand"
    substr: "Operand"
    case_insensitive: typing.Optional[bool] = False


# Convenience type for all Operands and Operations
Operation = typing.Union[
    AndOperation,
    OrOperation,
    NotOperation,
    EqOperation,
    GtOperation,
    GteOperation,
    InOperation,
    ContainsOperation,
]
Operand = typing.Union[LiteralOperation, GetFieldOperator, ConvertOperation, Operation]

# Update the models to include the recursive types
LiteralOperation.model_rebuild()
GetFieldOperator.model_rebuild()
AndOperation.model_rebuild()
OrOperation.model_rebuild()
NotOperation.model_rebuild()
EqOperation.model_rebuild()
GtOperation.model_rebuild()
GteOperation.model_rebuild()
InOperation.model_rebuild()
ContainsOperation.model_rebuild()


class Query(BaseModel):
    # Here, we use `expr_` to match the MongoDB query language's "aggregation" operator syntax.
    # This is certainly a subset of the full MongoDB query language, but it is a good starting point.
    # https://www.mongodb.com/docs/manual/reference/operator/query/expr/#mongodb-query-op.-expr
    """
    The top-level object for querying traced calls.

    The `Query` wraps a single `$expr`, which uses Mongo-style aggregation operators
    to filter calls. This expression can combine logical conditions, comparisons,
    type conversions, and string matching.

    Examples:
        ```
        # Filter calls where op_name == "predict"
        {
            "$expr": {
                "$eq": [
                    {"$getField": "op_name"},
                    {"$literal": "predict"}
                ]
            }
        }

        # Filter where a call's display name contains "llm"
        {
            "$expr": {
                "$contains": {
                    "input": {"$getField": "display_name"},
                    "substr": {"$literal": "llm"},
                    "case_insensitive": true
                }
            }
        }
        ```
    """

    expr_: Operation = Field(alias="$expr")
    # In the future, we could have other top-level Query Operators as described here:
    # https://www.mongodb.com/docs/manual/reference/operator/query/
