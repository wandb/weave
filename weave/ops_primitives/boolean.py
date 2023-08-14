import typing
from ..api import op, weave_class
from .. import weave_types as types


@weave_class(weave_type=types.Boolean)
class Boolean:
    @op(name="boolean-equal")
    def bool_equals(lhs: typing.Optional[bool], rhs: typing.Optional[bool]) -> bool:  # type: ignore
        return lhs == rhs

    @op(name="boolean-notEqual")
    def bool_notEquals(lhs: typing.Optional[bool], rhs: typing.Optional[bool]) -> bool:  # type: ignore
        return lhs != rhs

    @op(name="and")
    def bool_and(lhs: bool, rhs: typing.Optional[bool]) -> bool:  # type: ignore
        return lhs and bool(rhs)

    @op(name="or")
    def bool_or(lhs: bool, rhs: typing.Optional[bool]) -> bool:  # type: ignore
        return lhs or bool(rhs)

    @op(name="boolean-not")
    def bool_not(bool: bool) -> bool:  # type: ignore
        return not bool


types.Boolean.instance_class = Boolean


def none_coalesce_output_type(input_types):
    if types.NoneType().assign_type(input_types["lhs"]):
        return input_types["rhs"]
    return types.union(input_types["lhs"], input_types["rhs"])


@op(name="none-coalesce", output_type=none_coalesce_output_type)
def none_coalesce(lhs: typing.Any, rhs: typing.Any):
    # TODO: This logic is really complicated in Weave0.
    if isinstance(lhs, list) and isinstance(rhs, list):
        return [l or r for l, r in zip(lhs, rhs)]
    return lhs or rhs
