import typing

from wandb import data_types as wandb_data_types
from wandb.data_types import _dtypes as wandb_dtypes
from weave.decorators import op

from . import weave_types as types
from . import errors
from . import ops


def weave0_type_json_to_weave1_type(old_type_json: typing.Any) -> types.Type:
    return _convert_type(wandb_dtypes.TypeRegistry.type_from_dict(old_type_json))


def _convert_type(old_type: wandb_dtypes.Type) -> types.Type:
    if isinstance(old_type, wandb_dtypes.TypedDictType):
        return types.TypedDict(
            {
                prop_name: _convert_type(old_type)
                for prop_name, old_type in old_type.params["type_map"].items()
            }
        )
    elif isinstance(old_type, wandb_dtypes.UnionType):
        return types.UnionType(
            *(_convert_type(old_type) for old_type in old_type.params["allowed_types"])
        )
    elif isinstance(old_type, wandb_dtypes.NoneType):
        return types.none_type
    elif isinstance(old_type, wandb_dtypes.NumberType):
        # TODO: should we try to figure out if its an Int?
        return types.Float()
    elif isinstance(old_type, wandb_dtypes.StringType):
        # TODO: should we try to figure out if its an Int?
        return types.String()
    elif isinstance(old_type, wandb_data_types._ImageFileType):
        return ops.ImageFile.WeaveType()
        print("OLD TYPE", old_type)
        raise NotImplementedError
    else:
        raise errors.WeaveInternalError(
            "converting old Weave type not yet implemented: %s" % type(old_type)
        )
