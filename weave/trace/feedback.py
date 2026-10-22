"""Classes for working with feedback on a project or ref level."""

from __future__ import annotations

import datetime
import json
import logging
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, cast

from pydantic import BaseModel, Field, model_validator

from weave.trace import util
from weave.trace.context import weave_client_context
from weave.trace.display import display
from weave.trace.display.rich import pydantic_util
from weave.trace.display.rich.container import AbstractRichContainer
from weave.trace.display.rich.refs import Refs
from weave.trace.feedback_types import (
    AGENT_USER_FEEDBACK_TYPE,
    NOTE_FEEDBACK_TYPE,
    REACTION_FEEDBACK_TYPE,
)
from weave.trace.refs import (
    AgentConversationRef,
    AgentSpanRef,
    AgentTurnRef,
    AnyRef,
    ObjectRef,
    Ref,
)
from weave.utils.project_id import to_project_id
from weave.vendor.weave_server_sdk.types import (
    FeedbackCreateParams,
    feedback_purge_params,
    feedback_query_params,
)

# Reason the Agent UI records for human reactions; keep in sync with Reactions.tsx.
AGENT_REACTION_REASON = "Set by user"

# The old warning used this logger name, not this module's.
logger = logging.getLogger("weave.trace_server.common_interface")
_warned_feedback_fields: set[tuple[str, ...]] = set()


