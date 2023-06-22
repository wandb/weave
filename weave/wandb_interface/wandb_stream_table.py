import typing

from .wandb_lite_run import InMemoryLazyLiteRun
from ..weave_types import TypeRegistry


def obj_to_media_type(obj: typing.Any) -> dict:
    obj_type = TypeRegistry.type_of(obj)
    obj_dict = obj_type.instance_to_dict(obj)
    type_dict = obj_type.to_dict()
    return {
        "_type": type_dict,
        **obj_dict,
    }


class StreamTable:
    def __init__(
        self,
        table_name: str,
        project_name: typing.Optional[str] = None,
        entity_name: typing.Optional[str] = None,
    ):
        self._lite_run = InMemoryLazyLiteRun(
            entity_name, project_name, table_name, "stream_table"
        )

    def log(self, row_or_rows: typing.Union[dict, list[dict]]) -> None:
        if isinstance(row_or_rows, dict):
            row_or_rows = [row_or_rows]

        for row in row_or_rows:
            self._log_row(row)

    def _log_row(self, row: dict) -> None:
        weave_row = {key: obj_to_media_type(value) for key, value in row.items()}
        self._lite_run.log(weave_row)

    def finish(self) -> None:
        self._lite_run.finish()

    def __del__(self) -> None:
        self.finish()
