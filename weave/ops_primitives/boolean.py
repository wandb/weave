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


@op(name="none-coalesce")
def none_coalesce(a: typing.Any, b: typing.Any) -> typing.Any:
    # TODO: This logic is really complicated in Weavae0.
    return a or b
