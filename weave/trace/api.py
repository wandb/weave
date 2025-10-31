"""The top-level functions for Weave Trace API."""

from __future__ import annotations

import contextlib
import logging
import sys
import warnings
from collections.abc import Iterator
from typing import Any, Union, cast, overload

from typing_extensions import TypedDict, Unpack

# TODO: type_handlers is imported here to trigger registration of the image serializer.
# There is probably a better place for this, but including here for now to get the fix in.
from weave import type_handlers  # noqa: F401
from weave.trace import urls, weave_client, weave_init
from weave.trace.autopatch import AutopatchSettings
from weave.trace.constants import TRACE_OBJECT_EMOJI
from weave.trace.context import call_context
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.context.call_context import get_current_call, require_current_call
from weave.trace.display.term import configure_logger
from weave.trace.op import PostprocessInputsFunc, PostprocessOutputFunc, as_op, op
from weave.trace.refs import ObjectRef, Ref
from weave.trace.settings import (
    UserSettings,
    parse_and_apply_settings,
    should_disable_weave,
)
from weave.trace.table import Table
from weave.trace.view_utils import set_call_view
from weave.trace_server.ids import generate_id
from weave.trace_server.interface.builtin_object_classes import leaderboard
from weave.type_wrappers.Content.content import Content

logger = logging.getLogger(__name__)

# Sentinel object to distinguish between "not provided" (auto-generate) and explicit None (disable)
_AUTO_GENERATE = object()

_global_postprocess_inputs: PostprocessInputsFunc | None = None
_global_postprocess_output: PostprocessOutputFunc | None = None
_global_attributes: dict[str, Any] = {}


class _InitKwargs(TypedDict, total=False):
    """Common keyword arguments for weave.init()."""

    settings: UserSettings | dict[str, Any] | None
    autopatch_settings: AutopatchSettings | None
    global_postprocess_inputs: PostprocessInputsFunc | None
    global_postprocess_output: PostprocessOutputFunc | None
    global_attributes: dict[str, Any] | None


@overload
def init(
    project_name: str,
    /,
    **kwargs: Unpack[_InitKwargs],
) -> weave_client.WeaveClient: ...


@overload
def init(
    *,
    entity: str,
    project: str,
    **kwargs: Unpack[_InitKwargs],
) -> weave_client.WeaveClient: ...


