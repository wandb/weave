import json
from datetime import datetime
from typing import Any, Collection, Iterable, Iterator, Optional

from rich.console import Console
from rich.table import Table

from . import graph_client_context
from . import util
from weave import pydantic_util
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.query import Query
from weave.trace.refs import parse_uri


class Feedbacks:
    """A collection of feedback items with display utilities."""

    items: list[tsi.Feedback]

    def __init__(self, items: Iterable[tsi.Feedback]) -> None:
        self.items = list(items)

    def __getitem__(self, index: int) -> tsi.Feedback:
        return self.items[index]

    def __iter__(self) -> Iterator[tsi.Feedback]:
        self.current = 0
        return self

    def __next__(self) -> tsi.Feedback:
        if self.current < len(self.items):
            item = self.items[self.current]
            self.current += 1
            return item
        raise StopIteration

    def __len__(self) -> int:
        return len(self.items)

    def as_table(self, include_ref: bool = True) -> Table:
        table = Table(show_header=True, header_style="bold cyan")
        if include_ref:
            table.add_column("Ref", overflow="fold")
        table.add_column("Type", justify="center")
        table.add_column("Feedback", overflow="fold")
        table.add_column("Created")
        table.add_column("ID", overflow="fold")
        table.add_column("Creator")
        for feedback in self.items:
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
            if include_ref:
                row.insert(0, feedback.weave_ref)
            table.add_row(*row)
        return table

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text("Feedbacks(...)")
        elif len(self) == 1:
            p.text(pydantic_util.model_to_str(self.items[0]))
        else:
            table = self.as_table()
            p.text(pydantic_util.table_to_str(table))


class RefFeedback:
    """Object for interacting with feedback associated with a particular ref."""

    weave_ref: str
    project_id: str
    items: Optional[list[tsi.Feedback]] = None

    def __init__(self, ref: str) -> None:
        self.weave_ref = ref
        parsed_ref = parse_uri(ref)
        self.project_id = f"{parsed_ref.entity}/{parsed_ref.project}"
        self.client = graph_client_context.require_graph_client()

    def _maybe_fetch(self) -> None:
        if self.items is None:
            self.refresh()

    def refresh(self) -> None:
        self.items = self._query()

    def __getitem__(self, index: int) -> tsi.Feedback:
        self._maybe_fetch()
        assert self.items is not None
        return self.items[index]

    def __iter__(self) -> Iterator[tsi.Feedback]:
        self._maybe_fetch()
        self.current = 0
        return self

    def __next__(self) -> tsi.Feedback:
        assert self.items is not None
        if self.current < len(self.items):
            item = self.items[self.current]
            self.current += 1
            return item
        raise StopIteration

    def __len__(self) -> int:
        self._maybe_fetch()
        assert self.items is not None
        return len(self.items)

    def add(
        self,
        feedback_type: str,
        payload: Optional[dict[str, Any]] = None,
        creator: Optional[str] = None,
        **kwargs: dict[str, Any],
    ) -> str:
        """Add feedback to the ref.

        feedback_type: A string identifying the type of feedback. The "wandb." prefix is reserved.
        creator: The name to display for the originator of the feedback.
        """
        if feedback_type.startswith("wandb."):
            raise ValueError('Feedback type cannot start with "wandb."')
        feedback = {}
        feedback.update(payload or {})
        feedback.update(kwargs)
        return self._add(feedback_type, feedback, creator)

    def _add(
        self, feedback_type: str, payload: dict[str, Any], creator: Optional[str]
    ) -> str:
        self._maybe_fetch()
        assert self.items is not None
        freq = tsi.FeedbackCreateReq(
            project_id=self.project_id,
            weave_ref=self.weave_ref,
            feedback_type=feedback_type,
            payload=payload,
            creator=creator,
        )
        response = self.client.server.feedback_create(freq)

        # Add to internal items so we don't have to refresh
        feedback = tsi.Feedback(
            **freq.dict(),
            id=response.id,
            created_at=response.created_at,
            wb_user_id=response.wb_user_id,
        )
        self.items.append(feedback)
        return response.id

    def add_reaction(self, emoji: str, creator: Optional[str] = None) -> str:
        return self._add(
            "wandb.reaction.1",
            {
                "emoji": emoji,
            },
            creator=creator,
        )

    def add_note(self, note: str, creator: Optional[str] = None) -> str:
        return self._add(
            "wandb.note.1",
            {
                "note": note,
            },
            creator=creator,
        )

    # TODO: Consider exposing more flexible query options.
    def query(self, limit: Optional[int] = None) -> Feedbacks:
        return Feedbacks(self._query(limit))

    def _query(self, limit: Optional[int] = None) -> list[tsi.Feedback]:
        query = {
            "$expr": {
                "$eq": [
                    {"$getField": "weave_ref"},
                    {"$literal": self.weave_ref},
                ],
            }
        }
        sort_by = [
            {
                "field": "created_at",
                "direction": "asc",
            },
        ]
        req = tsi.FeedbackQueryReq(
            project_id=self.project_id,
            query=query,
            sort_by=sort_by,
            limit=limit,
        )
        response = self.client.server.feedback_query(req)
        # Response is dicts because API allows user to specify fields, but we don't
        # expose that in this Python API.
        return list(tsi.Feedback(**r) for r in response.result)

    def purge(self, feedback_id: str) -> None:
        req = tsi.FeedbackPurgeReq(
            project_id=self.project_id,
            query=Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "id"},
                            {"$literal": feedback_id},
                        ],
                    }
                }
            ),
        )
        self.client.server.feedback_purge(req)
        if self.items:
            self.items = [f for f in self.items if f.id != feedback_id]

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text("RefFeedback(...)")
        else:
            self._maybe_fetch()
            assert self.items is not None
            table = Feedbacks(self.items).as_table(include_ref=False)
            p.text(pydantic_util.table_to_str(table))
