"""These are the top-level functions in the `import weave` namespace.
"""

import time
import typing
from typing import Optional
import os
import contextlib
import dataclasses
from typing import Any
import threading

from . import urls

from weave.legacy import graph as _graph
from weave.legacy.graph import Node

# If this is not imported, serialization of Weave Nodes is incorrect!
from weave.legacy import graph_mapper as _graph_mapper

from . import storage as _storage
from . import ref_base as _ref_base
from weave.legacy import artifact_wandb as _artifact_wandb
from weave.legacy import wandb_api as _wandb_api

from . import weave_internal as _weave_internal
from . import errors as _errors

from . import util as _util

from weave.legacy import context as _context
from weave.legacy import context_state as _context_state
from weave.legacy import run as _run
from . import weave_init as _weave_init
from . import weave_client as _weave_client
from weave import client_context
from weave.call_context import get_current_call as get_current_call
from weave.trace import context as trace_context
from .trace.constants import TRACE_OBJECT_EMOJI
from weave.trace.refs import ObjectRef

# exposed as part of api
from . import weave_types as types

# needed to enable automatic numpy serialization
from . import types_numpy as _types_numpy

from . import errors
from weave.legacy.decorators import weave_class, mutation, type
from weave.trace.op import op

from weave.trace.op import Op
from . import usage_analytics
from weave.legacy.context import (
    use_fixed_server_port,
    use_frontend_devmode,
    # eager_execution,
    use_lazy_execution,
)

from weave.legacy.panel import Panel

from weave.legacy.arrow.list_ import ArrowWeaveList as WeaveList
from .table import Table


def save(node_or_obj, name=None):
    from weave.legacy.ops_primitives.weave_api import save, get

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


def get(ref_str):
    obj = _storage.get(ref_str)
    ref = typing.cast(_ref_base.Ref, _storage._get_ref(obj))
    return _weave_internal.make_const_node(ref.type, obj)


def use(nodes, client=None):
    usage_analytics.use_called()
    if client is None:
        client = _context.get_client()
    return _weave_internal.use(nodes, client)


def _get_ref(obj):
    if isinstance(obj, _storage.Ref):
        return obj
    ref = _storage.get_ref(obj)
    if ref is None:
        raise _errors.WeaveApiError("obj is not a weave object: %s" % obj)
    return ref


def versions(obj):
    if isinstance(obj, _graph.ConstNode):
        obj = obj.val
    elif isinstance(obj, _graph.OutputNode):
        obj = use(obj)
    ref = _get_ref(obj)
    return ref.versions()  # type: ignore


def expr(obj):
    ref = _get_ref(obj)
    return _trace.get_obj_expr(ref)


def type_of(obj: typing.Any) -> types.Type:
    return types.TypeRegistry.type_of(obj)


# def weave(obj: typing.Any) -> RuntimeConstNode:
#     return _weave_internal.make_const_node(type_of(obj), obj)  # type: ignore


def from_pandas(df):
    return _ops.pandas_to_awl(df)


#### Newer API below


def init(project_name: str) -> _weave_client.WeaveClient:
    """Initialize weave tracking, logging to a wandb project.

    Logging is initialized globally, so you do not need to keep a reference
    to the return value of init.

    Following init, calls of weave.op() decorated functions will be logged
    to the specified project.

    Args:
        project_name: The name of the Weights & Biases project to log to.

    Returns:
        A Weave client.
    """
    # This is the stream-table backend. Disabling it in favor of the new
    # trace-server backend.
    # return _weave_init.init_wandb(project_name).client
    # return _weave_init.init_trace_remote(project_name).client
    return _weave_init.init_weave(project_name).client


@contextlib.contextmanager
def remote_client(
    project_name,
) -> typing.Iterator[_weave_init.weave_client.WeaveClient]:
    inited_client = _weave_init.init_weave(project_name)
    try:
        yield inited_client.client
    finally:
        inited_client.reset()


# This is currently an internal interface. We'll expose something like it though ("offline" mode)
def init_local_client() -> _weave_client.WeaveClient:
    return _weave_init.init_local().client


@contextlib.contextmanager
def local_client() -> typing.Iterator[_weave_client.WeaveClient]:
    inited_client = _weave_init.init_local()
    try:
        yield inited_client.client
    finally:
        inited_client.reset()


