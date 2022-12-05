from .wbmedia import TableClientArtifactFileRef
from .. import weave_types as types


def process_run_dict_obj(run_dict):
    return {k: _process_run_dict_item(v) for k, v in run_dict.items()}


def _process_run_dict_item(val):
    if isinstance(val, dict) and "_type" in val and val["_type"] == "table-file":
        return TableClientArtifactFileRef(val["artifact_path"])
    return val


def process_run_dict_type(run_dict):
    return types.TypedDict(
        {k: _process_run_dict_item_type(v) for k, v in run_dict.items()}
    )


def _process_run_dict_item_type(val):
    if isinstance(val, dict) and "_type" in val and val["_type"] == "table-file":
        return TableClientArtifactFileRef.WeaveType()
    return types.TypeRegistry.type_of(val)
