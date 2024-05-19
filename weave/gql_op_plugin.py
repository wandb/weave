import typing
from dataclasses import dataclass

from . import input_provider
from . import op_args
from . import op_def
from . import input_provider
from . import weave_types as types

# A GQLOutputTypeFn is a function that is called during the refinement phase of the compile pass
# to propagate the GQL keys of a node's input types to its output type.
GQLOutputTypeFn = typing.Callable[
    [input_provider.InputProvider, types.Type], types.Type
]


_ROOT_RESOLVERS: set[op_def.OpDef] = set()


@dataclass
class GqlOpPlugin:
    query_fn: typing.Callable[[input_provider.InputAndStitchProvider, str], str]
    is_root: bool = False
    root_resolver: typing.Optional["op_def.OpDef"] = None

    # given the input types to the op, return a new output type with the input types'
    # gql keys propagated appropriately. this is not a part of output_type to avoid
    # the UI needing to make additional network requests to get the output type
    gql_op_output_type: typing.Optional[GQLOutputTypeFn] = None

    def __post_init__(self) -> None:
        if self.root_resolver is not None:
            _ROOT_RESOLVERS.add(self.root_resolver)


# Ops in `domain_ops` can add this plugin to their op definition to indicate
# that they need data to be fetched from the GQL API. At it's core, the plugin
# allows the user to specify a `query_fn` that takes in the inputs to the op and
# returns a GQL query fragment that is needed by the calling op. The plugin also
# allows the user to specify whether the op is a root op which indicates it is
# the "top" of the GQL query tree. Note, while ops can use this directly (eg.
# see `project_ops.py::artifacts`), most ops use the higher level helpers
# defined in `wb_domain_gql.py`
def wb_gql_op_plugin(
    query_fn: typing.Callable[[input_provider.InputAndStitchProvider, str], str],
    is_root: bool = False,
    root_resolver: typing.Optional["op_def.OpDef"] = None,
    gql_op_output_type: typing.Optional[GQLOutputTypeFn] = None,
) -> dict[str, GqlOpPlugin]:
    return {
        "wb_domain_gql": GqlOpPlugin(
            query_fn, is_root, root_resolver, gql_op_output_type
        )
    }


def get_gql_plugin(
    op_def: "op_def.OpDef",
) -> typing.Optional[GqlOpPlugin]:
    if op_def.plugins is not None and "wb_domain_gql" in op_def.plugins:
        return op_def.plugins["wb_domain_gql"]
    return None


def first_arg_name(
    opdef: "op_def.OpDef",
) -> typing.Optional[str]:
    if not isinstance(opdef.input_type, op_args.OpNamedArgs):
        return None
    try:
        return next(iter(opdef.input_type.arg_types.keys()))
    except StopIteration:
        return None
