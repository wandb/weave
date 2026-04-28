"""The top-level functions for Weave Trace API."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterator
from typing import Any, cast

# TODO: type_handlers is imported here to trigger registration of the image serializer.
# There is probably a better place for this, but including here for now to get the fix in.
from weave import type_handlers  # noqa: F401
from weave.trace import urls, weave_client, weave_init
from weave.trace.autopatch import AutopatchSettings
from weave.trace.constants import TRACE_OBJECT_EMOJI
from weave.trace.context import call_context, weave_client_context
from weave.trace.context.call_context import get_current_call, require_current_call
from weave.trace.display.term import configure_logger, update_logger_level
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


def init(
    project_name: str,
    *,
    settings: UserSettings | dict[str, Any] | None = None,
    autopatch_settings: AutopatchSettings | None = None,
    global_postprocess_inputs: PostprocessInputsFunc | None = None,
    global_postprocess_output: PostprocessOutputFunc | None = None,
    global_attributes: dict[str, Any] | None = None,
) -> weave_client.WeaveClient:
    """Initializes Weave tracing for a Weights & Biases project and returns the active client.

    Call this once, early in your program. After it returns, any function decorated
    with `weave.op` is traced to the specified project, and many supported LLM and
    agent libraries are automatically patched so their calls appear as traces too.
    The client is registered globally, so you don't need to hold on to the return
    value unless you want to use it directly.

    Calling `weave.init` again with the same project is a no-op and returns the
    existing client. Calling it with a different project flushes any pending calls
    on the previous client and replaces it.

    If `project_name` doesn't include a team, Weave resolves your default W&B
    entity. If you're not yet authenticated, Weave runs `wandb login` to prompt
    for an API key.

    Args:
        project_name (str): The Weights & Biases project to log to, as
            `"your-team/your-project"` or `"your-project"`. When the team is
            omitted, Weave uses the `WANDB_ENTITY` environment variable, or
            your default entity from wandb. See
            [User Settings](https://docs.wandb.ai/platform/app/settings-page/user-settings#default-team)
            for how to find or change your default entity.
        settings (UserSettings | dict[str, Any] | None): Configuration for the
            Weave client. Pass a `UserSettings` instance, a dict of field names
            to values, or `None` to use defaults. Any field can also be set via
            an environment variable by uppercasing the name and adding the
            `WEAVE_` prefix (for example, `WEAVE_DISABLED=true`). Environment
            variables take precedence over values passed here. The most commonly
            used fields are:

                - `disabled` (bool): Turns tracing off. All `weave.op` functions
                    run as plain Python and no network calls are made.
                    Default: `False`.
                - `print_call_link` (bool): Prints a link to the Weave UI when
                    a traced op runs. Default: `True`.
                - `log_level` (str): Logger level for the `weave` logger. One of
                    `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Default: `INFO`.
                - `display_viewer` (str): Console renderer for Weave output. One
                    of `auto`, `rich`, `print`. Default: `auto`.
                - `capture_code` (bool): Saves op source code alongside each
                    version so ops can be reloaded later. Default: `True`.
                - `implicitly_patch_integrations` (bool): Auto-patches supported
                    libraries (for example, OpenAI, Anthropic) when they're
                    imported. When `False`, call `weave.integrations.patch_openai()`
                    or similar explicitly. Default: `True`.
                - `redact_pii` (bool): Scans trace data for PII (emails, phone
                    numbers, credit cards, etc.) and replaces matches with
                    placeholders before sending to the server. Requires the
                    `presidio-analyzer` and `presidio-anonymizer` packages.
                    Default: `False`.
                - `redact_pii_fields` (list[str]): PII entity types to redact
                    when `redact_pii` is `True`. When empty, Presidio's default
                    set is used. See the
                    [supported entities](https://microsoft.github.io/presidio/supported_entities/)
                    for the full list. Default: `[]`.
                - `redact_pii_exclude_fields` (list[str]): PII entity types to
                    exclude from redaction. Default: `[]`.
                - `capture_client_info` (bool): Includes Python and SDK version
                    information with each trace. Default: `True`.
                - `capture_system_info` (bool): Includes operating system
                    information with each trace. Default: `True`.
                - `client_parallelism` (int | None): Number of background
                    workers for trace uploads. `None` lets Weave choose based
                    on the host. Default: `None`.
                - `use_server_cache` (bool): Caches server responses on local
                    disk to speed up repeated reads. Default: `False`.
                - `server_cache_size_limit` (int): Size limit of the local
                    server cache, in bytes. Default: `1_000_000_000` (1 GB).
                - `server_cache_dir` (str): Directory used for the local server
                    cache. Default: a system temporary directory.
                - `scorers_dir` (str): Directory that holds downloaded scorer
                    model checkpoints. Default: `~/.cache/wandb/weave-scorers`.
                - `max_calls_queue_size` (int): Maximum number of pending
                    calls buffered in memory before upload. Set to `0` for no
                    limit. Default: `100_000`.
                - `retry_max_interval` (float): Maximum backoff interval
                    between retries, in seconds. Default: `300.0` (5 minutes).
                - `retry_max_attempts` (int): Number of times Weave re-attempts
                    a failed request before giving up. Default: `3`.
                - `enable_disk_fallback` (bool): Writes dropped queue items to
                    disk so they can be recovered later. Default: `True`.
                - `use_parallel_table_upload` (bool): Uploads large tables in
                    parallel chunks instead of sequentially. Default: `True`.
                - `http_timeout` (float): Per-request HTTP timeout in seconds,
                    covering connect, transfer, and server processing. Increase
                    for slow networks or large payloads. Default: `30.0`.
                - `use_stainless_server` (bool): Uses the Stainless-generated
                    HTTP client for trace server communication. Experimental.
                    Default: `False`.
                - `use_calls_complete` (bool): Sends start and end data for a
                    call in a single request, which reduces server load for
                    short-lived ops. Default: `False`.

            For the authoritative list of every supported field, see
            `UserSettings` in `weave.trace.settings`. For the full list of
            environment variables, see
            [Configure Weave environment variables](https://docs.wandb.ai/weave/guides/core-types/env-vars).
        autopatch_settings (AutopatchSettings | None): Deprecated. Per-integration
            autopatch configuration. Use explicit patching instead, for example
            `weave.integrations.patch_openai()`. Passing a non-`None` value logs
            a deprecation warning and has no effect on new integrations.
        global_postprocess_inputs (PostprocessInputsFunc | None): A function
            applied to the input dict of every traced op before the inputs are
            sent to the server. Runs after any op-specific `postprocess_inputs`.
            Use this to drop or mask fields globally.
        global_postprocess_output (PostprocessOutputFunc | None): A function
            applied to the return value of every traced op before the output is
            sent to the server. Runs after any op-specific `postprocess_output`.
        global_attributes (dict[str, Any] | None): Attributes merged into every
            trace produced by this process, for example `{"env": "production"}`.
            Keys set here are overridden by attributes set via
            `weave.attributes()` inside a call.

    Returns:
        weave_client.WeaveClient: The active Weave client, bound to the given
        project. When Weave is disabled through settings or the `WEAVE_DISABLED`
        environment variable, a dummy client that skips all network calls is
        returned instead.

    Raises:
        ValueError: When `project_name` is empty, is only whitespace, or
            contains more than one `/` separator.
        WeaveWandbAuthenticationException: When the team isn't specified and
            wandb can't resolve a default entity (usually because the user
            isn't logged in).
        RuntimeError: When the Weave service isn't reachable on the configured
            trace server.

    Example:
        ```python
        import weave

        weave.init("your-team/your-project")

        @weave.op
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        greet("Ada")
        ```

    See Also:
        - `weave.op`: Decorator that marks a function as traceable.
        - `weave.publish`: Saves and versions an object under the active project.
        - `weave.get_client`: Returns the active client without initializing.
        - `weave.finish`: Flushes pending work and tears down the active client.
        - `UserSettings`: The full schema for the `settings` argument.
    """
    if not project_name or not project_name.strip():
        raise ValueError("project_name must be non-empty")

    configure_logger()

    # Check if deprecated autopatch_settings is used
    if autopatch_settings is not None:
        logger.warning(
            "The 'autopatch_settings' parameter is deprecated and will be removed in a future version. "
            "Please use explicit patching instead. For example:\n"
            "----------------------------------------\n"
            "    import weave\n"
            "    weave.init('%s')\n"
            "    weave.integrations.patch_openai()\n"
            "----------------------------------------\n"
            "See https://docs.wandb.ai/models/integrations for more information.",
            project_name,
        )

    parse_and_apply_settings(settings)

    global _global_postprocess_inputs  # noqa: PLW0603
    global _global_postprocess_output  # noqa: PLW0603
    global _global_attributes  # noqa: PLW0603

    _global_postprocess_inputs = global_postprocess_inputs
    _global_postprocess_output = global_postprocess_output
    _global_attributes = global_attributes or {}

    if should_disable_weave():
        return weave_init.init_weave_disabled()

    return weave_init.init_weave(
        project_name,
    )


def get_client() -> weave_client.WeaveClient | None:
    """Returns the active `WeaveClient` instance, or `None` if Weave hasn't been initialized.

    Use this when you need access to the client after initialization has already 
    happened elsewhere, or when you want to check whether Weave is active before 
    calling client methods.

    If you need the client and want an error when it's absent, use
    `weave_client_context.require_weave_client()` instead, which raises
    `WeaveInitError` rather than returning `None`.

    Returns:
        weave_client.WeaveClient | None: The active client bound to the project
        passed to `weave.init()`, or `None` if `weave.init()` hasn't been called
        in this process (or if `weave.finish()` has been called since the last
        `weave.init()`).

    Example:
        ```python
        import weave

        weave.init("your-team/your-project")

        client = weave.get_client()
        if client is not None:
            print(client.entity, client.project)
        ```

    See Also:
        - `weave.init`: Initializes Weave and registers the global client.
        - `weave.finish`: Flushes pending work and removes the global client.
        - `weave_client_context.require_weave_client`: Like `get_client`, but raises
          `WeaveInitError` when no client is active.
    """
    return weave_client_context.get_weave_client()


def publish(
    obj: Any,
    name: str | None = None,
    tags: list[str] | None = None,
    aliases: list[str] | None = None,
) -> ObjectRef:
    """Saves a Python object to Weave and returns a versioned reference to it.

    Weave creates a content hash for `obj` and compares it to the latest
    version stored under the same name. A new version is created only when
    the hash differs, so publishing the same object twice does not create 
    a new version.

    When Weave is disabled (via the `WEAVE_DISABLED` environment variable or
    `settings={'disabled': True}` in `weave.init()`), this function returns a
    placeholder `ObjectRef` without making any network calls.

    After saving, Weave logs a link to the object in the Weave UI.

    Args:
        obj: The Python object to save. Any serializable Python value is
            accepted, including `weave.Model`, `weave.Dataset`, `weave.op`
            functions, dicts, and Pydantic models.
        name (str | None): The name to store the object under. When `None`,
            Weave falls back to `obj.name` (if the attribute exists) and then
            to the class name. Defaults to `None`.
        tags (list[str] | None): Tag strings to attach to this version after
            saving. Tags are additive labels used for filtering and grouping in
            the Weave UI. `None` attaches no tags. Defaults to `None`.
        aliases (list[str] | None): Alias strings to point at this version
            after saving. An alias resolves to exactly one version at a time,
            making it useful for stable identifiers like `"production"` or
            `"champion"`. `None` sets no aliases. Defaults to `None`.

    Returns:
        ObjectRef: A reference to the saved object version, containing
        `entity`, `project`, `name`, and `digest` fields. Call `ref.uri()`
        to get the fully qualified `weave:///` URI, or pass the ref directly
        to `weave.get()` to retrieve the object later.

    Raises:
        WeaveInitError: Raised when `weave.init()` hasn't been called and
            Weave is not disabled.

    Example:
        ```python
        import weave

        weave.init("your-team/your-project")

        dataset = weave.Dataset(name="my-dataset", rows=[{"input": "hello", "output": "world"}])
        ref = weave.publish(dataset, tags=["reviewed"], aliases=["champion"])

        # Retrieve it later using the ref or its URI
        same_dataset = weave.get(ref)
        ```

    See Also:
        - `weave.get`: Retrieves a published object by `ObjectRef` or URI.
        - `weave.ref`: Constructs an `ObjectRef` from a name or URI without fetching.
        - `weave.add_tags`: Adds tags to a published version after the fact.
        - `weave.set_aliases`: Updates aliases on a published version after the fact.
        - `ObjectRef`: The reference type returned by this function.
    """
    save_name: str
    if name:
        save_name = name
    elif n := getattr(obj, "name", None):
        save_name = n
    else:
        save_name = obj.__class__.__name__

    # If weave is disabled, return a dummy ref without making network calls
    if should_disable_weave():
        return weave_client.ObjectRef(
            entity="DISABLED",
            project="DISABLED",
            name=save_name,
            _digest="DISABLED",
        )

    client = weave_client_context.require_weave_client()

    ref = client._save_object(obj, save_name, "latest")

    if isinstance(ref, ObjectRef):
        if tags:
            client.add_tags(ref, tags)
        if aliases:
            client.set_aliases(ref, aliases)
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
        # Ensure logger level is up to date before logging
        update_logger_level()
        msg = f"{TRACE_OBJECT_EMOJI} Published to {url}"
        if tags or aliases:
            extras = []
            if tags:
                extras.append(f"tags: {', '.join(tags)}")
            if aliases:
                extras.append(f"aliases: {', '.join(aliases)}")
            msg += f" ({'; '.join(extras)})"
        logger.info(msg)
    return ref


def add_tags(obj_ref: ObjectRef | str, tags: list[str]) -> None:
    """Attaches tags to a published object version, extending its existing tag set.

    Tags are free-form, additive labels you can apply to a published
    object version for filtering, grouping, and organization in the
    Weave UI. Calls to `add_tags` are cumulative; use
    `weave.remove_tags` to take tags off and `weave.get_tags` to read
    the current set.

    Tags differ from aliases. Any number of tags can coexist on a single
    version, and the same tag can apply to any number of versions. An
    alias such as `production`, by contrast, resolves to one specific
    version at a time. See `weave.set_aliases` for the alias workflow.

    The target object must already be published. Most callers obtain
    its `ObjectRef` from `weave.publish()`; alternatively, pass the
    `weave:///` URI string copied from the Weave UI or returned by a
    previous `ref.uri()` call.

    Args:
        obj_ref: The version to tag. Pass either an `ObjectRef` returned
            by `weave.publish()` or a fully qualified `weave:///` URI
            string. Short forms like `"name:version"` aren't accepted
            here; resolve them to a URI with `weave.ref()` first.
        tags: Tag strings to add to the version's tag set.

    Raises:
        WeaveInitError: If `weave.init()` hasn't been called in the
            current process.
        ValueError: If `obj_ref` is a string that isn't a valid
            `weave:///` URI.

    Example:
        >>> import weave
        >>> weave.init("your-team/your-project")
        >>>
        >>> @weave.op
        ... def greet(name: str) -> str:
        ...     return f"Hello, {name}!"
        >>>
        >>> ref = weave.publish(greet)
        >>> weave.add_tags(ref, ["reviewed", "frozen"])

    See Also:
        - `weave.publish`: Saves an object and returns the `ObjectRef`
          to tag.
        - `weave.remove_tags`: Removes tags from a version (inverse).
        - `weave.get_tags`: Reads the current tags on a version.
        - `weave.list_tags`: Lists every distinct tag in the project.
        - `weave.get_tags_and_aliases`: Reads tags and aliases together.
        - `weave.set_aliases`: Manages aliases, the version-pointer
          companion to tags.
    """
    client = weave_client_context.require_weave_client()
    client.add_tags(obj_ref, tags)


def remove_tags(obj_ref: ObjectRef | str, tags: list[str]) -> None:
    """Removes specific tags from a published object version.

    Only the tags listed in `tags` are removed. All other tags on the version
    remain untouched. To see the current tag set before removing, call
    `weave.get_tags()` first. Tags not currently on the version are ignored.

    The target object must already be published. Most callers obtain its
    `ObjectRef` from `weave.publish()`; alternatively, pass the `weave:///`
    URI string copied from the Weave UI or returned by a previous
    `ref.uri()` call.

    Args:
        obj_ref: The version to remove tags from. Pass either an `ObjectRef`
            returned by `weave.publish()` or a fully qualified `weave:///`
            URI string. Short forms like `"name:version"` aren't accepted
            here; resolve them to a URI with `weave.ref()` first.
        tags: Tag strings to remove from the version's tag set.

    Raises:
        WeaveInitError: Raised when `weave.init()` hasn't been called in the
            current process.
        ValueError: Raised when `obj_ref` is a string that isn't a valid
            `weave:///` URI.

    Example:
        ```python
        import weave

        weave.init("your-team/your-project")

        dataset = weave.Dataset(name="eval-set", rows=[{"input": "hi"}])
        ref = weave.publish(dataset, tags=["reviewed", "frozen"])

        weave.remove_tags(ref, ["frozen"])
        print(weave.get_tags(ref))  # ["reviewed"]
        ```

    See Also:
        - `weave.add_tags`: Adds tags to a version (inverse).
        - `weave.get_tags`: Reads the current tag set on a version.
        - `weave.list_tags`: Lists every distinct tag across the project.
        - `weave.publish`: Saves an object and returns the `ObjectRef` to tag.
    """
    client = weave_client_context.require_weave_client()
    client.remove_tags(obj_ref, tags)


def get_tags(obj_ref: ObjectRef | str) -> list[str]:
    """Get tags for an object version.

    Args:
        obj_ref: Reference to the object version, either an ObjectRef
            or a weave:/// URI string.

    Returns:
        List of tag strings.
    """
    client = weave_client_context.require_weave_client()
    return client.get_tags(obj_ref)


def set_aliases(obj_ref: ObjectRef | str, alias: str | list[str]) -> None:
    """Set one or more aliases for an object version.

    Args:
        obj_ref: Reference to the object version, either an ObjectRef
            or a weave:/// URI string.
        alias: An alias name or list of alias names to set (e.g., "production").
    """
    client = weave_client_context.require_weave_client()
    client.set_aliases(obj_ref, alias)


def remove_aliases(obj_ref: ObjectRef | str, alias: str | list[str]) -> None:
    """Remove one or more aliases from an object.

    Args:
        obj_ref: Reference to the object, either an ObjectRef
            or a weave:/// URI string.
        alias: An alias name or list of alias names to remove.
    """
    client = weave_client_context.require_weave_client()
    client.remove_aliases(obj_ref, alias)


def get_aliases(obj_ref: ObjectRef | str) -> list[str]:
    """Get aliases for an object version.

    Args:
        obj_ref: Reference to the object version, either an ObjectRef
            or a weave:/// URI string.

    Returns:
        List of alias strings.
    """
    client = weave_client_context.require_weave_client()
    return client.get_aliases(obj_ref)


def get_tags_and_aliases(obj_ref: ObjectRef | str) -> tuple[list[str], list[str]]:
    """Get both tags and aliases for an object version in a single call.

    Args:
        obj_ref: Reference to the object version, either an ObjectRef
            or a weave:/// URI string.

    Returns:
        A tuple of (tags, aliases). Each is a list of strings.
    """
    client = weave_client_context.require_weave_client()
    return client.get_tags_and_aliases(obj_ref)


def list_tags() -> list[str]:
    """List all distinct tags in the project.

    Returns:
        Sorted list of all tag strings in the project.
    """
    client = weave_client_context.require_weave_client()
    return client.list_tags()


def list_aliases() -> list[str]:
    """List all distinct aliases in the project.

    Returns:
        Sorted list of all alias strings in the project.
    """
    client = weave_client_context.require_weave_client()
    return client.list_aliases()


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
def thread(thread_id: str | object | None = _AUTO_GENERATE) -> Iterator[ThreadContext]:
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
        actual_thread_id = cast(str | None, thread_id)

    # Create context object
    context = ThreadContext(actual_thread_id)

    with call_context.set_thread_id(actual_thread_id):
        # Reset turn lineage when entering new thread context
        call_context.set_turn_id(None)
        yield context


def finish() -> None:
    """Stops logging to weave.

    Following finish, calls of weave.op decorated functions will no longer be logged. You will need to run weave.init() again to resume logging.

    """
    # Capture client before teardown so we can still flush outstanding work.
    wc = weave_client_context.get_weave_client()
    weave_init.finish()

    # Flush any remaining calls
    if wc is not None:
        wc.finish()


__all__ = [
    "ObjectRef",
    "Table",
    "ThreadContext",
    "add_tags",
    "as_op",
    "attributes",
    "finish",
    "get",
    "get_aliases",
    "get_client",
    "get_current_call",
    "get_tags",
    "get_tags_and_aliases",
    "init",
    "list_aliases",
    "list_tags",
    "op",
    "publish",
    "ref",
    "remove_aliases",
    "remove_tags",
    "require_current_call",
    "set_aliases",
    "set_view",
    "thread",
    "weave_client_context",
]