def publish(obj: typing.Any, name: Optional[str] = None) -> _weave_client.ObjectRef:
    """Save and version a python object.

    If an object with name already exists, and the content hash of obj does
    not match the latest version of that object, a new version will be created.

    TODO: Need to document how name works with this change.

    Args:
        obj: The object to save and version.
        name: The name to save the object under.

    Returns:
        A weave Ref to the saved object.
    """
    client = client_context.weave_client.require_weave_client()

    save_name: str
    if name:
        save_name = name
    elif hasattr(obj, "name"):
        save_name = obj.name
    else:
        save_name = obj.__class__.__name__

    ref = client._save_object(obj, save_name, "latest")

    if isinstance(ref, _weave_client.ObjectRef):
        url = urls.object_version_path(
            ref.entity,
            ref.project,
            ref.name,
            ref.digest,
        )
        print(f"{TRACE_OBJECT_EMOJI} Published to {url}")

    return ref


def ref(location: str) -> _weave_client.ObjectRef:
    """Construct a Ref to a Weave object.

    TODO: what happens if obj does not exist

    Args:
        location: A fully-qualified weave ref URI, or if weave.init() has been called, "name:version" or just "name" ("latest" will be used for version in this case).


    Returns:
        A weave Ref to the object.
    """
    if not "://" in location:
        client = client_context.weave_client.get_weave_client()
        if not client:
            raise ValueError("Call weave.init() first, or pass a fully qualified uri")
        if "/" in location:
            raise ValueError("'/' not currently supported in short-form URI")
        if ":" not in location:
            name = location
            version = "latest"
        else:
            name, version = location.split(":")
        location = str(client._ref_uri(name, version, "obj"))

    uri = _weave_client.parse_uri(location)
    if not isinstance(uri, _weave_client.ObjectRef):
        raise ValueError("Expected an object ref")
    return uri


def obj_ref(obj: typing.Any) -> typing.Optional[_weave_client.ObjectRef]:
    return _weave_client.get_ref(obj)


def output_of(obj: typing.Any) -> typing.Optional[_weave_client.Call]:
    client = client_context.weave_client.require_weave_client()

    ref = obj_ref(obj)
    if ref is None:
        return ref

    return client._ref_output_of(ref)


def as_op(fn: typing.Callable) -> Op:
    """Given a @weave.op() decorated function, return its Op.

    @weave.op() decorated functions are instances of Op already, so this
    function should be a no-op at runtime. But you can use it to satisfy type checkers
    if you need to access OpDef attributes in a typesafe way.

    Args:
        fn: A weave.op() decorated function.

    Returns:
        The Op of the function.
    """
    if not isinstance(fn, Op):
        raise ValueError("fn must be a weave.op() decorated function")
    return fn


import contextlib


@contextlib.contextmanager
def attributes(attributes: typing.Dict[str, typing.Any]) -> typing.Iterator:
    cur_attributes = {**trace_context.call_attributes.get()}
    cur_attributes.update(attributes)

    token = trace_context.call_attributes.set(cur_attributes)
    try:
        yield
    finally:
        trace_context.call_attributes.reset(token)


def serve(
    model_ref: ObjectRef,
    method_name: typing.Optional[str] = None,
    auth_entity: typing.Optional[str] = None,
    port: int = 9996,
    thread: bool = False,
) -> str:
    import uvicorn
    from .serve_fastapi import object_method_app

    client = client_context.weave_client.require_weave_client()
    # if not isinstance(
    #     client, _graph_client_wandb_art_st.GraphClientWandbArtStreamTable
    # ):
    #     raise ValueError("serve currently only supports wandb client")

    print(f"Serving {model_ref}")
    print(f"🥐 Server docs and playground at http://localhost:{port}/docs")
    print()
    os.environ["PROJECT_NAME"] = f"{client.entity}/{client.project}"
    os.environ["MODEL_REF"] = str(model_ref)

    wandb_api_ctx = _wandb_api.get_wandb_api_context()
    app = object_method_app(model_ref, method_name=method_name, auth_entity=auth_entity)
    trace_attrs = trace_context.call_attributes.get()

    def run():
        # This function doesn't return, because uvicorn.run does not
        # return.
        with _wandb_api.wandb_api_context(wandb_api_ctx):
            with attributes(trace_attrs):
                uvicorn.run(app, host="0.0.0.0", port=port)

    if _util.is_notebook():
        thread = True
    if thread:

        t = threading.Thread(target=run, daemon=True)
        t.start()
        time.sleep(1)
        return "http://localhost:%d" % port
    else:
        # Run should never return
        run()
    raise ValueError("Should not reach here")


def finish() -> None:
    """Stops logging to weave.

    Following finish, calls of weave.op() decorated functions will no longer be logged. You will need to run weave.init() again to resume logging.

    """
    _weave_init.finish()


__docspec__ = [
    init,
    publish,
    ref,
    get_current_call,
    finish,
]
