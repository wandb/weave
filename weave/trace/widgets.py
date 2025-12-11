"""Widget types for custom views in call summaries."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Widget(BaseModel):
    """Base class for all view widgets."""

    pass


class ScoreSummaryWidget(Widget):
    """Widget displaying score summary for the current evaluation call.

    This widget displays the score summary from the call it's attached to.
    No configuration needed - it automatically uses the current call's data.

    Examples:
        >>> from weave.trace.widgets import ScoreSummaryWidget
        >>> widget = ScoreSummaryWidget()
    """

    type: Literal["score_summary"] = "score_summary"


class ChildPredictionsWidget(Widget):
    """Widget displaying child predictions of the current evaluation call.

    This widget displays the predictions from the call it's attached to.
    No configuration needed - it automatically uses the current call's child calls.

    Examples:
        >>> from weave.trace.widgets import ChildPredictionsWidget
        >>> widget = ChildPredictionsWidget()
    """

    type: Literal["child_predictions"] = "child_predictions"


AnyWidget = Annotated[
    ScoreSummaryWidget | ChildPredictionsWidget,
    Field(discriminator="type"),
]

__all__ = [
    "AnyWidget",
    "ChildPredictionsWidget",
    "ScoreSummaryWidget",
    "Widget",
]
