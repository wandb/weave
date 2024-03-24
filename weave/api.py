"""These are the top-level functions in the `import weave` namespace.
"""

import time
import typing
from typing import Optional
import os
import contextlib
import dataclasses
from typing import Any

from . import urls


# from . import util as _util

from . import weave_init as _weave_init
from . import weave_client as _weave_client
from . import graph_client_context as _graph_client_context

# from weave.monitoring import monitor as _monitor


from weave.trace.op import op, Op


from .table import Table


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
    client = _graph_client_context.require_graph_client()

    save_name: str
    if name:
        save_name = name
    elif hasattr(obj, "name"):
        save_name = obj.name
    else:
        save_name = obj.__class__.__name__

    ref = client.save_object(obj, save_name, "latest")

    # print(f"Published {ref.type.root_type_class().name} to {ref.ui_url}")
    # print(f"Published to {ref.ui_url}")
    print("Published")

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
        client = _graph_client_context.get_graph_client()
        if not client:
            raise ValueError("Call weave.init() first, or pass a fully qualified uri")
        if "/" in location:
            raise ValueError("'/' not currently supported in short-form URI")
        if ":" not in location:
            name = location
            version = "latest"
        else:
            name, version = location.split(":")
        location = str(client.ref_uri(name, version, "obj"))

    uri = _weave_client.parse_uri(location)
    if not isinstance(uri, _weave_client.ObjectRef):
        raise ValueError("Expected an object ref")
    return uri


def obj_ref(obj: typing.Any) -> typing.Optional[_weave_client.ObjectRef]:
    return _weave_client.get_ref(obj)


def output_of(obj: typing.Any) -> typing.Optional[_weave_client.Call]:
    client = _graph_client_context.require_graph_client()

    ref = obj_ref(obj)
    if ref is None:
        return ref

    return client.ref_output_of(ref)


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
    cur_attributes = {**_monitor._attributes.get()}
    cur_attributes.update(attributes)

    token = _monitor._attributes.set(cur_attributes)
    try:
        yield
    finally:
        _monitor._attributes.reset(token)


# def serve(
#     model_ref: _artifact_wandb.WandbArtifactRef,
#     method_name: typing.Optional[str] = None,
#     auth_entity: typing.Optional[str] = None,
#     port: int = 9996,
#     thread: bool = False,
# ) -> typing.Optional[str]:
#     import uvicorn
#     from .serve_fastapi import object_method_app

#     client = _graph_client_context.require_graph_client()
#     # if not isinstance(
#     #     client, _graph_client_wandb_art_st.GraphClientWandbArtStreamTable
#     # ):
#     #     raise ValueError("serve currently only supports wandb client")

#     print(f"Serving {model_ref}")
#     print(f"🥐 Server docs and playground at http://localhost:{port}/docs")
#     print()
#     os.environ["PROJECT_NAME"] = f"{client.entity}/{client.project}"
#     os.environ["MODEL_REF"] = str(model_ref)

#     wandb_api_ctx = _wandb_api.get_wandb_api_context()
#     app = object_method_app(model_ref, method_name=method_name, auth_entity=auth_entity)
#     trace_attrs = _monitor._attributes.get()

#     def run():
#         with _wandb_api.wandb_api_context(wandb_api_ctx):
#             with attributes(trace_attrs):
#                 uvicorn.run(app, host="0.0.0.0", port=port)

#     if _util.is_notebook():
#         thread = True
#     if thread:
#         from threading import Thread

#         t = Thread(target=run, daemon=True)
#         t.start()
#         time.sleep(1)
#         return "http://localhost:%d" % port
#     else:
#         run()
#     return None


__docspec__ = [init, publish, ref]
