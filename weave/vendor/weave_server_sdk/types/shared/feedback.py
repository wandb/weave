# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from typing import Dict, List, Optional
from datetime import datetime

from ..._models import BaseModel

__all__ = ["Feedback"]


class Feedback(BaseModel):
    id: str

    created_at: datetime

    feedback_type: str

    payload: Dict[str, object]

    project_id: str

    weave_ref: str

    annotation_ref: Optional[str] = None

    call_ref: Optional[str] = None

    creator: Optional[str] = None

    queue_id: Optional[str] = None
    """The annotation queue ID this feedback was created from.

    References annotation_queues.id. NULL when feedback is created outside of
    queues.
    """

    runnable_ref: Optional[str] = None

    scorer_rating_confidences: Optional[Dict[str, float]] = None
    """confidence (0-1) per rating, keyed by rating name"""

    scorer_rating_reasons: Optional[Dict[str, str]] = None
    """reason text per rating, keyed by rating name"""

    scorer_ratings: Optional[Dict[str, float]] = None
    """numeric ratings (0-1) keyed by rating name"""

    scorer_tag_confidences: Optional[Dict[str, float]] = None
    """confidence (0-1) per tag, keyed by tag name"""

    scorer_tag_reasons: Optional[Dict[str, str]] = None
    """reason text per tag, keyed by tag name"""

    scorer_tags: Optional[List[str]] = None
    """Tags applied to the ref by a scorer"""

    scorer_trace_id: Optional[str] = None
    """
    Trace of the scorer (judge) invocation that produced this feedback
    (spans.trace_id of the judge call). Distinct from span_trace_id, which is the
    scored turn. Lets signals price the invocation off the judge span without
    joining the calls model.
    """

    span_agent_name: Optional[str] = None
    """Display name of the scored agent (from spans.agent_name)"""

    span_agent_version: Optional[str] = None
    """Version of the scored agent (from spans.agent_version)"""

    span_conversation_id: Optional[str] = None
    """Conversation the feedback belongs to (from spans.conversation_id)"""

    span_status_code: Optional[str] = None
    """Status of the scored turn (from spans.status_code)"""

    span_trace_id: Optional[str] = None
    """Turn the feedback belongs to (from spans.trace_id)"""

    trigger_ref: Optional[str] = None

    wb_user_id: Optional[str] = None
    """Do not set directly. Server will automatically populate this field."""
