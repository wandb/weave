"""The top-level functions for Weave Trace API."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

# TODO: type_handlers is imported here to trigger registration of the image serializer.
# There is probably a better place for this, but including here for now to get the fix in.
from weave import type_handlers  # noqa: F401
from weave.trace import urls, weave_client, weave_init
from weave.trace.autopatch import AutopatchSettings
from weave.trace.constants import TRACE_OBJECT_EMOJI
from weave.trace.context import call_context
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.context.call_context import get_current_call, require_current_call
from weave.trace.op import PostprocessInputsFunc, PostprocessOutputFunc, as_op, op
from weave.trace.refs import ObjectRef, parse_uri
from weave.trace.settings import (
    UserSettings,
    parse_and_apply_settings,
    should_disable_weave,
)
from weave.trace.table import Table
from weave.trace_server.interface.builtin_object_classes import leaderboard

_global_postprocess_inputs: PostprocessInputsFunc | None = None
_global_postprocess_output: PostprocessOutputFunc | None = None
_global_attributes: dict[str, Any] = {}


def init(
    project_name: str,
    *,
    settings: UserSettings | dict[str, Any] | None = None,
    autopatch_settings: AutopatchSettings | None = None,
    global_postprocess_inputs: PostprocessInputsFunc | None = None,
    global_postprocess_output: PostprocessOutputFunc | None = None,
    global_attributes: dict[str, Any] | None = None,
) -> weave_client.WeaveClient:
    """Initialize weave tracking, logging to a wandb project.

    Logging is initialized globally, so you do not need to keep a reference
    to the return value of init.

    Following init, calls of weave.op() decorated functions will be logged
    to the specified project.

    Args:
        project_name: The name of the Weights & Biases project to log to.
        settings: Configuration for the Weave client generally.
        autopatch_settings: Configuration for autopatch integrations, e.g. openai
        global_postprocess_inputs: A function that will be applied to all inputs of all ops.
        global_postprocess_output: A function that will be applied to all outputs of all ops.
        global_attributes: A dictionary of attributes that will be applied to all traces.

    NOTE: Global postprocessing settings are applied to all ops after each op's own
    postprocessing.  The order is always:
    1. Op-specific postprocessing
    2. Global postprocessing

    Returns:
        A Weave client.
    """
    parse_and_apply_settings(settings)

    global _global_postprocess_inputs
    global _global_postprocess_output
    global _global_attributes

    _global_postprocess_inputs = global_postprocess_inputs
    _global_postprocess_output = global_postprocess_output
    _global_attributes = global_attributes or {}

    if should_disable_weave():
        return weave_init.init_weave_disabled().client

    initialized_client = weave_init.init_weave(
        project_name,
        autopatch_settings=autopatch_settings,
    )

    return initialized_client.client


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


def publish(obj: Any, name: str | None = None) -> ObjectRef:
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

    if isinstance(ref, ObjectRef):
        if isinstance(ref, weave_client.OpRef):
            url = urls.op_version_path(
                ref.entity,
                ref.project,
                ref.name,
                ref.digest,
            )
        elif isinstance(obj, leaderboard.Leaderboard):
            url = urls.leaderboard_path(
                ref.entity,
                ref.project,
                ref.name,
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


def ref(location: str) -> ObjectRef:
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
    if not isinstance(uri, ObjectRef):
        raise TypeError("Expected an object ref")
    return uri


def get(uri: str | ObjectRef) -> Any:
    """A convenience function for getting an object from a URI.

    Many objects logged by Weave are automatically registered with the Weave
    server. This function allows you to retrieve those objects by their URI.

    Args:
        uri: A fully-qualified weave ref URI.

    Returns:
        The object.

    Example:

    ```python
    weave.init("weave_get_example")
    dataset = weave.Dataset(rows=[{"a": 1, "b": 2}])
    ref = weave.publish(dataset)

    dataset2 = weave.get(ref)  # same as dataset!
    ```
    """
    if isinstance(uri, ObjectRef):
        return uri.get()
    return ref(uri).get()


def obj_ref(obj: Any) -> ObjectRef | None:
    return weave_client.get_ref(obj)


def output_of(obj: Any) -> weave_client.Call | None:
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
    cur_attributes = {**call_context.call_attributes.get()}
    cur_attributes.update(attributes)

    token = call_context.call_attributes.set(cur_attributes)
    try:
        yield
    finally:
        call_context.call_attributes.reset(token)


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
    "finish",
    "op",
    "Table",
    "ObjectRef",
    "parse_uri",
    "get_current_call",
    "weave_client_context",
    "require_current_call",
    "get",
]