def init(
    project_name: str | None = None,
    *,
    entity: str | None = None,
    project: str | None = None,
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
        project_name: The name of the Weights & Biases team and project to log to. If you don't
            specify a team, your default entity is used.
            To find or update your default entity, refer to [User Settings](https://docs.wandb.ai/guides/models/app/settings-page/user-settings/#default-team) in the W&B Models documentation.
            Can be either "<project_name>" or "<entity_name>/<project_name>".
            Mutually exclusive with entity and project parameters.
        entity: The Weights & Biases entity (team) name. Mutually exclusive with project_name.
            Must be provided together with project parameter.
        project: The Weights & Biases project name. Mutually exclusive with project_name.
            Must be provided together with entity parameter.
        settings: Configuration for the Weave client generally.
        autopatch_settings: (Deprecated) Configuration for autopatch integrations. Use explicit patching instead.
        global_postprocess_inputs: A function that will be applied to all inputs of all ops.
        global_postprocess_output: A function that will be applied to all outputs of all ops.
        global_attributes: A dictionary of attributes that will be applied to all traces.

    NOTE: Global postprocessing settings are applied to all ops after each op's own
    postprocessing.  The order is always:
    1. Op-specific postprocessing
    2. Global postprocessing

    Returns:
        A Weave client.

    Examples:
        >>> import weave
        >>> # Using project_name string format (backward compatible)
        >>> weave.init("wandb/weave")
        >>> # Using entity and project parameters (wandb.init style)
        >>> weave.init(entity="wandb", project="weave")
    """
    # Validate that exactly one of the two parameter styles is provided
    has_project_name = project_name is not None and project_name.strip()
    has_entity_project = entity is not None or project is not None

    if has_project_name and has_entity_project:
        raise ValueError(
            "Cannot specify both 'project_name' and 'entity'/'project' parameters. "
            "Use either project_name='entity/project' or entity='entity', project='project'."
        )

    if not has_project_name and not has_entity_project:
        raise ValueError(
            "Must provide either 'project_name' or both 'entity' and 'project' parameters."
        )

    if has_entity_project:
        if entity is None or project is None:
            raise ValueError(
                "Both 'entity' and 'project' must be provided when using entity/project style."
            )
        if not entity.strip() or not project.strip():
            raise ValueError("entity and project must be non-empty strings")
        # Construct project_name from entity and project
        project_name = f"{entity}/{project}"

    # At this point, project_name is guaranteed to be a non-empty string
    # (either from the parameter or constructed from entity/project)
    project_name = cast(str, project_name)

    configure_logger()

    if sys.version_info < (3, 10):
        warnings.warn(
            "Python 3.9 will reach end of life in October 2025, after which weave will drop support for it.  Please upgrade to Python 3.10 or later!",
            DeprecationWarning,
            stacklevel=2,
        )

    # Check if deprecated autopatch_settings is used
    if autopatch_settings is not None:
        logger.warning(
            "The 'autopatch_settings' parameter is deprecated and will be removed in a future version. "
            "Please use explicit patching instead. For example:\n"
            "----------------------------------------\n"
            "    import weave\n"
            f"    weave.init('{project_name}')\n"
            "    weave.integrations.patch_openai()\n"
            "----------------------------------------\n"
            "See https://docs.wandb.ai/guides/integrations for more information.",
        )

    parse_and_apply_settings(settings)

    global _global_postprocess_inputs
    global _global_postprocess_output
    global _global_attributes

    _global_postprocess_inputs = global_postprocess_inputs
    _global_postprocess_output = global_postprocess_output
    _global_attributes = global_attributes or {}

    if should_disable_weave():
        return weave_init.init_weave_disabled()

    return weave_init.init_weave(project_name)


def get_client() -> weave_client.WeaveClient | None:
    return weave_client_context.get_weave_client()


def publish(obj: Any, name: str | None = None) -> ObjectRef:
    """Save and version a Python object.

    Weave creates a new version of the object if the object's name already exists and its content hash does
    not match the latest version of that object.

    Args:
        obj: The object to save and version.
        name: The name to save the object under.

    Returns:
        A Weave Ref to the saved object.
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
        logger.info(f"{TRACE_OBJECT_EMOJI} Published to {url}")
    return ref


def ref(location: str) -> ObjectRef:
    """Creates a Ref to an existing Weave object. This does not directly retrieve
    the object but allows you to pass it to other Weave API functions.

    Args:
        location: A Weave Ref URI, or if `weave.init()` has been called, `name:version` or `name`. If no version is provided, `latest` is used.

    Returns:
        A Weave Ref to the object.
    """
    if "://" not in location:
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

    ref = Ref.parse_uri(location)
    if not isinstance(ref, ObjectRef):
        raise TypeError("Expected an object ref")
    return ref


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


@contextlib.contextmanager
def attributes(attributes: dict[str, Any]) -> Iterator:
    """Context manager for setting attributes on a call.

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


def set_view(
    name: str,
    content: Content | str,
    *,
    extension: str | None = None,
    mimetype: str | None = None,
    metadata: dict[str, Any] | None = None,
    encoding: str = "utf-8",
) -> None:
    """Attach a custom view to the current call summary at `_weave.views.<name>`.

    Args:
        name: The view name (key under `summary._weave.views`).
        content: A `weave.Content` instance or raw string. Strings are wrapped via
            `Content.from_text` using the supplied extension or mimetype.
        extension: Optional file extension to use when `content` is a string.
        mimetype: Optional MIME type to use when `content` is a string.
        metadata: Optional metadata to attach when creating `Content` from text.
        encoding: Text encoding to apply when creating `Content` from text.

    Returns:
        None

    Examples:
        >>> import weave
        >>> weave.init("proj")
        >>> @weave.op
        ... def foo():
        ...     weave.set_view("readme", "# Hello", extension="md")
        ...     return 1
        >>> foo()
    """
    if isinstance(content, str) and len(content) == 0:
        raise ValueError("Content cannot be an empty string")

    if not isinstance(name, str) or len(name) == 0:
        raise ValueError("`name` must be a non-empty string")

    call = require_current_call()
    client = weave_client_context.require_weave_client()

    set_call_view(
        call=call,
        client=client,
        name=name,
        content=content,
        extension=extension,
        mimetype=mimetype,
        metadata=metadata,
        encoding=encoding,
    )


class ThreadContext:
    """Context object providing access to current thread and turn information."""

    def __init__(self, thread_id: str | None):
        """Initialize ThreadContext with the specified thread_id.

        Args:
            thread_id: The thread identifier for this context, or None if disabled.
        """
        self._thread_id = thread_id

    @property
    def thread_id(self) -> str | None:
        """Get the thread_id for this context.

        Returns:
            The thread identifier, or None if thread tracking is disabled.
        """
        return self._thread_id

    @property
    def turn_id(self) -> str | None:
        """Get the current turn_id from the active context.

        Returns:
            The current turn_id if set, None otherwise.
        """
        return call_context.get_turn_id()


@contextlib.contextmanager
def thread(thread_id: str | None | object = _AUTO_GENERATE) -> Iterator[ThreadContext]:
    """Context manager for setting thread_id on calls within the context.

    Examples:
    ```python
    # Auto-generate thread_id
    with weave.thread() as t:
        print(f"Thread ID: {t.thread_id}")
        result = my_function("input")  # This call will have the auto-generated thread_id
        print(f"Current turn: {t.turn_id}")

    # Explicit thread_id
    with weave.thread("custom_thread") as t:
        result = my_function("input")  # This call will have thread_id="custom_thread"

    # Disable threading
    with weave.thread(None) as t:
        result = my_function("input")  # This call will have thread_id=None
    ```

    Args:
        thread_id: The thread identifier to associate with calls in this context.
                  If not provided, a UUID v7 will be auto-generated.
                  If None, thread tracking will be disabled.

    Yields:
        ThreadContext: An object providing access to thread_id and current turn_id.
    """
    # Determine actual thread_id to use
    actual_thread_id: str | None
    if thread_id is _AUTO_GENERATE:
        # No argument provided - auto-generate
        actual_thread_id = generate_id()
    else:
        # Explicit thread_id (string or None)
        actual_thread_id = cast(Union[str, None], thread_id)

    # Create context object
    context = ThreadContext(actual_thread_id)

    with call_context.set_thread_id(actual_thread_id):
        # Reset turn lineage when entering new thread context
        call_context.set_turn_id(None)
        yield context


def finish() -> None:
    """Stops logging to weave.

    Following finish, calls of weave.op() decorated functions will no longer be logged. You will need to run weave.init() again to resume logging.

    """
    weave_init.finish()

    # Flush any remaining calls
    if wc := weave_client_context.get_weave_client():
        wc.finish()


# As of this writing, most important symbols are
# re-exported in __init__.py.
# __docspec__ = []


__all__ = [
    "ObjectRef",
    "Table",
    "ThreadContext",
    "as_op",
    "attributes",
    "finish",
    "get",
    "get_client",
    "get_current_call",
    "init",
    "op",
    "publish",
    "ref",
    "require_current_call",
    "set_view",
    "thread",
    "weave_client_context",
]
