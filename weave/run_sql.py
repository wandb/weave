import typing

from . import graph_client_context


class RunSql:
    _attrs: typing.Any

    def __init__(self, attrs) -> None:
        self._attrs = attrs

    @property
    def id(self):
        return self._attrs["id"]

    @property
    def trace_id(self):
        return self._attrs["trace_id"]

    @property
    def ui_url(self) -> str:
        gc = graph_client_context.require_graph_client()
        return gc.run_ui_url(self)
