from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.table import Table

from weave.trace.api import publish as weave_publish

# from weave.trace_server.interface.builtin_object_classes.saved_view import (
#     CallsFilter,
#     Column,
#     Filter,
#     Filters,
#     Pin,
#     SortBy,
#     SortDirection,
# )
from weave.trace.api import ref as weave_ref
from weave.trace.context import weave_client_context
from weave.trace.refs import ObjectRef
from weave.trace.rich import pydantic_util
from weave.trace_server.interface.builtin_object_classes.dashboard import (
    Dashboard as DashboardBase,
)


class Dashboard:
    """A fluent-style class for working with Dashboard objects."""

    base: DashboardBase
    ref: ObjectRef | None = None

    def __init__(self, label: str = "Dashboard") -> None:
        self.base = DashboardBase(
            # view_type=view_type,
            label=label,
            # definition={},
        )

    @property
    def entity(self) -> str | None:
        if self.ref:
            return self.ref.entity
        client = weave_client_context.get_weave_client()
        return client.entity if client else None

    @property
    def project(self) -> str | None:
        if self.ref:
            return self.ref.project
        client = weave_client_context.get_weave_client()
        return client.project if client else None

    @property
    def name(self) -> str:
        return self.base.label

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text("SavedView(...)")
        else:
            p.text(self.to_rich_table_str())

    def to_rich_table_str(self) -> str:
        table = Table(show_header=False)
        table.add_column("Key", justify="right", style="bold cyan")
        table.add_column("Value")
        table.add_row("Name", self.name)
        if self.base.description is not None:
            table.add_row("Description", self.base.description)
        if self.ref:
            table.add_row("Ref", self.ref.uri())
        return pydantic_util.table_to_str(table)

    def __str__(self) -> str:
        return self.to_rich_table_str()

    def save(self) -> Dashboard:
        """Publish the dashboard to the server."""
        name = self.base.name
        if name is None:
            name = (
                datetime.now()
                .isoformat()
                .replace("T", "_")
                .replace(":", "-")
                .replace(".", "-")[:-1]
            )
        self.ref = weave_publish(self.base, name)
        return self

    @classmethod
    def load(cls, ref: str) -> Dashboard:
        obj_ref = weave_ref(ref)
        base = obj_ref.get()
        instance = cls.__new__(cls)
        instance.ref = obj_ref
        instance.base = base
        return instance
