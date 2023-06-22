import typing

from .wandb_lite_run import InMemoryLazyLiteRun

from .. import storage

# from ..weave_types import TypeRegistry


# TODO: Move this into a mapper that can do the storage for files too
def obj_to_weave(obj: typing.Any) -> dict:
    if isinstance(obj, dict):
        return {key: obj_to_weave(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [obj_to_weave(value) for value in obj]
    elif isinstance(obj, tuple):
        return [obj_to_weave(value) for value in obj]
    elif isinstance(obj, set):
        return [obj_to_weave(value) for value in obj]
    elif isinstance(obj, frozenset):
        return [obj_to_weave(value) for value in obj]
    # all primitives
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        return storage.to_python(obj)


class StreamTable:
    def __init__(
        self,
        table_name: str,
        project_name: typing.Optional[str] = None,
        entity_name: typing.Optional[str] = None,
    ):
        self._lite_run = InMemoryLazyLiteRun(
            entity_name, project_name or "stream-tables", table_name, "stream_table"
        )

    def log(self, row_or_rows: typing.Union[dict, list[dict]]) -> None:
        if isinstance(row_or_rows, dict):
            row_or_rows = [row_or_rows]

        for row in row_or_rows:
            self._log_row(row)

    def _log_row(self, row: dict) -> None:
        self._lite_run.log(obj_to_weave(row))

    def finish(self) -> None:
        self._lite_run.finish()

    def __del__(self) -> None:
        self.finish()
