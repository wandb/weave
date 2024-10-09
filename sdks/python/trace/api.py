"""The top-level functions for Weave Trace API."""

import contextlib
import os
import threading
import time
from typing import Any, Iterator, Optional, Union

# TODO: type_serializers is imported here to trigger registration of the image serializer.
# There is probably a better place for this, but including here for now to get the fix in.
from weave import type_serializers  # noqa: F401
from weave.trace import context, urls, util, weave_client, weave_init
from weave.trace.call_context import get_current_call, require_current_call
from weave.trace.client_context import weave_client as weave_client_context
from weave.trace.constants import TRACE_OBJECT_EMOJI
from weave.trace.op import as_op, op
from weave.trace.refs import ObjectRef, parse_uri
from weave.trace.settings import (
    UserSettings,
    parse_and_apply_settings,
    should_disable_weave,
)
from weave.trace.table import Table


def init(
    project_name: str,
    *,
    settings: Optional[Union[UserSettings, dict[str, Any]]] = None,
) -> weave_client.WeaveClient:
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
    parse_and_apply_settings(settings)

    if should_disable_weave():
        return weave_init.init_weave_disabled().client

    return weave_init.init_weave(project_name).client


@contextlib.contextmanager
def remote_client(project_name: str) -> Iterator[weave_init.weave_client.WeaveClient]:
    inited_client = weave_init.init_weave(project_name)
    try:
        yield inited_client.client
    finally:
        inited_client.reset()


# This is currently an internal interface. We'll expose something like it though ("offline" mode)
def init_local_client() -> weave_client.WeaveClient:
    return weave_init.init_local().client


@contextlib.contextmanager
def local_client() -> Iterator[weave_client.WeaveClient]:
    inited_client = weave_init.init_local()
    try:
        yield inited_client.client
    finally:
        inited_client.reset()


def publish(obj: Any, name: Optional[str] = None) -> weave_client.ObjectRef:
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
    client = weave_client_context.require_weave_client()

    save_name: str
    if name:
        save_name = name
    elif n := getattr(obj, "name", None):
        save_name = n
    else:
        save_name = obj.__class__.__name__

    ref = client._save_object(obj, save_name, "latest")

    if isinstance(ref, weave_client.ObjectRef):
        if isinstance(ref, weave_client.OpRef):
            url = urls.op_version_path(
                ref.entity,
                ref.project,
                ref.name,
                ref.digest,
            )
        # TODO(gst): once frontend has direct dataset/model links
        # elif isinstance(obj, weave_client.Dataset):
        else:
            url = urls.object_version_path(
                ref.entity,
                ref.project,
                ref.name,
                ref.digest,
            )
        print(f"{TRACE_OBJECT_EMOJI} Published to {url}")
    return ref


def ref(location: str) -> weave_client.ObjectRef:
    """Construct a Ref to a Weave object.

    TODO: what happens if obj does not exist

    Args:
        location: A fully-qualified weave ref URI, or if weave.init() has been called, "name:version" or just "name" ("latest" will be used for version in this case).


    Returns:
        A weave Ref to the object.
    """
    if not "://" in location:
        client = weave_client_context.get_weave_client()
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

    uri = parse_uri(location)
    if not isinstance(uri, weave_client.ObjectRef):
        raise ValueError("Expected an object ref")
    return uri


def obj_ref(obj: Any) -> Optional[weave_client.ObjectRef]:
    return weave_client.get_ref(obj)


def output_of(obj: Any) -> Optional[weave_client.Call]:
    client = weave_client_context.require_weave_client()

    ref = obj_ref(obj)
    if ref is None:
        return ref

    return client._ref_output_of(ref)


@contextlib.contextmanager
def attributes(attributes: dict[str, Any]) -> Iterator:
    """
    Context manager for setting attributes on a call.

    Example:

    ```python
    with weave.attributes({'env': 'production'}):
        print(my_function.call("World"))
    ```
    """
    cur_attributes = {**context.call_attributes.get()}
    cur_attributes.update(attributes)

    token = context.call_attributes.set(cur_attributes)
    try:
        yield
    finally:
        context.call_attributes.reset(token)


def serve(
    model_ref: ObjectRef,
    method_name: Optional[str] = None,
    auth_entity: Optional[str] = None,
    port: int = 9996,
    thread: bool = False,
) -> str:
    import uvicorn

    from weave.trace.serve_fastapi import object_method_app
    from weave.wandb_interface import wandb_api

    client = weave_client_context.require_weave_client()
    # if not isinstance(
    #     client, _graph_client_wandb_art_st.GraphClientWandbArtStreamTable
    # ):
    #     raise ValueError("serve currently only supports wandb client")

    print(f"Serving {model_ref}")
    print(f"🥐 Server docs and playground at http://localhost:{port}/docs")
    print()
    os.environ["PROJECT_NAME"] = f"{client.entity}/{client.project}"
    os.environ["MODEL_REF"] = str(model_ref)

    wandb_api_ctx = wandb_api.get_wandb_api_context()
    app = object_method_app(model_ref, method_name=method_name, auth_entity=auth_entity)
    trace_attrs = context.call_attributes.get()

    def run() -> None:
        # This function doesn't return, because uvicorn.run does not return.
        with wandb_api.wandb_api_context(wandb_api_ctx):
            with attributes(trace_attrs):
                uvicorn.run(app, host="0.0.0.0", port=port)

    if util.is_notebook():
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
    weave_init.finish()


# As of this writing, most important symbols are
# re-exported in __init__.py.
# __docspec__ = []


__all__ = [
    "init",
    "remote_client",
    "local_client",
    "init_local_client",
    "as_op",
    "publish",
    "ref",
    "obj_ref",
    "output_of",
    "attributes",
    "serve",
    "finish",
    "op",
    "Table",
    "ObjectRef",
    "parse_uri",
    "get_current_call",
    "weave_client_context",
    "require_current_call",
]
