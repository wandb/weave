import json
from datetime import datetime
from typing import Any, Collection, Optional

from rich.table import Table
from rich.console import Console

from . import graph_client_context
from weave.trace_server import trace_server_interface as tsi
from weave.trace.refs import parse_uri

class Feedback:

    weave_ref: str
    project_id: str
    items: Optional[list[tsi.Feedback]] = None

    def __init__(self, ref: str) -> None:
        self.weave_ref = ref
        parsed_ref = parse_uri(ref)
        self.project_id = f'{parsed_ref.entity}/{parsed_ref.project}'
        self.client = graph_client_context.require_graph_client()

    def _maybe_fetch(self):
        if self.items is None:
            # TODO: Caching logic
            self.refresh()

    def refresh(self):
        # print('fetching feedback for ' + self.call_id)
        self.items = self.query()

    def __getitem__(self, index):
        self._maybe_fetch()
        return self.items[index]

    def __iter__(self):
        self._maybe_fetch()
        self.current = 0
        return self

    def __next__(self):
        if self.current < len(self.items):
            item = self.items[self.current]
            self.current += 1
            return item
        raise StopIteration

    def __len__(self):
        self._maybe_fetch()
        return len(self.items)

    def add(self, feedback_type: str, payload: dict[str, Any] = None, creator: Optional[str] = None, **kwargs) -> str:
        # This is the public API.
        # It allows specifying kwargs or a dictionary.
        # It prevents use of our prefix.
        # print('adding feedback for ' + self.call_id)
        # creator is a special parameter that gets stored in its own column.
        # Need to specify payload explicitly if you want a creator key.
        if feedback_type.startswith('wandb.'):
            raise ValueError('Feedback type cannot start with "wandb."')
        feedback = {}
        feedback.update(payload or {})
        feedback.update(kwargs)
        return self._add(feedback_type, feedback, creator)

    def _add(self, feedback_type: str, payload: dict[str, Any], creator: Optional[str]) -> str:
        self._maybe_fetch()
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
        return self._add("wandb.reaction.1", {
            "emoji": emoji,
        }, creator=creator)

    def add_note(self, note: str, creator: Optional[str] = None) -> str:
        return self._add("wandb.note.1", {
            "note": note,
        }, creator=creator)

    def query(self,
              *,
              # TODO: filters - user, date range, etc
              # TODO: sort order,
              limit: Optional[int] = None):
        # TODO:
        # filters = [
        #     {
        #         "field": "weave_ref",
        #         "op": "eq",
        #         "value": self.weave_ref,
        #     },
        # ]
        query = {
            '$expr': {
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
        return [tsi.Feedback(**r) for r in response.result]

    def purge(self, feedback_id: str) -> None:
        self.client.server.feedback_purge(tsi.FeedbackPurgeReq(id=feedback_id, project_id=self.project_id))
        self.items = [f for f in self.items if f.id != feedback_id]

    def _as_rich_table(self):
        self._maybe_fetch()
        # TODO: Maybe show reaction summary here
        # TODO: Separate columns for reactions, notes, other?
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Type", justify="center")
        table.add_column("Feedback")
        table.add_column("Created")
        table.add_column("ID")
        table.add_column("Name")
        for feedback in self:
            typ = feedback.feedback_type
            if typ == "wandb.reaction.1":
                content = feedback.payload["emoji"]
            elif typ == "wandb.note.1":
                content = feedback.payload["note"]
            else:
                content = json.dumps(feedback.payload, indent=2)
            name = feedback.creator or feedback.wb_user_id
            if feedback.creator != feedback.wb_user_id:
                name += f" ({feedback.wb_user_id})"
            table.add_row(
                typ,
                content,
                str(feedback.created_at),
                feedback.id,
                name,
            )
        return table

    def __str__(self):
        table = self._as_rich_table()
        console = Console()
        with console.capture() as capture:
            console.print(table)
        x = capture.get()
        return x.strip()

    def _repr_pretty_(self, p, cycle):
        """Show a nicely formatted table in ipython."""
        print()
        print(self)
