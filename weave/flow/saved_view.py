from datetime import datetime
from typing import Any

from weave.trace.api import publish as weave_publish
from weave.trace.api import ref as weave_ref
from weave.trace_server.interface.builtin_object_classes.saved_view import (
    Filter,
    Filters,
    Pin,
    SortClause,
    SortDirection,
)
from weave.trace_server.interface.builtin_object_classes.saved_view import (
    SavedView as SavedViewBase,
)

DEFAULT_PIN = Pin(left=["CustomCheckbox", "op_name"], right=[])
DEFAULT_FILTER = Filters(items=[], logicOperator="and")

OPERATOR_MAP = {
    "equals": "(string): equals",
}
OPERATOR_MAP_INV = {v: k for k, v in OPERATOR_MAP.items()}


class SavedView:
    """A fluent-style class for working with SavedView objects."""

    base: SavedViewBase

    def __init__(self, table: str, label: str) -> None:
        self.base = SavedViewBase(
            table=table,
            label=label,
            definition={},
        )

    def rename(self, label: str) -> "SavedView":
        self.base.label = label
        return self

    def add_filter(self, field: str, operator: str, value: Any) -> "SavedView":
        if not self.base.definition.filters:
            self.base.definition.filters = DEFAULT_FILTER.copy()
        assert self.base.definition.filters is not None
        op = OPERATOR_MAP.get(operator)
        if not op:
            raise ValueError(f"Operator {operator} not supported")
        next_id = len(self.base.definition.filters.items)
        filter = Filter(id=next_id, field=field, operator=op, value=value)
        self.base.definition.filters.items.append(filter)
        return self

    def add_sort(self, field: str, sort: SortDirection) -> "SavedView":
        if self.base.definition.sort is None:
            self.base.definition.sort = []
        clause = SortClause(field=field, sort=sort)
        self.base.definition.sort.append(clause)
        return self

    def sort_by(self, field: str, sort: SortDirection) -> "SavedView":
        self.base.definition.sort = []
        return self.add_sort(field, sort)

    def show_column(self, col_name: str) -> "SavedView":
        if not self.base.definition.cols:
            self.base.definition.cols = {}
        self.base.definition.cols[col_name] = True
        return self

    def hide_column(self, col_name: str) -> "SavedView":
        if not self.base.definition.cols:
            self.base.definition.cols = {}
        self.base.definition.cols[col_name] = False
        return self

    def pin_column_left(self, col_name: str) -> "SavedView":
        if not self.base.definition.pin:
            self.base.definition.pin = DEFAULT_PIN.copy()
        assert self.base.definition.pin is not None
        if col_name in self.base.definition.pin.right:
            self.base.definition.pin.right.remove(col_name)
        if col_name not in self.base.definition.pin.left:
            self.base.definition.pin.left.append(col_name)
        return self

    def pin_column_right(self, col_name: str) -> "SavedView":
        if not self.base.definition.pin:
            self.base.definition.pin = DEFAULT_PIN.copy()
        assert self.base.definition.pin is not None
        if col_name in self.base.definition.pin.left:
            self.base.definition.pin.left.remove(col_name)
        if col_name not in self.base.definition.pin.right:
            self.base.definition.pin.right.append(col_name)
        return self

    def unpin_column(self, col_name: str) -> "SavedView":
        if not self.base.definition.pin:
            self.base.definition.pin = DEFAULT_PIN.copy()
        assert self.base.definition.pin is not None
        if col_name in self.base.definition.pin.left:
            self.base.definition.pin.left.remove(col_name)
        elif col_name in self.base.definition.pin.right:
            self.base.definition.pin.right.remove(col_name)
        return self

    def page_size(self, page_size: int) -> "SavedView":
        self.base.definition.page_size = page_size
        return self

    @property
    def name(self) -> str:
        return self.base.label

    def __str__(self) -> str:
        parts = []
        parts.append(f"SavedView '{self.name}'")

        if self.base.definition.filters and self.base.definition.filters.items:
            filter_strs = []
            for f in self.base.definition.filters.items:
                filter_strs.append(f"{f.field} {f.operator} {f.value}")
            parts.append(f"Filters: {', '.join(filter_strs)}")

        if self.base.definition.sort:
            sort_strs = []
            for s in self.base.definition.sort:
                sort_strs.append(f"{s.field} {s.sort}")
            parts.append(f"Sort: {', '.join(sort_strs)}")

        if self.base.definition.cols:
            shown = [
                col for col, visible in self.base.definition.cols.items() if visible
            ]
            hidden = [
                col for col, visible in self.base.definition.cols.items() if not visible
            ]
            if shown:
                parts.append(f"Shown columns: {', '.join(shown)}")
            if hidden:
                parts.append(f"Hidden columns: {', '.join(hidden)}")

        if self.base.definition.pin:
            if self.base.definition.pin.left:
                parts.append(
                    f"Left-pinned columns: {', '.join(self.base.definition.pin.left)}"
                )
            if self.base.definition.pin.right:
                parts.append(
                    f"Right-pinned columns: {', '.join(self.base.definition.pin.right)}"
                )

        if self.base.definition.page_size:
            parts.append(f"Page size: {self.base.definition.page_size}")

        return "\n".join(parts)

    def save(self) -> None:
        name = self.base.name
        if name is None:
            formatted_now = (
                datetime.now()
                .isoformat()
                .replace("T", "_")
                .replace(":", "-")
                .replace(".", "-")[:-1]
            )
            name = f"{self.base.table}_{formatted_now}"
        weave_publish(self.base, name)

    @classmethod
    def load(cls, ref: str) -> "SavedView":
        base = weave_ref(ref).get()
        instance = cls.__new__(cls)
        instance.base = base
        return instance

    # TODO: Where should we put method to query SavedViews?
    # TODO: View deletion
