"""Utilities for attaching Content-backed views to trace calls."""

from __future__ import annotations

from typing import Any

from weave.trace.call import Call
from weave.trace.serialization.serialize import to_json
from weave.trace.weave_client import WeaveClient
from weave.type_wrappers.Content.content import Content


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


def set_call_view(
    *,
    call: Call,
    client: WeaveClient,
    name: str,
    content: Content | str,
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
        content: ``weave.Content`` or raw text to serialize into the view.
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
    content_obj = resolve_view_content(
        content,
        extension=extension,
        mimetype=mimetype,
        metadata=metadata,
        encoding=encoding,
    )

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
    views[name] = to_json(content_obj, project_id, client, use_dictify=False)
