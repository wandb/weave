"""CallViewSpec builtin type for storing view configurations attached to calls."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def
from weave.trace_server.interface.builtin_object_classes.saved_view import (
    SavedViewDefinition,
)


class ContentViewItem(BaseModel):
    """Serialized Content object for display in call views.

    Represents rich content like markdown, HTML, or other text formats
    that can be rendered in the UI.
    """

    type: Literal["content"] = "content"
    mimetype: str
    encoding: str | None = None
    data: str  # base64 encoded content
    metadata: dict[str, Any] | None = None


class ScoreSummaryWidgetItem(BaseModel):
    """Widget displaying score summary for the current evaluation call.

    This widget displays the score summary from the call it's attached to.
    No configuration needed - it automatically uses the current call's data.
    """

    type: Literal["score_summary"] = "score_summary"


class ChildPredictionsWidgetItem(BaseModel):
    """Widget displaying child predictions of the current evaluation call.

    This widget displays the predictions from the call it's attached to.
    No configuration needed - it automatically uses the current call's child calls.
    """

    type: Literal["child_predictions"] = "child_predictions"


class TableRefViewItem(BaseModel):
    """Reference to a Table object for display in call views.

    Stores a URI reference to a saved Table that can be rendered
    as a data table in the UI.
    """

    type: Literal["table_ref"] = "table_ref"
    # Named 'uri' not 'ref' to avoid collision with ObjectRef 'ref' attribute pattern
    uri: str  # Table URI (e.g., weave-trace-internal:///project/table/digest)


class ObjectRefViewItem(BaseModel):
    """Reference to a Weave object for display in call views.

    Stores a URI reference to a saved object (e.g., SavedView) that
    can be resolved and rendered by the UI.
    """

    type: Literal["object_ref"] = "object_ref"
    # Named 'uri' not 'ref' to avoid collision with ObjectRef 'ref' attribute pattern
    uri: str  # Object URI (e.g., weave:///entity/project/object/SavedView:digest)


class SavedViewDefinitionItem(BaseModel):
    """Embedded SavedView definition for display in call views.

    Stores the view definition directly in the CallViewSpec rather than
    requiring a separate SavedView object to be saved and referenced.
    This simplifies the user workflow by eliminating the need to save
    a SavedView object before attaching it to a call.
    """

    type: Literal["saved_view_definition"] = "saved_view_definition"
    label: str  # Display label for the view
    definition: SavedViewDefinition


# Union of all view item types with discriminator for proper deserialization
ViewItem = Annotated[
    ContentViewItem
    | ScoreSummaryWidgetItem
    | ChildPredictionsWidgetItem
    | TableRefViewItem
    | ObjectRefViewItem
    | SavedViewDefinitionItem,
    Field(discriminator="type"),
]


class CallViewSpec(base_object_def.BaseObject):
    """View specification attached to a call.

    Contains a mapping of view names to their specifications. Each view
    can be a single item or a list of items that will be rendered together.

    The view spec is stored as a versioned object, enabling deduplication
    when the same view configuration is used across multiple calls.

    Examples:
        >>> spec = CallViewSpec(
        ...     views={
        ...         "report": ContentViewItem(
        ...             mimetype="text/markdown",
        ...             data="IyBIZWxsbw==",  # base64 "# Hello"
        ...         ),
        ...         "scores": ScoreSummaryWidgetItem(),
        ...     }
        ... )
    """

    views: dict[str, ViewItem | list[ViewItem]] = Field(
        default_factory=dict,
        description="Mapping of view names to view item(s)",
    )


__all__ = [
    "CallViewSpec",
    "ChildPredictionsWidgetItem",
    "ContentViewItem",
    "ObjectRefViewItem",
    "SavedViewDefinitionItem",
    "ScoreSummaryWidgetItem",
    "TableRefViewItem",
    "ViewItem",
]
