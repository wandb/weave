"""Classes for working with feedback on a project or ref level."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

from rich.table import Table

from weave.trace import util
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.refs import parse_object_uri, parse_uri
from weave.trace.rich import pydantic_util
from weave.trace.rich.container import AbstractRichContainer
from weave.trace.rich.refs import Refs
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.query import Query


class Feedbacks(AbstractRichContainer[tsi.Feedback]):
    """A collection of Feedback objects with utilities."""

    show_refs: bool

    def __init__(
        self, show_refs: bool, feedbacks: Iterable[tsi.Feedback] | None = None
    ) -> None:
        super().__init__("Feedback", feedbacks)
        self.show_refs = show_refs

    def refs(self) -> Refs:
        """Return the unique refs associated with these feedbacks."""
        uris = list(dict.fromkeys(feedback.weave_ref for feedback in self.items))
        return Refs(uris)

    def _add_table_columns(self, table: Table) -> None:
        if self.show_refs:
            table.add_column("Ref", overflow="fold")
        table.add_column("Type", justify="center")
        table.add_column("Feedback", overflow="fold")
        table.add_column("Created")
        table.add_column("ID", overflow="fold")
        table.add_column("Creator")

    def _item_to_row(self, item: tsi.Feedback) -> list:
        feedback = item

        typ = feedback.feedback_type
        display_type = typ
        if typ == "wandb.reaction.1":
            display_type = "reaction"
            if util.is_notebook():
                # TODO: Emojis mess up table alignment in Jupyter 😢
                #       maybe there is something else we could do here?
                content = feedback.payload["alias"]
            else:
                content = feedback.payload["emoji"]
        elif typ == "wandb.note.1":
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
    _query: tsi.Query
    offset: int | None
    limit: int | None

    feedbacks: Feedbacks | None

    def __init__(
        self,
        entity: str,
        project: str,
        query: Query,
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

    def __iter__(self) -> Iterator[tsi.Feedback]:
        yield from self.execute()

    def __getitem__(self, index: int) -> tsi.Feedback:
        return self.execute()[index]

    def __len__(self) -> int:
        return len(self.execute())

    def refresh(self) -> Feedbacks:
        sort_by = [
            {
                "field": "created_at",
                "direction": "asc",
            },
        ]
        req = tsi.FeedbackQueryReq(
            project_id=f"{self.entity}/{self.project}",
            query=self._query,
            sort_by=sort_by,
            offset=self.offset,
            limit=self.limit,
        )
        response = self.client.server.feedback_query(req)
        # Response is dicts because API allows user to specify fields, but we don't
        # expose that in this Python API.
        return Feedbacks(self.show_refs, (tsi.Feedback(**r) for r in response.result))

    def execute(self) -> Feedbacks:
        if self.feedbacks is not None:
            return self.feedbacks
        self.feedbacks = self.refresh()
        return self.feedbacks

    def refs(self) -> Refs:
        return self.execute().refs()

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
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

    def __init__(self, ref: str) -> None:
        parsed_ref = parse_uri(ref)
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
            query=Query(**query),
        )
        self.weave_ref = ref

    def _add(
        self,
        feedback_type: str,
        payload: dict[str, Any],
        creator: str | None,
        annotation_ref: str | None = None,
    ) -> str:
        freq = tsi.FeedbackCreateReq(
            project_id=f"{self.entity}/{self.project}",
            weave_ref=self.weave_ref,
            feedback_type=feedback_type,
            payload=payload,
            creator=creator,
        )
        if annotation_ref:
            try:
                parse_object_uri(annotation_ref)
            except TypeError:
                raise TypeError(
                    "annotation_ref must be a valid object ref, eg weave:///<entity>/<project>/object/<name>:<digest>"
                )
            freq.annotation_ref = annotation_ref
        response = self.client.server.feedback_create(freq)
        self.feedbacks = None  # Clear cache
        return response.id

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
        return self._add(
            "wandb.reaction.1",
            {
                "emoji": emoji,
            },
            creator=creator,
        )

    def add_note(self, note: str, creator: str | None = None) -> str:
        return self._add(
            "wandb.note.1",
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
        req = tsi.FeedbackPurgeReq(
            project_id=f"{self.entity}/{self.project}",
            query=Query(**query),
        )
        self.client.server.feedback_purge(req)
        self.feedbacks = None  # Clear cache


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


__docspec__ = [
    Feedbacks,
    FeedbackQuery,
    RefFeedbackQuery,
]
