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
    if type(old_type) == wandb_dtypes.Type:
        return types.Type()
    elif isinstance(old_type, wandb_dtypes.TypedDictType):
        return types.TypedDict(
            {
                prop_name: _convert_type(old_type)
                for prop_name, old_type in old_type.params["type_map"].items()
            }
        )
    elif isinstance(old_type, wandb_dtypes.ListType):
        return types.List(_convert_type(old_type.params["element_type"]))
    elif isinstance(old_type, wandb_dtypes.InvalidType):
        return types.Invalid()
    elif isinstance(old_type, wandb_dtypes.AnyType):
        return types.Any()
    elif isinstance(old_type, wandb_dtypes.UnknownType):
        return types.UnknownType()
    elif isinstance(old_type, wandb_dtypes.TimestampType):
        raise errors.WeaveInternalError(
            "converting old Weave type not yet implemented: %s" % type(old_type)
        )
    elif isinstance(old_type, wandb_dtypes.BooleanType):
        return types.Boolean()
    elif isinstance(old_type, wandb_dtypes.PythonObjectType):
        return types.type_class_type_name(old_type.params["class_name"])
    elif isinstance(old_type, wandb_dtypes.ConstType):
        val = old_type.params["val"]
        if old_type.params["is_set"]:
            val = set(val)
        return types.Const(types.TypeRegistry.type_of(val), val)
    elif isinstance(old_type, wandb_dtypes.NDArrayType):
        raise errors.WeaveInternalError(
            "converting old Weave type not yet implemented: %s" % type(old_type)
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
        return ops.ImageArtifactFileRef.WeaveType()  # type: ignore
    else:
        raise errors.WeaveInternalError(
            "converting old Weave type not yet implemented: %s" % type(old_type)
        )
