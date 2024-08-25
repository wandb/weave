import typing

import weave
from weave.legacy.weave import context_state, weave_internal

_loading_builtins_token = context_state.set_loading_built_ins()

MetricRows = typing.TypeVar("MetricRows")


@weave.type()
class _TestType(typing.Generic[MetricRows]):
    metrics: MetricRows


context_state.clear_loading_built_ins(_loading_builtins_token)


def test_const_type_mapper():
    node = weave_internal.make_const_node(
        _TestType.WeaveType(weave.types.List(weave.types.Number())), None
    )
    fn_node = weave_internal.define_fn(
        {"row": weave.types.Number()}, lambda row: row + 1
    )
    node.metrics.map(fn_node)
