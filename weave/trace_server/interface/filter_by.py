import typing
from pydantic import BaseModel


# Can be any standard json-able value
class RawValue(BaseModel):
    value_: typing.Union[str, int, float, bool, dict[str, "RawValue"], list["RawValue"]]


# Field should be a key of `CallSchema`. For dictionary fields (`attributes`,
# `inputs`, `outputs`, `summary`), the field can be dot-separated.
class FieldSelect(BaseModel):
    field_: str
    # Should this be an operation??
    cast_: typing.Optional[typing.Literal["str", "int", "float", "bool"]] = None


Operand = typing.Union[RawValue, FieldSelect, "Operation"]

# Operations: all operations have the form of a single property
# with the name of the operation suffixed with an underscore.
# Subset of Mongo Operators: https://www.mongodb.com/docs/manual/reference/operator/query/
# Starting with these operators for now since they are the most common and with negation
# can cover most of the other operators.
class AndOperation(BaseModel):
    and_: typing.Tuple["Operand", "Operand"]


class OrOperation(BaseModel):
    or_: typing.Tuple["Operand", "Operand"]


class NotOperation(BaseModel):
    not_: "Operand"


class EqOperation(BaseModel):
    eq_: typing.Tuple["Operand", "Operand"]


class GtOperation(BaseModel):
    gt_: typing.Tuple["Operand", "Operand"]


class GteOperation(BaseModel):
    gte_: typing.Tuple["Operand", "Operand"]


class LikeOperation(BaseModel):
    like_: typing.Tuple["Operand", "Operand"]


Operation = typing.Union[
    AndOperation,
    OrOperation,
    NotOperation,
    EqOperation,
    GtOperation,
    GteOperation,
    LikeOperation,
]


# Update the models to include the recursive types
RawValue.model_rebuild()
FieldSelect.model_rebuild()
AndOperation.model_rebuild()
OrOperation.model_rebuild()
NotOperation.model_rebuild()
EqOperation.model_rebuild()
GtOperation.model_rebuild()
GteOperation.model_rebuild()
LikeOperation.model_rebuild()


class FilterBy(BaseModel):
    filter: Operation
