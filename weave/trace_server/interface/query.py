"""
This file contains the interface definition for the Trace Server Query model. It
is heavily inspired by the MongoDB query language, but is a subset of the full
MongoDB query language. In particular, we have made the following simplifications:
* We only support the "aggregation" operators, not the "query" operators. This is purely
    for simplicity and because the "aggregation" operators are more powerful. The Mongo docs
    language has evolved over time and the primary query language is column-oriented. However, the
    more expressive aggregation language is more expressive and can be used for both direct queries,
    but also for column comparison and calculations. We can add support for the "query" operators
    in the future if needed.
* Instead of using a dollar sign ($) prefix for the operators, we use an underscore (_) suffix. This
    is simply to satisfy the python requirements for variable names.
* We only support a subset of the operators / shorthand forms for now. We can add more operators
    in the future as needed.
    * One notable omission here is the lack of support for "$field" as a shorthand for the "getField"
        operator.
* We have _added_ a `contains_` operator which is not in the MongoDB query language. This is a simple
    substring match operator.
"""

import typing
from pydantic import BaseModel, Field


class Query(BaseModel):
    # Here, we use `expr_` to match the MongoDB query language's "aggregation" operator syntax.
    # This is certainly a subset of the full MongoDB query language, but it is a good starting point.
    # https://www.mongodb.com/docs/manual/reference/operator/query/expr/#mongodb-query-op.-expr
    expr_: "Operation" = Field(alias="$expr")
    # In the future, we could have other top-level Query Operators as described here:
    # https://www.mongodb.com/docs/manual/reference/operator/query/


# Operations: all operations have the form of a single property
# with the name of the operation suffixed with an underscore.
# Subset of Mongo _Aggregation_ Operators: https://www.mongodb.com/docs/manual/reference/operator/aggregation/
# Starting with these operators for now since they are the most common and with negation
# can cover most of the other operators.

# https://www.mongodb.com/docs/manual/reference/operator/aggregation/literal/
# Can be any standard json-able value
class LiteralOperation(BaseModel):
    literal_: typing.Union[
        str, int, float, bool, dict[str, "LiteralOperation"], list["LiteralOperation"]
    ] = Field(alias="$literal")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/getField/
# Note: currently only the shorthand form is supported.
# Field should be a key of `CallSchema`. For dictionary fields (`attributes`,
# `inputs`, `outputs`, `summary`), the field can be dot-separated.
class GetFieldOperator(BaseModel):
    get_field_: str = Field(alias="$getField")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/convert/
class ConvertOperation(BaseModel):
    convert_: "ConvertSpec" = Field(alias="$convert")


class ConvertSpec(BaseModel):
    input: "Operand"
    # Subset of https://www.mongodb.com/docs/manual/reference/bson-types/#std-label-bson-types
    to: typing.Literal["double", "string", "int", "bool"]


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/and/
class AndOperation(BaseModel):
    and_: typing.List["Operand"] = Field(alias="$and")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/or/
class OrOperation(BaseModel):
    or_: typing.List["Operand"] = Field(alias="$or")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/not/
class NotOperation(BaseModel):
    not_: typing.Tuple["Operand"] = Field(alias="$not")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/eq/
class EqOperation(BaseModel):
    eq_: typing.Tuple["Operand", "Operand"] = Field(alias="$eq")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/gt/
class GtOperation(BaseModel):
    gt_: typing.Tuple["Operand", "Operand"] = Field(alias="$gt")


# https://www.mongodb.com/docs/manual/reference/operator/aggregation/gte/
class GteOperation(BaseModel):
    gte_: typing.Tuple["Operand", "Operand"] = Field(alias="$gte")


# This is not technically in the Mongo spec. Mongo has:
# https://www.mongodb.com/docs/manual/reference/operator/aggregation/regexMatch/,
# however, rather than support a full regex match right now, we will
# support a substring match. We can add regex support later if needed.
class ContainsOperation(BaseModel):
    contains_: "ContainsSpec" = Field(alias="$contains")


class ContainsSpec(BaseModel):
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
    ContainsOperation,
]
Operand = typing.Union[
    LiteralOperation, GetFieldOperator, ConvertOperation, "Operation"
]


# Update the models to include the recursive types
LiteralOperation.model_rebuild()
GetFieldOperator.model_rebuild()
AndOperation.model_rebuild()
OrOperation.model_rebuild()
NotOperation.model_rebuild()
EqOperation.model_rebuild()
GtOperation.model_rebuild()
GteOperation.model_rebuild()
ContainsOperation.model_rebuild()
