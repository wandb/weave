import contextlib
import os
import threading
import time
from typing import Any, Callable, Iterator, Optional

from weave import client_context
from weave.call_context import get_current_call as get_current_call
from weave.legacy import wandb_api as _wandb_api
from weave.trace import context as trace_context
from weave.trace.op import Op
from weave.trace.refs import ObjectRef, parse_uri

from . import urls, util, weave_client, weave_init
from .trace.constants import TRACE_OBJECT_EMOJI


def init(project_name: str) -> weave_client.WeaveClient:
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
    # return weave_init.init_wandb(project_name).client
    # return weave_init.init_trace_remote(project_name).client
    return weave_init.init_weave(project_name).client


@contextlib.contextmanager
def remote_client(
    project_name,
) -> Iterator[weave_init.weave_client.WeaveClient]:
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


def as_op(fn: Callable) -> Op:
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
    client = client_context.weave_client.require_weave_client()

    save_name: str
    if name:
        save_name = name
    elif hasattr(obj, "name"):
        save_name = obj.name
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

    uri = parse_uri(location)
    if not isinstance(uri, weave_client.ObjectRef):
        raise ValueError("Expected an object ref")
    return uri


def obj_ref(obj: Any) -> Optional[weave_client.ObjectRef]:
    return weave_client.get_ref(obj)


def output_of(obj: Any) -> Optional[weave_client.Call]:
    client = client_context.weave_client.require_weave_client()

    ref = obj_ref(obj)
    if ref is None:
        return ref

    return client._ref_output_of(ref)


@contextlib.contextmanager
def attributes(attributes: dict[str, Any]) -> Iterator:
    cur_attributes = {**trace_context.call_attributes.get()}
    cur_attributes.update(attributes)

    token = trace_context.call_attributes.set(cur_attributes)
    try:
        yield
    finally:
        trace_context.call_attributes.reset(token)


def serve(
    model_ref: ObjectRef,
    method_name: Optional[str] = None,
    auth_entity: Optional[str] = None,
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
        # This function doesn't return, because uvicorn.run does not return.
        with _wandb_api.wandb_api_context(wandb_api_ctx):
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


__docspec__ = [
    init,
    publish,
    ref,
    get_current_call,
    finish,
]
