import typing
from pydantic import BaseModel


# Can be any standard json-able value
class _RawValue(BaseModel):
    value_: typing.Union[
        str, int, float, bool, dict[str, "_RawValue"], list["_RawValue"]
    ]


# Field should be a key of `CallSchema`. For dictionary fields (`attributes`,
# `inputs`, `outputs`, `summary`), the field can be dot-separated.
class _FieldSelect(BaseModel):
    field_: str
    # Should this be an operation??
    cast_: typing.Optional[typing.Literal["str", "int", "float", "bool"]] = None


_Operand = typing.Union[_RawValue, _FieldSelect, "_Operation"]

# Operations: all operations have the form of a single property
# with the name of the operation suffixed with an underscore.
# Subset of Mongo Operators: https://www.mongodb.com/docs/manual/reference/operator/query/
# Starting with these operators for now since they are the most common and with negation
# can cover most of the other operators.
class _AndOperation(BaseModel):
    and_: typing.Tuple["_Operand", "_Operand"]


class _OrOperation(BaseModel):
    or_: typing.Tuple["_Operand", "_Operand"]


class _NotOperation(BaseModel):
    not_: "_Operand"


class _EqOperation(BaseModel):
    eq_: typing.Tuple["_Operand", "_Operand"]


class _GtOperation(BaseModel):
    gt_: typing.Tuple["_Operand", "_Operand"]


class _GteOperation(BaseModel):
    gte_: typing.Tuple["_Operand", "_Operand"]


class _LikeOperation(BaseModel):
    like_: typing.Tuple["_Operand", "_Operand"]


_Operation = typing.Union[
    _AndOperation,
    _OrOperation,
    _NotOperation,
    _EqOperation,
    _GtOperation,
    _GteOperation,
    _LikeOperation,
]


# Update the models to include the recursive types
_RawValue.model_rebuild()
_FieldSelect.model_rebuild()
_AndOperation.model_rebuild()
_OrOperation.model_rebuild()
_NotOperation.model_rebuild()
_EqOperation.model_rebuild()
_GtOperation.model_rebuild()
_GteOperation.model_rebuild()
_LikeOperation.model_rebuild()


class FilterBy(BaseModel):
    filter: _Operation

