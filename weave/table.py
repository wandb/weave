from typing import Optional, Iterator

from weave.trace_server.refs import Ref


class Table:
    ref: Optional[Ref]

    def __init__(self, rows: list) -> None:
        self.rows = rows
        self.ref = None

    def __iter__(self) -> Iterator:
        return iter(self.rows)
