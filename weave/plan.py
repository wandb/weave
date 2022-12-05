# Walk the graph, attaching information about downstream accesses to each Node
#
# This is very much WIP. Its only used if a runs2 op is in the DAG, which is
# also WIP.

import copy
import typing

from . import graph
from . import forward_graph
from . import errors
from . import registry_mem
from . import compile
from .language_features.tagging import opdef_util


def do_plan(fg: forward_graph.ForwardGraph) -> forward_graph.ForwardGraph:
    to_run: set[forward_graph.ForwardNode] = fg.roots

    while len(to_run):
        running_now = to_run.copy()
        to_run = set()
        for forward_node in running_now:
            plan_node(fg, forward_node)
        for forward_node in running_now:
            for downstream_forward_node in forward_node.input_to:
                ready_to_run = True
                for param_node in downstream_forward_node.node.from_op.inputs.values():
                    if not fg.has_result(param_node):
                        ready_to_run = False
                if ready_to_run:
                    to_run.add(downstream_forward_node)
    return fg


def plan(result_nodes: list[graph.Node]) -> forward_graph.ForwardGraph:
    fg = forward_graph.ForwardGraph(result_nodes)
    do_plan(fg)
    return fg


# Need to upgrade mypy to 960 or great to get this recursive type to work.
# Our pre-commit mypy is pegged to an earlier version. Upgrading it may
# introduce new errors, so not doing it yet.
# TODO: Fix
ColsType = typing.Dict[str, "ColsType"]  # type:ignore


def get_cols(p: forward_graph.ForwardGraph, node: graph.Node) -> ColsType:
    col_recorder = p.get_result(node)  # type: ignore
    return col_recorder.get_all_cols()


class ColRecorder:
    tags: dict
    cols: dict

    def __init__(self, owner: graph.Node, tags: typing.Optional[dict] = None) -> None:
        self.owner = owner
        if tags is None:
            self.tags = {}
        else:
            self.tags = copy.copy(tags)
        self.cols = {}

    def add_col(self, col: str, recorder: "ColRecorder") -> None:
        self.cols[col] = recorder

    def get_all_cols(self) -> ColsType:
        return {k: v.get_all_cols() for k, v in self.cols.items()}


def plan_node(fg: forward_graph.ForwardGraph, fn: forward_graph.ForwardNode) -> None:
    node = fn.node
    if isinstance(node, graph.ConstNode):
        return
    r = _plan_node(fg, node)
    fn.set_result(r)


def _plan_node(fg: forward_graph.ForwardGraph, node: graph.OutputNode) -> ColRecorder:
    op_def = registry_mem.memory_registry.get_op(node.from_op.name)
    arg0 = list(node.from_op.inputs.values())[0]
    arg0_cr = fg.get_result(arg0)
    if (
        node.from_op.name == "root-project"
        or node.from_op.name == "get"
        or node.from_op.name == "getReturnType"
        or node.from_op.name == "op-render_table_runs2"
        or node.from_op.name == "project-runs2"
    ):
        return ColRecorder(node)
    elif opdef_util.op_def_consumes_tags(op_def):
        # TODO: major hack here just to make it work!
        # I had originally hard-coded the project tag here.
        # this is what kicked off that whole slew of dispatch work! Because I want to
        # just handle a get_tag() op instead of parsing the name or something else weird
        # here.
        # So now I default to return ColRecord() just to make things work. Very bad!
        return arg0_cr.tags.get("project", ColRecorder(node))
    elif node.from_op.name.startswith("mapped_") or node.from_op.name.startswith(
        "mapped-"
    ):
        # Doesn't work because inside this function we access
        # a field... we need to know about that...
        # One fix is to expand the mapped function here...
        return arg0_cr
    elif (
        node.from_op.name.endswith("index")
        or node.from_op.name.endswith("__getitem__")
        or node.from_op.name.endswith("createIndexCheckpointTag")
        or node.from_op.name.endswith("limit")
        or node.from_op.name.endswith("offset")
    ):
        return arg0_cr
    elif node.from_op.name.endswith("filter"):
        filter_fn = list(node.from_op.inputs.values())[1].val
        filter_fn = compile.compile([filter_fn])[0]
        sub_plan = forward_graph.ForwardGraph([filter_fn], allow_var_nodes=True)
        var_nodes = typing.cast(
            list[graph.VarNode],
            graph.filter_nodes(
                filter_fn, lambda n: isinstance(n, graph.VarNode) and n.name == "row"
            ),
        )
        if not var_nodes:
            raise errors.WeaveInternalError('No var node called "row" found')
        # TODO: we're not performing index(n)
        for var_node in var_nodes:
            sub_plan.get_forward_node(var_node).set_result(arg0_cr)
        do_plan(sub_plan)
        return arg0_cr
    elif node.from_op.name.endswith("groupby"):
        filter_fn = list(node.from_op.inputs.values())[1].val
        filter_fn = compile.compile([filter_fn])[0]
        sub_plan = forward_graph.ForwardGraph([filter_fn], allow_var_nodes=True)
        var_nodes = typing.cast(
            list[graph.VarNode],
            graph.filter_nodes(
                filter_fn, lambda n: isinstance(n, graph.VarNode) and n.name == "row"
            ),
        )
        if not var_nodes:
            raise errors.WeaveInternalError('No var node called "row" found')
        # TODO: we're not performing index(n)
        for var_node in var_nodes:
            sub_plan.get_forward_node(var_node).set_result(arg0_cr)
        do_plan(sub_plan)
        return arg0_cr
    elif node.from_op.name.endswith("pick"):
        key = node.from_op.inputs["key"].val
        col_cr = arg0_cr.cols.get(key, None)
        if col_cr is None:
            col_cr = ColRecorder(node)
        arg0_cr.add_col(node.from_op.inputs["key"].val, col_cr)
        return col_cr
    if opdef_util.should_tag_op_def_outputs(op_def):
        # TODO: generilize.
        r = ColRecorder(node, {"project": arg0_cr})
        pass
    elif opdef_util.should_flow_tags(op_def):
        r = ColRecorder(node, arg0_cr.tags)
    else:
        r = ColRecorder(node)
    arg0_cr.add_col(node.from_op.name, r)
    return r
