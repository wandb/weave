"""Utilities for attaching Content-backed views to trace calls."""

from __future__ import annotations

from typing import Any

from weave.trace.call import Call
from weave.trace.serialization.serialize import to_json
from weave.trace.table import Table
from weave.trace.weave_client import WeaveClient
from weave.trace.widgets import Widget
from weave.type_wrappers.Content.content import Content

ViewItem = Content | str | Widget | Table
ViewSpec = ViewItem | list[ViewItem]


def resolve_view_content(
    content: Content | str,
    *,
    extension: str | None = None,
    mimetype: str | None = None,
    metadata: dict[str, Any] | None = None,
    encoding: str = "utf-8",
) -> Content:
    """Return a ``weave.Content`` for the provided content input.

    Args:
        content: Either a preconstructed ``weave.Content`` instance or a text
            string to encode as content.
        extension: Optional file extension (e.g. ``"md"`` or ``".html"``)
            used when the ``content`` argument is a string.
        mimetype: Explicit MIME type override for string content.
        metadata: Optional metadata to attach when constructing content from a
            string.
        encoding: Text encoding to use when converting string content.

    Returns:
        A ``weave.Content`` instance that can be serialized into the call
        summary.

    Raises:
        TypeError: If ``content`` is neither a string nor a ``weave.Content``.

    Examples:
        >>> resolve_view_content("# Title", extension="md").mimetype
        'text/markdown'
    """
    if isinstance(content, Content):
        result = content
    else:
        result = Content._from_guess(
            content,
            extension=extension,
            mimetype=mimetype,
        )

    updates: dict[str, Any] = {}
    if metadata is not None:
        updates["metadata"] = metadata
    if encoding is not None:
        updates["encoding"] = encoding

    if len(updates) > 0:
        result = result.model_copy(update=updates)

    return result


def serialize_view_item(
    item: ViewItem,
    project_id: str,
    client: WeaveClient,
    *,
    extension: str | None = None,
    mimetype: str | None = None,
    metadata: dict[str, Any] | None = None,
    encoding: str = "utf-8",
) -> dict[str, Any] | str:
    """Serialize a single view item to JSON.

    Args:
        item: A Content, string, Widget, or Table to serialize.
        project_id: The project ID for serialization context.
        client: The WeaveClient for serialization.
        extension: Optional file extension for string content.
        mimetype: Optional MIME type for string content.
        metadata: Optional metadata for string content.
        encoding: Encoding for string content.

    Returns:
        A JSON-serializable dictionary or string (for Table refs).
    """
    if isinstance(item, Widget):
        return item.model_dump()
    elif isinstance(item, Table):
        # Publish the table and return its ref URI
        table_ref = client._save_table(item)
        return table_ref.uri()
    elif isinstance(item, (Content, str)):
        content_obj = resolve_view_content(
            item,
            extension=extension,
            mimetype=mimetype,
            metadata=metadata,
            encoding=encoding,
        )
        return to_json(content_obj, project_id, client, use_dictify=False)
    else:
        raise TypeError(f"Unsupported view item type: {type(item)}")


def serialize_view_spec(
    spec: ViewSpec,
    project_id: str,
    client: WeaveClient,
    *,
    extension: str | None = None,
    mimetype: str | None = None,
    metadata: dict[str, Any] | None = None,
    encoding: str = "utf-8",
) -> dict[str, Any] | str | list[dict[str, Any] | str]:
    """Serialize a view specification to JSON.

    Args:
        spec: A single view item or list of view items.
        project_id: The project ID for serialization context.
        client: The WeaveClient for serialization.
        extension: Optional file extension for string content.
        mimetype: Optional MIME type for string content.
        metadata: Optional metadata for string content.
        encoding: Encoding for string content.

    Returns:
        A JSON-serializable dictionary, string (for Table refs), or list of these.
    """
    if isinstance(spec, list):
        return [serialize_view_item(item, project_id, client) for item in spec]
    else:
        return serialize_view_item(
            spec,
            project_id,
            client,
            extension=extension,
            mimetype=mimetype,
            metadata=metadata,
            encoding=encoding,
        )


def set_call_view(
    *,
    call: Call,
    client: WeaveClient,
    name: str,
    content: ViewSpec,
    extension: str | None = None,
    mimetype: str | None = None,
    metadata: dict[str, Any] | None = None,
    encoding: str = "utf-8",
) -> None:
    """Attach serialized content to the provided call's summary under `weave.views`.

    Args:
        call: The call whose summary should receive the view entry.
        client: The active ``WeaveClient`` used for serialization.
        name: Key to store the view under within ``summary.weave.views``.
        content: A ``weave.Content``, raw text, ``Widget``, ``Table``, or list of these
            to serialize into the view.
        extension: Optional file extension used when converting text content.
        mimetype: Optional MIME type applied when converting text content.
        metadata: Optional metadata for newly created ``Content`` objects.
        encoding: Encoding used when converting string content to bytes.

    Returns:
        None

    Raises:
        ValueError: If ``name`` is not a non-empty string.

    Examples:
        >>> from weave.trace.call import Call
        >>> call = Call(None, "proj", None, {})  # doctest: +SKIP
        >>> set_call_view(  # doctest: +SKIP
        ...     call=call,
        ...     client=client,
        ...     name="report",
        ...     content="<h1>Hello</h1>",
        ...     extension="html",
        ... )
    """
    if call.summary is None:
        call.summary = {}

    summary = call.summary

    weave_bucket = summary.get("weave")
    if not isinstance(weave_bucket, dict):
        weave_bucket = {}
        summary["weave"] = weave_bucket

    legacy_views = summary.get("views")
    if isinstance(legacy_views, dict):
        summary.pop("views", None)
    views = weave_bucket.get("views")

    if not isinstance(views, dict):
        views = {}
        weave_bucket["views"] = views

    if isinstance(legacy_views, dict):
        views.update(legacy_views)

    project_id = client._project_id()
    views[name] = serialize_view_spec(
        content,
        project_id,
        client,
        extension=extension,
        mimetype=mimetype,
        metadata=metadata,
        encoding=encoding,
    )
