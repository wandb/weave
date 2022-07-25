from ..api import op


@op(name="boolean-equal")
def bool_equals(lhs: bool, rhs: bool) -> bool:
    return lhs == rhs


@op(name="boolean-notEqual")
def bool_notEquals(lhs: bool, rhs: bool) -> bool:
    return lhs != rhs


@op(name="and")
def bool_and(lhs: bool, rhs: bool) -> bool:
    return lhs and rhs


@op(name="or")
def bool_or(lhs: bool, rhs: bool) -> bool:
    return lhs or rhs


@op(name="boolean-not")
def bool_not(bool: bool) -> bool:
    return not bool
