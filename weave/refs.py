"""Support for a collection of refs."""

from typing import Iterable, Optional

from rich.table import Table

from weave.trace.refs import parse_uri, AnyRef, CallRef

from weave.trace.rich_container import AbstractRichContainer


class Refs(AbstractRichContainer[str]):
    """A collection of ref strings with utilities."""

    def __init__(self, refs: Optional[Iterable[str]] = None) -> None:
        super().__init__("Ref", refs)

    def _add_table_columns(self, table: Table) -> None:
        table.add_column("Ref", overflow="fold")

    def _item_to_row(self, item: str) -> list:
        return [item]

    def parsed(self) -> list[AnyRef]:
        return [parse_uri(ref) for ref in self.items]

    def call_refs(self) -> "Refs":
        return Refs(ref for ref in self.items if isinstance(parse_uri(ref), CallRef))
