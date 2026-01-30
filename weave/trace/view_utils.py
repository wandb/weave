"""Utilities for attaching Content-backed views to trace calls."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from weave.trace.call import Call
from weave.trace.refs import ObjectRef
from weave.trace.serialization.serialize import to_json
from weave.trace.table import Table
from weave.trace.widgets import ChildPredictionsWidget, ScoreSummaryWidget, Widget
from weave.trace_server.interface.builtin_object_classes.call_view_spec import (
    CallViewSpec,
    ChildPredictionsWidgetItem,
    ContentViewItem,
    ObjectRefViewItem,
    SavedViewDefinitionItem,
    ScoreSummaryWidgetItem,
    TableRefViewItem,
)
from weave.trace_server.interface.builtin_object_classes.call_view_spec import (
    ViewItem as CallViewSpecItem,
)
from weave.type_wrappers.Content.content import Content

if TYPE_CHECKING:
    from weave.flow.saved_view import SavedView as SDKSavedView
    from weave.trace.weave_client import WeaveClient

    # Type aliases for type checking - includes SavedView
    ViewItem = Content | str | Widget | Table | ObjectRef | SDKSavedView
    ViewSpec = ViewItem | list[ViewItem]
else:
    # At runtime, use Any since SDKSavedView causes circular import
    ViewItem = Any
    ViewSpec = Any


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


def _sdk_view_item_to_call_view_spec_item(
    item: ViewItem,
    client: WeaveClient,
    *,
    extension: str | None = None,
    mimetype: str | None = None,
    metadata: dict[str, Any] | None = None,
    encoding: str = "utf-8",
) -> CallViewSpecItem:
    """Convert an SDK view item to a CallViewSpec item for storage.

    Args:
        item: A Content, string, Widget, Table, or SavedView to convert.
        client: The WeaveClient for saving tables.
        extension: Optional file extension for string content.
        mimetype: Optional MIME type for string content.
        metadata: Optional metadata for string content.
        encoding: Encoding for string content.

    Returns:
        A CallViewSpec item (ContentViewItem, WidgetItem, TableRefViewItem, or
        SavedViewDefinitionItem).
    """
    # Import here to avoid circular imports
    from weave.flow.saved_view import SavedView as SDKSavedView

    if isinstance(item, ScoreSummaryWidget):
        return ScoreSummaryWidgetItem()
    elif isinstance(item, ChildPredictionsWidget):
        return ChildPredictionsWidgetItem()
    elif isinstance(item, Widget):
        # Future widgets - default to score_summary for now
        return ScoreSummaryWidgetItem()
    elif isinstance(item, Table):
        # Publish the table and return its ref URI
        table_ref = client._save_table(item)
        return TableRefViewItem(uri=table_ref.uri())
    elif isinstance(item, SDKSavedView):
        # Embed the SavedView definition directly in the CallViewSpec
        # This avoids needing to save the SavedView as a separate object
        return SavedViewDefinitionItem(
            label=item.base.label,
            definition=item.base.definition,
        )
    elif isinstance(item, ObjectRef):
        # Store object references (e.g., SavedView) as URI strings
        return ObjectRefViewItem(uri=item.uri())
    elif isinstance(item, (Content, str)):
        content_obj = resolve_view_content(
            item,
            extension=extension,
            mimetype=mimetype,
            metadata=metadata,
            encoding=encoding,
        )
        # Encode content data as base64
        data_bytes = (
            content_obj.data
            if isinstance(content_obj.data, bytes)
            else content_obj.data.encode(content_obj.encoding or "utf-8")
        )
        return ContentViewItem(
            mimetype=content_obj.mimetype,
            encoding=content_obj.encoding,
            data=base64.b64encode(data_bytes).decode("ascii"),
            metadata=content_obj.metadata,
        )
    else:
        raise TypeError(f"Unsupported view item type: {type(item)}")


def _sdk_view_spec_to_call_view_spec_item(
    spec: ViewSpec,
    client: WeaveClient,
    *,
    extension: str | None = None,
    mimetype: str | None = None,
    metadata: dict[str, Any] | None = None,
    encoding: str = "utf-8",
) -> CallViewSpecItem | list[CallViewSpecItem]:
    """Convert an SDK view spec to CallViewSpec item(s).

    Args:
        spec: A single view item or list of view items.
        client: The WeaveClient for saving tables.
        extension: Optional file extension for string content.
        mimetype: Optional MIME type for string content.
        metadata: Optional metadata for string content.
        encoding: Encoding for string content.

    Returns:
        A CallViewSpec item or list of items.
    """
    if isinstance(spec, list):
        return [_sdk_view_item_to_call_view_spec_item(item, client) for item in spec]
    else:
        return _sdk_view_item_to_call_view_spec_item(
            spec,
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
    """Attach a view to the call's pending views for later storage as CallViewSpec.

    Views are stored in the call's _pending_views dict and will be converted to
    a CallViewSpec object when the call is finished. This allows deduplication
    of identical view configurations across calls.

    Args:
        call: The call whose pending views should receive the view entry.
        client: The active ``WeaveClient`` used for serialization.
        name: Key to store the view under.
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
    # Store the converted view item in _pending_views
    call._pending_views[name] = _sdk_view_spec_to_call_view_spec_item(
        content,
        client,
        extension=extension,
        mimetype=mimetype,
        metadata=metadata,
        encoding=encoding,
    )


def build_and_save_call_view_spec(
    call: Call,
    client: WeaveClient,
) -> str | None:
    """Build a CallViewSpec from pending views and save it as an object.

    This function collects all pending views from the call, creates a CallViewSpec
    object, and saves it to the project. The returned ref URI can be used as the
    view_spec_ref in the call_end request.

    Args:
        call: The call with pending views to save.
        client: The WeaveClient for saving the object.

    Returns:
        The view_spec_ref URI string, or None if no views are pending.
    """
    if not call._pending_views:
        return None

    # Convert pending views dict values to the proper union type
    views_dict: dict[str, CallViewSpecItem | list[CallViewSpecItem]] = {}
    for name, item in call._pending_views.items():
        views_dict[name] = item

    # Create the CallViewSpec object
    view_spec = CallViewSpec(views=views_dict)

    # Save as a versioned object - content-addressed storage will deduplicate
    ref: ObjectRef = client._save_object(view_spec, name="CallViewSpec")

    return ref.uri()
