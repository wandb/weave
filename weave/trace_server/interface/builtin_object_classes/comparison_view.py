"""ComparisonView builtin object class for saving comparison view configurations.

This allows users to save and restore comparison configurations including
evaluation call IDs and selected metrics.
"""

from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def


class ComparisonViewDefinition(BaseModel):
    """Definition of a comparison view's configuration.

    Args:
        evaluation_call_ids (List[str]): List of evaluation call IDs being compared.
        selected_metrics (Optional[List[str]]): List of metrics that are visible in plots.

    Examples:
        >>> definition = ComparisonViewDefinition(
        ...     evaluation_call_ids=["call_1", "call_2"],
        ...     selected_metrics=["accuracy", "f1_score"]
        ... )
    """

    evaluation_call_ids: list[str]
    selected_metrics: list[str] | None = None


class ComparisonView(base_object_def.BaseObject):
    """A saved comparison view configuration.

    Args:
        label (str): Human-readable name for the comparison view.
        definition (ComparisonViewDefinition): The view's configuration.

    Examples:
        >>> view = ComparisonView(
        ...     label="My Comparison",
        ...     definition=ComparisonViewDefinition(
        ...         evaluation_call_ids=["call_1", "call_2"]
        ...     )
        ... )
    """

    label: str
    definition: ComparisonViewDefinition


__all__ = ["ComparisonView", "ComparisonViewDefinition"]
