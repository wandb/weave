import logging
import typing
import uuid

from .wandb_lite_run import InMemoryLazyLiteRun

from .. import runfiles_wandb
from .. import storage
from .. import weave_types
from .. import artifact_base


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

        def ref_persister_artifact(
            type: weave_types.Type, refs: typing.Iterable[artifact_base.ArtifactRef]
        ) -> artifact_base.Artifact:
            # Save all the reffed objects into the new artifact.
            for mem_ref in refs:
                if mem_ref.path is not None and mem_ref._type is not None:
                    # Hack: add a random salt to the end (i really want content addressing here)
                    # but this is a quick fix to avoid collisions
                    path = mem_ref.path + "-" + str(uuid.uuid4())
                    artifact.set(path, mem_ref._type, mem_ref._obj)
            return artifact

        res = storage.to_python(obj, None, ref_persister_artifact)
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
        splits = table_name.split("/")
        if len(splits) == 1:
            pass
        elif len(splits) == 2:
            if project_name is not None:
                raise ValueError(
                    f"Cannot specify project_name and table_name with '/' in it: {table_name}"
                )
            project_name = splits[0]
            table_name = splits[1]
        elif len(splits) == 3:
            if project_name is not None or entity_name is not None:
                raise ValueError(
                    f"Cannot specify project_name or entity_name and table_name with 2 '/'s in it: {table_name}"
                )
            entity_name = splits[0]
            project_name = splits[1]
            table_name = splits[2]

        # For now, we force the user to specify the entity and project
        # technically, we could infer the entity from the API key, but
        # that tends to confuse users.
        if entity_name is None or entity_name == "":
            raise ValueError(f"Must specify entity_name")
        elif project_name is None or project_name == "":
            raise ValueError(f"Must specify project_name")
        elif table_name is None or table_name == "":
            raise ValueError(f"Must specify table_name")

        self._lite_run = InMemoryLazyLiteRun(
            entity_name, project_name, table_name, "wb_stream_table"
        )

    def log(self, row_or_rows: typing.Union[dict, list[dict]]) -> None:
        if isinstance(row_or_rows, dict):
            row_or_rows = [row_or_rows]

        for row in row_or_rows:
            self._log_row(row)

    def _log_row(self, row: dict) -> None:
        if self._artifact is None:
            uri = runfiles_wandb.WeaveWBRunFilesURI.from_run_identifiers(
                self._lite_run._entity_name,
                self._lite_run._project_name,
                self._lite_run._run_name,
            )
            self._artifact = runfiles_wandb.WandbRunFiles(name=uri.name, uri=uri)
        self._lite_run.log(obj_to_weave(row, self._artifact))  # type: ignore

    def finish(self) -> None:
        self._lite_run.finish()

    def __del__(self) -> None:
        self.finish()


def maybe_history_type_to_weave_type(tc_type: str) -> typing.Optional[weave_types.Type]:
    possible_type = weave_types.type_name_to_type(tc_type)
    if possible_type is not None:
        try:
            return possible_type()
        except Exception as e:
            logging.warning(
                f"StreamTable Type Error: Found type for {tc_type}, but blind construction failed: {e}",
            )
    return None


def is_weave_encoded_history_cell(cell: dict) -> bool:
    return "_weave_type" in cell and "_val" in cell


def from_weave_encoded_history_cell(cell: dict) -> typing.Any:
    if not is_weave_encoded_history_cell(cell):
        raise ValueError(f"Expected weave encoded history cell, got {cell}")
    weave_json = {
        "_type": cell["_weave_type"],
        "_val": cell["_val"],
    }
    return storage.from_python(weave_json)
