import typing


from .wandb_lite_run import InMemoryLazyLiteRun

from ..ops_domain import wb_util
from .. import runfiles_wandb
from .. import artifact_mem
from .. import storage


def obj_to_weave(obj: typing.Any, artifact: runfiles_wandb.WandbRunFiles) -> typing.Any:
    def recurse(obj: typing.Any) -> typing.Any:
        return obj_to_weave(obj, artifact)

    if isinstance(obj, dict):
        return {key: recurse(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [recurse(value) for value in obj]
    elif isinstance(obj, tuple):
        return [recurse(value) for value in obj]
    elif isinstance(obj, set):
        return [recurse(value) for value in obj]
    elif isinstance(obj, frozenset):
        return [recurse(value) for value in obj]
    # all primitives
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        res = storage.to_python(obj, ref_art_constructor=lambda x, y: artifact)
        type_name = res.get("_type", {}).get("type")
        if type_name is None:
            raise ValueError(f"Could not serialize object of type {type(obj)}")

        # Ugg - gorilla only know how to handle plain string types
        return {"_type": type_name, "_weave_type": res["_type"], "_val": res["_val"]}


class StreamTable:
    _artifact: typing.Optional[runfiles_wandb.WandbRunFiles] = None

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
        if self._artifact is None:
            self._artifact = wb_util.filesystem_runfiles_from_run_path(
                wb_util.RunPath(
                    entity_name=self._lite_run._entity_name,
                    project_name=self._lite_run._project_name,
                    run_name=self._lite_run.run.id,
                )
            )
        self._lite_run.log(obj_to_weave(row, self._artifact))  # type: ignore

    def finish(self) -> None:
        self._lite_run.finish()

    def __del__(self) -> None:
        self.finish()
