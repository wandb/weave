import typing
from .wbmedia import TableClientArtifactFileRef, TableRunFileRef
from .. import weave_types as types

from dataclasses import dataclass


@dataclass
class RunPath:
    entity_name: str
    project_name: str
    run_name: str


def process_run_dict_obj(run_dict, run_path: typing.Optional[RunPath] = None):
    return {k: _process_run_dict_item(v, run_path) for k, v in run_dict.items()}


def _process_run_dict_item(val, run_path: typing.Optional[RunPath] = None):
    if isinstance(val, dict) and "_type" in val and val["_type"] == "table-file":
        if "artifact_path" in val:
            return TableClientArtifactFileRef(val["artifact_path"])
        elif "path" in val and run_path is not None:
            return TableRunFileRef(
                run_path.entity_name,
                run_path.project_name,
                run_path.run_name,
                val["path"],
            )
    return val


def process_run_dict_type(run_dict):
    return types.TypedDict(
        {k: _process_run_dict_item_type(v) for k, v in run_dict.items()}
    )


def _process_run_dict_item_type(val):
    if isinstance(val, dict) and "_type" in val and val["_type"] == "table-file":
        if "artifact_path" in val:
            return TableClientArtifactFileRef.WeaveType()
        else:
            return TableRunFileRef.WeaveType()

    return types.TypeRegistry.type_of(val)
