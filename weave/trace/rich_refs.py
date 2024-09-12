"""Support for a collection of refs."""

from typing import Iterable, Optional

from rich.table import Table

from weave.trace.client_context import weave_client as weave_client_context
from weave.trace.refs import AnyRef, CallRef, parse_uri
from weave.trace.rich_container import AbstractRichContainer
from weave.trace.vals import WeaveObject


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

    # TODO: Perhaps there should be a Calls that extends AbstractRichContainer
    def calls(self) -> list[WeaveObject]:
        client = weave_client_context.require_weave_client()
        objs = []
        for ref in self.call_refs():
            parsed = parse_uri(ref)
            assert isinstance(parsed, CallRef)
            objs.append(client.get_call(parsed.id))
        return objs
