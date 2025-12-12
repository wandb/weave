from pydantic import BaseModel, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def


class OpViewDefinition(BaseModel):
    """The view template and configuration."""

    # The Handlebars HTML template
    template: str

    # Template type for future extensibility (e.g., "handlebars", "react")
    template_type: str = Field(default="handlebars")

    # Optional: metadata about what data the template expects
    # Could be used for validation or documentation
    expected_schema: dict | None = Field(default=None)


class OpView(base_object_def.BaseObject):
    """A reusable view template associated with an op.

    Views are associated with the base op name (without version) so they
    apply to all versions of an op within a project.
    """

    # The op this view is for (base op ref without version,
    # e.g., "weave:///entity/project/op/my_op")
    op_name: str

    # Human-readable label for the view
    label: str

    # The view definition
    definition: OpViewDefinition

    # Optional: ordering hint when multiple views exist for same op
    priority: int = Field(default=0)


__all__ = ["OpView", "OpViewDefinition"]
