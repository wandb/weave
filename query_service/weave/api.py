"""The top-level functions for Weave Query API."""

import typing

from weave.legacy.weave import graph as _graph
from weave.legacy.weave.graph import Node

# If this is not imported, serialization of Weave Nodes is incorrect!
from weave.legacy.weave import graph_mapper as _graph_mapper

from . import storage as _storage
from . import ref_base as _ref_base
from weave.legacy.weave import wandb_api as _wandb_api

from weave.legacy.weave import weave_internal as _weave_internal

from weave.legacy.weave import util as _util

from weave.legacy.weave import context as _context
from ...trace import weave_init as _weave_init
from ...trace import weave_client as _weave_client

# exposed as part of api
from weave.legacy.weave import weave_types as types

# needed to enable automatic numpy serialization
from . import types_numpy as _types_numpy

from weave.legacy.weave import errors
from weave.legacy.weave.decorators import weave_class, mutation, type

from weave.legacy.weave import usage_analytics
from weave.legacy.weave.context import (
    use_fixed_server_port,
    use_frontend_devmode,
    # eager_execution,
    use_lazy_execution,
)

from weave.legacy.weave.panel import Panel

from weave.legacy.weave.arrow.list_ import ArrowWeaveList as WeaveList

# TODO: This is here because the op overloaded...
from weave.trace.op import op  # noqa: F401

def save(node_or_obj, name=None):  # type: ignore
    from weave.legacy.weave.ops_primitives.weave_api import get, save

    if isinstance(node_or_obj, _graph.Node):
        return save(node_or_obj, name=name)
    else:
        # If the user does not provide a branch, then we explicitly set it to
        # the default branch, "latest".
        branch = None
        name_contains_branch = name is not None and ":" in name
        if not name_contains_branch:
            branch = "latest"
        ref = _storage.save(node_or_obj, name=name, branch=branch)
        if name is None:
            # if the user didn't provide a name, the returned reference
            # will be to the specific version
            uri = ref.uri
        else:
            # otherwise the reference will be to whatever branch was provided
            # or the "latest" branch if only a name was provided.
            uri = ref.branch_uri
        return get(str(uri))


def get(ref_str):  # type: ignore
    obj = _storage.get(ref_str)
    ref = typing.cast(_ref_base.Ref, _storage._get_ref(obj))
    return _weave_internal.make_const_node(ref.type, obj)


def use(nodes, client=None):  # type: ignore
    usage_analytics.use_called()
    if client is None:
        client = _context.get_client()
    return _weave_internal.use(nodes, client)


def _get_ref(obj):  # type: ignore
    if isinstance(obj, _storage.Ref):
        return obj
    ref = _storage.get_ref(obj)
    if ref is None:
        raise errors.WeaveApiError("obj is not a weave object: %s" % obj)
    return ref


def versions(obj):  # type: ignore
    if isinstance(obj, _graph.ConstNode):
        obj = obj.val
    elif isinstance(obj, _graph.OutputNode):
        obj = use(obj)
    ref = _get_ref(obj)
    return ref.versions()  # type: ignore


def expr(obj):  # type: ignore
    ref = _get_ref(obj)
    return _trace.get_obj_expr(ref)


def type_of(obj: typing.Any) -> types.Type:  # type: ignore
    return types.TypeRegistry.type_of(obj)


# def weave(obj: typing.Any) -> RuntimeConstNode:
#     return _weave_internal.make_const_node(type_of(obj), obj)  # type: ignore


def from_pandas(df):  # type: ignore
    return _ops.pandas_to_awl(df)


__all__ = [
    # These seem to be important imports for query service...
    # TODO: Remove as many as possible...
    "_graph",
    "Node",
    "_graph_mapper",
    "_storage",
    "_ref_base",
    "_wandb_api",
    "_weave_internal",
    "_util",
    "_context",
    "_weave_init",
    "_weave_client",
    "types",
    "_types_numpy",
    "errors",
    "mutation",
    "weave_class",
    "type",
    "usage_analytics",
    "use_fixed_server_port",
    "use_frontend_devmode",
    "use_lazy_execution",
    "Panel",
    "WeaveList",
    # These are the actual functions declared
    "save",
    "get",
    "use",
    "_get_ref",
    "versions",
    "expr",
    "type_of",
    "from_pandas",
]
