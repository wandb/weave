"""The trace server's query models. The classes now live in the client."""

import warnings
from collections.abc import Sequence

# Re-exported, so the old import path keeps working and names the same classes.
from weave.trace.builtin_object_classes.query import (  # noqa: F401
    AndOperation,
    CastTo,
    ContainsOperation,
    ContainsSpec,
    ConvertOperation,
    ConvertSpec,
    EqOperation,
    GetFieldOperator,
    GteOperation,
    GtOperation,
    InOperation,
    LiteralOperation,
    LteOperation,
    LtOperation,
    NotOperation,
    Operand,
    Operation,
    OrOperation,
    Query,
    SizeOperation,
)

# TODO: delete this module together with weave.shared.
warnings.warn(
    "weave.shared.interface.query is deprecated and will be removed in a future "
    "release.",
    FutureWarning,
    stacklevel=2,
)


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
