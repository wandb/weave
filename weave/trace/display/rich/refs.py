"""Support for a collection of refs."""

from collections.abc import Iterable

from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.display import display
from weave.trace.display.rich.container import AbstractRichContainer
from weave.trace.refs import AnyRef, CallRef, Ref
from weave.trace.vals import WeaveObject


class Refs(AbstractRichContainer[str]):
    """A collection of ref strings with utilities."""

    def __init__(self, refs: Iterable[str] | None = None) -> None:
        super().__init__("Ref", refs)

    def _add_table_columns(self, table: display.Table) -> None:
        table.add_column("Ref", overflow="fold")

    def _item_to_row(self, item: str) -> list:
        return [item]

    def parsed(self) -> list[AnyRef]:
        return [Ref.parse_uri(ref) for ref in self.items]

    def call_refs(self) -> "Refs":
        return Refs(
            ref for ref in self.items if isinstance(Ref.parse_uri(ref), CallRef)
        )

    # TODO: Perhaps there should be a Calls that extends AbstractRichContainer
    def calls(self) -> list[WeaveObject]:
        client = weave_client_context.require_weave_client()
        objs = []
        for ref in self.call_refs():
            parsed = Ref.parse_uri(ref)
            assert isinstance(parsed, CallRef)
            objs.append(client.get_call(parsed.id))
        return objs