class Feedback(BaseModel):
    """A feedback row, as a feedback query returns it."""

    id: str
    project_id: str
    weave_ref: str
    creator: str | None = None
    feedback_type: str
    payload: dict[str, Any]
    annotation_ref: str | None = None
    runnable_ref: str | None = None
    call_ref: str | None = None
    trigger_ref: str | None = None
    queue_id: str | None = None
    scorer_tags: list[str] = Field(default_factory=list)
    scorer_tag_reasons: dict[str, str] = Field(default_factory=dict)
    scorer_tag_confidences: dict[str, float] = Field(default_factory=dict)
    scorer_ratings: dict[str, float] = Field(default_factory=dict)
    scorer_rating_reasons: dict[str, str] = Field(default_factory=dict)
    scorer_rating_confidences: dict[str, float] = Field(default_factory=dict)
    span_agent_name: str = ""
    span_agent_version: str = ""
    span_status_code: str = "UNSET"
    span_conversation_id: str = ""
    span_trace_id: str = ""
    scorer_trace_id: str = ""
    wb_user_id: str | None = None
    created_at: datetime.datetime

    @model_validator(mode="before")
    @classmethod
    def warn_on_extra_fields(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        known = set(cls.model_fields)
        known.update(
            field.alias
            for field in cls.model_fields.values()
            if field.alias is not None
        )
        extra_fields = set(values) - known
        if not extra_fields or not logger.isEnabledFor(logging.WARNING):
            return values
        fields = tuple(sorted(extra_fields))
        if fields not in _warned_feedback_fields:
            _warned_feedback_fields.add(fields)
            logger.warning(
                "Ignoring unexpected fields while validating %s: %s",
                cls.__name__,
                ", ".join(fields),
            )
        return values


class Feedbacks(AbstractRichContainer[Feedback]):
    """A collection of Feedback objects with utilities."""

    show_refs: bool

    def __init__(
        self, show_refs: bool, feedbacks: Iterable[Feedback] | None = None
    ) -> None:
        super().__init__("Feedback", feedbacks)
        self.show_refs = show_refs

    def refs(self) -> Refs:
        """Return the unique refs associated with these feedbacks."""
        uris = list(dict.fromkeys(feedback.weave_ref for feedback in self.items))
        return Refs(uris)

    def _add_table_columns(self, table: display.Table) -> None:
        if self.show_refs:
            table.add_column("Ref", overflow="fold")
        table.add_column("Type", justify="center")
        table.add_column("Feedback", overflow="fold")
        table.add_column("Created")
        table.add_column("ID", overflow="fold")
        table.add_column("Creator")

    def _item_to_row(self, item: Feedback) -> list:
        feedback = item

        type_ = feedback.feedback_type
        display_type = type_
        if type_ == REACTION_FEEDBACK_TYPE:
            display_type = "reaction"
            if util.is_notebook():
                # TODO: Emojis mess up table alignment in Jupyter 😢
                #       maybe there is something else we could do here?
                content = feedback.payload["alias"]
            else:
                content = feedback.payload["emoji"]
        elif type_ == NOTE_FEEDBACK_TYPE:
            display_type = "note"
            content = feedback.payload["note"]
        else:
            content = json.dumps(feedback.payload, indent=2)

        # TODO: Prettier relative time display?
        created_at = str(feedback.created_at.replace(tzinfo=None))

        creator = feedback.wb_user_id
        if feedback.creator is not None:
            creator = f"{feedback.creator} ({creator})"

        row = [
            display_type,
            content,
            created_at,
            feedback.id,
            creator,
        ]
        if self.show_refs:
            row.insert(0, feedback.weave_ref)
        return row


class FeedbackQuery:
    """Lazy-loading object for fetching feedback from the server."""

    entity: str
    project: str

    show_refs: bool
    _query: Mapping[str, Any]
    offset: int | None
    limit: int | None

    feedbacks: Feedbacks | None

    def __init__(
        self,
        entity: str,
        project: str,
        query: Mapping[str, Any],
        offset: int | None = None,
        limit: int | None = None,
        show_refs: bool = False,
    ):
        self.client = weave_client_context.require_weave_client()
        self.entity = entity
        self.project = project

        self.show_refs = show_refs
        self._query = query
        self.offset = offset
        self.limit = limit

        self.feedbacks = None

    def __iter__(self) -> Iterator[Feedback]:
        yield from self.execute()

    def __getitem__(self, index: int) -> Feedback:
        return self.execute()[index]

    def __len__(self) -> int:
        return len(self.execute())

    def refresh(self) -> Feedbacks:
        sort_by: list[feedback_query_params.SortBy] = [
            {
                "field": "created_at",
                "direction": "asc",
            },
        ]
        response = self.client.server.feedback_query(
            {
                "project_id": to_project_id(self.entity, self.project),
                "fields": None,
                "query": cast(feedback_query_params.Query, self._query),
                "sort_by": sort_by,
                "limit": self.limit,
                "offset": self.offset,
            }
        )
        # Response is dicts because API allows user to specify fields, but we don't
        # expose that in this Python API.
        return Feedbacks(self.show_refs, (Feedback(**r) for r in response.result))

    def execute(self) -> Feedbacks:
        if self.feedbacks is not None:
            return self.feedbacks
        self.feedbacks = self.refresh()
        return self.feedbacks

    def refs(self) -> Refs:
        return self.execute().refs()

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:  # noqa: PLW3201
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text("FeedbackQuery(...)")
        else:
            self.execute()
            assert self.feedbacks is not None
            if len(self.feedbacks) == 1:
                p.text(pydantic_util.model_to_str(self.feedbacks[0]))
            else:
                table = self.feedbacks.as_rich_table()
                p.text(pydantic_util.table_to_str(table))


class RefFeedbackQuery(FeedbackQuery):
    """Object for interacting with feedback associated with a particular ref."""

    weave_ref: str
    _parsed_ref: AnyRef

    def __init__(self, ref: str) -> None:
        parsed_ref = Ref.parse_uri(ref)
        query = {
            "$expr": {
                "$eq": [
                    {"$getField": "weave_ref"},
                    {"$literal": ref},
                ],
            }
        }
        super().__init__(
            entity=parsed_ref.entity,
            project=parsed_ref.project,
            query=query,
        )
        self.weave_ref = ref
        self._parsed_ref = parsed_ref

    def _create(self, freq: FeedbackCreateParams) -> str:
        response = self.client.server.feedback_create(freq)
        self.feedbacks = None  # Clear cache
        return response.id

    def _add(
        self,
        feedback_type: str,
        payload: dict[str, Any],
        creator: str | None,
        annotation_ref: str | None = None,
    ) -> str:
        if annotation_ref:
            try:
                ObjectRef.parse_uri(annotation_ref)
            except TypeError:
                raise TypeError(
                    "annotation_ref must be a valid object ref, eg weave:///<entity>/<project>/object/<name>:<digest>"
                ) from None
        freq = feedback_create_params(
            project_id=to_project_id(self.entity, self.project),
            weave_ref=self.weave_ref,
            feedback_type=feedback_type,
            payload=payload,
            creator=creator,
            annotation_ref=annotation_ref or None,
        )
        return self._create(freq)

    def _add_agent_reaction(self, emoji: str, creator: str | None) -> str:
        return self._create(
            feedback_create_params(
                project_id=to_project_id(self.entity, self.project),
                weave_ref=self.weave_ref,
                feedback_type=AGENT_USER_FEEDBACK_TYPE,
                scorer_tags=[emoji],
                scorer_tag_reasons={emoji: AGENT_REACTION_REASON},
                scorer_tag_confidences={emoji: 1.0},
                # Mirror the tag so wandb.reaction.1 consumers can read it too.
                payload={"emoji": emoji, "scorer_tags": [emoji]},
                creator=creator,
            )
        )

    def add(
        self,
        feedback_type: str,
        payload: dict[str, Any] | None = None,
        creator: str | None = None,
        annotation_ref: str | None = None,
        **kwargs: dict[str, Any],
    ) -> str:
        """Add feedback to the ref.

        feedback_type: A string identifying the type of feedback. The "wandb." prefix is reserved.
        creator: The name to display for the originator of the feedback.
        """
        _validate_feedback_type(feedback_type, annotation_ref)
        feedback = {}
        feedback.update(payload or {})
        feedback.update(kwargs)
        return self._add(feedback_type, feedback, creator, annotation_ref)

    def add_reaction(self, emoji: str, creator: str | None = None) -> str:
        """Add an emoji reaction, written as the type the target's UI renders."""
        if isinstance(
            self._parsed_ref, (AgentSpanRef, AgentTurnRef, AgentConversationRef)
        ):
            return self._add_agent_reaction(emoji, creator)
        return self._add(
            REACTION_FEEDBACK_TYPE,
            {
                "emoji": emoji,
            },
            creator=creator,
        )

    def add_note(self, note: str, creator: str | None = None) -> str:
        return self._add(
            NOTE_FEEDBACK_TYPE,
            {
                "note": note,
            },
            creator=creator,
        )

    def purge(self, feedback_id: str) -> None:
        # TODO: For safety we should also specify the weave_ref here
        #       But we need to loosen up the query restrictions in the
        #       backend to support that first.
        query = {
            "$expr": {
                "$eq": [
                    {"$getField": "id"},
                    {"$literal": feedback_id},
                ],
            }
        }
        self.client.server.feedback_purge(
            {
                "project_id": to_project_id(self.entity, self.project),
                "query": cast(feedback_purge_params.Query, query),
            }
        )
        self.feedbacks = None  # Clear cache


def feedback_create_params(
    *,
    project_id: str,
    weave_ref: str,
    feedback_type: str,
    payload: dict[str, Any],
    creator: str | None = None,
    annotation_ref: str | None = None,
    runnable_ref: str | None = None,
    call_ref: str | None = None,
    scorer_tags: list[str] | None = None,
    scorer_tag_reasons: dict[str, str] | None = None,
    scorer_tag_confidences: dict[str, float] | None = None,
) -> FeedbackCreateParams:
    """A feedback create request with every field, in a fixed order.

    The scorer and span fields get the server's defaults unless given, and batched
    feedback goes out in this key order.
    """
    return {
        "project_id": project_id,
        "weave_ref": weave_ref,
        "creator": creator,
        "feedback_type": feedback_type,
        "payload": payload,
        "annotation_ref": annotation_ref,
        "runnable_ref": runnable_ref,
        "call_ref": call_ref,
        "scorer_tags": scorer_tags or [],
        "scorer_tag_reasons": scorer_tag_reasons or {},
        "scorer_tag_confidences": scorer_tag_confidences or {},
        "scorer_ratings": {},
        "scorer_rating_reasons": {},
        "scorer_rating_confidences": {},
        "span_agent_name": "",
        "span_agent_version": "",
        "span_status_code": "UNSET",
        "span_conversation_id": "",
        "span_trace_id": "",
        "scorer_trace_id": "",
    }


def _validate_feedback_type(feedback_type: str, annotation_ref: str | None) -> None:
    if feedback_type.startswith("wandb.") and not annotation_ref:
        raise ValueError(
            'Feedback type cannot start with "wandb", it is reserved for annotation feedback.'
            "Provide an annotation_ref <entity/project/object/name:digest> to add annotation feedback."
        )
    elif not feedback_type.startswith("wandb.annotation.") and annotation_ref:
        raise ValueError(
            "To add annotation feedback, feedback_type must conform to the format: 'wandb.annotation.<name>'."
        )
