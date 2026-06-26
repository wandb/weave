"""This file contains the interface definition for the Trace Server Query model. It
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

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Operations: all operations have the form of a single property
# with the name of the operation suffixed with an underscore.
# Subset of Mongo _Aggregation_ Operators: https://www.mongodb.com/docs/manual/reference/operator/aggregation/
# Starting with these operators for now since they are the most common and with negation
# can cover most of the other operators.


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/literal/
# Can be any standard json-able value
class LiteralOperation(BaseModel):
    """Represents a constant value in the query language.

    This can be any standard JSON-serializable value.

    Example:
        ```
        {"$literal": "predict"}
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    literal_: (
        str
        | int
        | float
        | bool
        | dict[str, "LiteralOperation"]
        | list["LiteralOperation"]
        | None
    ) = Field(alias="$literal")


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
    """Access a field on the traced call.

    Supports dot notation for nested access, e.g. `summary.usage.tokens`.

    Only works on fields present in the `CallSchema`, including:
    - Top-level fields like `op_name`, `trace_id`, `started_at`
    - Nested fields like `inputs.input_name`, `summary.usage.tokens`, etc.

    Example:
        ```
        {"$getField": "op_name"}
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    get_field_: str = Field(alias="$getField")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/convert/
class ConvertOperation(BaseModel):
    """Convert the input value to a specific type (e.g., `int`, `bool`, `string`).

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

    model_config = ConfigDict(populate_by_name=True)

    convert_: "ConvertSpec" = Field(alias="$convert")


CastTo = Literal["double", "string", "int", "bool", "exists"]


class ConvertSpec(BaseModel):
    """Specifies conversion details for `$convert`.

    - `input`: The operand to convert.
    - `to`: The type to convert to.
    """

    input: "Operand"
    # Subset of https://www.mongodb.com/docs/manual/reference/bson-types/#std-label-bson-types
    to: CastTo


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/and/
class AndOperation(BaseModel):
    """Logical AND. All conditions must evaluate to true.

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

    model_config = ConfigDict(populate_by_name=True)

    and_: list["Operand"] = Field(alias="$and")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/or/
class OrOperation(BaseModel):
    """Logical OR. At least one condition must be true.

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

    model_config = ConfigDict(populate_by_name=True)

    or_: list["Operand"] = Field(alias="$or")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/not/
class NotOperation(BaseModel):
    """Logical NOT. Inverts the condition.

    Example:
        ```
        {
            "$not": [
                {"$eq": [{"$getField": "op_name"}, {"$literal": "debug"}]}
            ]
        }
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    not_: tuple["Operand"] = Field(alias="$not")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/eq/
class EqOperation(BaseModel):
    """Equality check between two operands.

    Example:
        ```
        {
            "$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]
        }
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    eq_: tuple["Operand", "Operand"] = Field(alias="$eq")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/gt/
class GtOperation(BaseModel):
    """Greater than comparison.

    Example:
        ```
        {
            "$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
        }
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    gt_: tuple["Operand", "Operand"] = Field(alias="$gt")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/lt/
class LtOperation(BaseModel):
    """Less than comparison.

    Example:
        ```
        {
            "$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
        }
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    lt_: tuple["Operand", "Operand"] = Field(alias="$lt")


# https://www.mongodb.com/docs/manual/reference/aggregation/gte/
class GteOperation(BaseModel):
    """Greater than or equal comparison.

    Example:
        ```
        {
            "$gte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
        }
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    gte_: tuple["Operand", "Operand"] = Field(alias="$gte")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/lte/
class LteOperation(BaseModel):
    """Less than or equal comparison.

    Example:
        ```
        {
            "$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}]
        }
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    lte_: tuple["Operand", "Operand"] = Field(alias="$lte")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/in/
class InOperation(BaseModel):
    """Membership check.

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

    model_config = ConfigDict(populate_by_name=True)

    in_: tuple["Operand", list["Operand"]] = Field(alias="$in")


# This is not technically in the Mongo spec. Mongo has:
# https://www.mongodb.com/docs/manual/reference/operator/aggregation/regexMatch/,
# however, rather than support a full regex match right now, we will
# support a substring match. We can add regex support later if needed.
class ContainsOperation(BaseModel):
    """Case-insensitive substring match.

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

    model_config = ConfigDict(populate_by_name=True)

    contains_: "ContainsSpec" = Field(alias="$contains")


class ContainsSpec(BaseModel):
    """Specification for the `$contains` operation.

    - `input`: The string to search.
    - `substr`: The substring to search for.
    - `case_insensitive`: If true, match is case-insensitive.
    """

    input: "Operand"
    substr: "Operand"
    case_insensitive: bool | None = False


class ContainsTokenOperation(BaseModel):
    """Whole-token match. Compiles to ClickHouse `hasToken`.

    Not part of MongoDB. Weave-specific addition. Matches when `substr` equals
    one of the tokens in `input` (tokens split on non-alphanumeric runs),
    unlike `$contains` which does a substring search.

    Example:
        ```
        {
            "$containsToken": {
                "input": {"$getField": "display_name"},
                "substr": {"$literal": "llm"},
                "case_insensitive": true
            }
        }
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    contains_token_: "ContainsTokenSpec" = Field(alias="$containsToken")


class ContainsTokenSpec(BaseModel):
    """Specification for the `$containsToken` operation.

    - `input`: The string to search.
    - `substr`: The whole token to search for.
    - `case_insensitive`: If true, match is case-insensitive.
    """

    input: "Operand"
    substr: "Operand"
    case_insensitive: bool | None = False


# Convenience type for all Operands and Operations
Operation = (
    AndOperation
    | OrOperation
    | NotOperation
    | EqOperation
    | GtOperation
    | LtOperation
    | GteOperation
    | LteOperation
    | InOperation
    | ContainsOperation
    | ContainsTokenOperation
)
Operand = LiteralOperation | GetFieldOperator | ConvertOperation | Operation

# Update the models to include the recursive types
LiteralOperation.model_rebuild()
GetFieldOperator.model_rebuild()
AndOperation.model_rebuild()
OrOperation.model_rebuild()
NotOperation.model_rebuild()
EqOperation.model_rebuild()
GtOperation.model_rebuild()
LtOperation.model_rebuild()
GteOperation.model_rebuild()
LteOperation.model_rebuild()
InOperation.model_rebuild()
ContainsOperation.model_rebuild()
ContainsTokenOperation.model_rebuild()


def infer_literal_filter_cast(operand: Operand) -> CastTo | None:
    """Infer a JSON dynamic-field cast from a comparison operand.

    `JSON_VALUE` returns strings, so numeric and boolean literals need the
    field side cast to match the parameter type the backend receives. String,
    `None`, and structured literals keep the existing uncast path.
    """
    if not isinstance(operand, LiteralOperation):
        return None

    value = operand.literal_
    # `bool` must be checked before `int` since `bool` is a subclass of `int`.
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    return None


def infer_shared_literal_filter_cast(
    operands: Sequence[Operand],
) -> CastTo | None:
    """Return a shared inferred cast for a homogeneous literal list.

    Mixed `int` + `double` lists promote to `double` so the field is parsed
    once. Any other mix (e.g. `int` + `bool`) returns `None` so the existing
    uncast path runs.
    """
    casts: set[CastTo] = set()
    for operand in operands:
        operand_cast = infer_literal_filter_cast(operand)
        if operand_cast is None:
            return None
        casts.add(operand_cast)
    if casts == {"int", "double"}:
        return "double"
    if len(casts) == 1:
        return next(iter(casts))
    return None


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

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
