# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional
from typing_extensions import Required, TypedDict

from .._types import SequenceNotStr

__all__ = ["FeedbackReplaceParams"]


class FeedbackReplaceParams(TypedDict, total=False):
    feedback_id: Required[str]

    feedback_type: Required[str]

    payload: Required[Dict[str, object]]

    project_id: Required[str]

    weave_ref: Required[str]

    id: Optional[str]
    """
    If provided by the client, this ID will be used for the feedback row instead of
    a server-generated one.
    """

    annotation_ref: Optional[str]

    call_ref: Optional[str]

    creator: Optional[str]

    queue_id: Optional[str]
    """The annotation queue ID this feedback was created from.

    References annotation_queues.id. NULL when feedback is created outside of
    queues.
    """

    runnable_ref: Optional[str]

    scorer_rating_confidences: Dict[str, float]
    """confidence (0-1) per rating, keyed by rating name"""

    scorer_rating_reasons: Dict[str, str]
    """reason text per rating, keyed by rating name"""

    scorer_ratings: Dict[str, float]
    """numeric ratings (0-1) keyed by rating name"""

    scorer_tag_confidences: Dict[str, float]
    """confidence (0-1) per tag, keyed by tag name"""

    scorer_tag_reasons: Dict[str, str]
    """reason text per tag, keyed by tag name"""

    scorer_tags: SequenceNotStr[str]
    """Tags applied to the ref by a scorer"""

    scorer_trace_id: str
    """
    Trace of the scorer (judge) invocation that produced this feedback
    (spans.trace_id of the judge call). Distinct from span_trace_id, which is the
    scored turn. Lets signals price the invocation off the judge span without
    joining the calls model.
    """

    span_agent_name: str
    """Display name of the scored agent (from spans.agent_name)"""

    span_agent_version: str
    """Version of the scored agent (from spans.agent_version)"""

    span_conversation_id: str
    """Conversation the feedback belongs to (from spans.conversation_id)"""

    span_status_code: str
    """Status of the scored turn (from spans.status_code)"""

    span_trace_id: str
    """Turn the feedback belongs to (from spans.trace_id)"""

    trigger_ref: Optional[str]

    wb_user_id: Optional[str]
    """Do not set directly. Server will automatically populate this field."""
