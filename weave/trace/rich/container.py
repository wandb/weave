from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from typing import Any, Generic, Optional, TypeVar

from rich.table import Table

from weave.trace.rich import pydantic_util

T = TypeVar("T")


class AbstractRichContainer(ABC, Generic[T]):
    """A container of items that can be displayed as a rich table."""

    item_type: str
    items: list[T]

    def __init__(self, item_type: str, items: Optional[Iterable[T]] = None) -> None:
        self.item_type = item_type
        self.items = list(items) if items else []

    def __getitem__(self, index: int) -> T:
        return self.items[index]

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    @abstractmethod
    def _add_table_columns(self, table: Table) -> None:
        pass

    @abstractmethod
    def _item_to_row(self, item: T) -> list:
        pass

    def as_rich_table(self) -> Table:
        table = Table(show_header=True, header_style="bold cyan")
        self._add_table_columns(table)
        for item in self.items:
            table.add_row(*self._item_to_row(item))
        return table

    def _cycle_repr(self) -> str:
        return f"AbstractContainer[{self.item_type}](...)"

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text(self._cycle_repr())
        else:
            table = self.as_rich_table()
            p.text(pydantic_util.table_to_str(table))
