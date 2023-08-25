import typing
from ..api import op, weave_class
from .. import weave_types as types
from .. import dispatch
from .dict import dict_


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


@op(
    output_type=lambda input_type: types.optional(
        types.union(*input_type["results"].property_types.values())
    )
)
def cond(cases: dict[str, bool], results: dict[str, typing.Any]):
    """Return first result.values()[i] for which case.values()[i] is True.

    Can be used where to achieve if/then/else, or SQL CASE-like behavior.

    Arguments are dictionaries, not lists, but keys are ignored entirely.
    This is important for vectorization. Lists are stored row-oriented in arrow,
    but we actually want columns for each case and result. Using dictionaries
    achieve this, since we map them to arrow structs.
    """
    for c, r in zip(cases.values(), results.values()):
        if c:
            return r
    return None


class Case(typing.TypedDict):
    # These are both actually Nodes, but this gets type-checking to pass for now.
    when: bool
    then: typing.Any


def case(cases: list[Case]) -> dispatch.RuntimeOutputNode:
    """Helper for writing cond expressions."""
    sep_cases = {"%s" % i: cases[i]["when"] for i in range(len(cases))}
    sep_results = {"%s" % i: cases[i]["then"] for i in range(len(cases))}
    return cond(dict_(**sep_cases), dict_(**sep_results))
