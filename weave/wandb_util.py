import typing

from wandb import data_types as wandb_data_types
from wandb.sdk.data_types import video as wandb_sdk_data_types_video
from wandb.sdk.data_types import html as wandb_sdk_data_types_html
from wandb.sdk.data_types import molecule as wandb_sdk_data_types_molecule
from wandb.sdk.data_types import object_3d as wandb_sdk_data_types_object_3d
from wandb.sdk.data_types import plotly as wandb_sdk_data_types_plotly
from wandb.sdk.data_types.helper_types import classes as wandb_sdk_data_types_classes
from wandb.sdk.data_types import _dtypes as wandb_data_types_dtypes

from wandb.sdk.interface import artifacts as wandb_sdk_interface_artifacts

from . import weave_types as types
from . import errors
from . import ops


def weave0_type_json_to_weave1_type(
    old_type_json: typing.Any,
    wb_artifact: typing.Optional[wandb_sdk_interface_artifacts.Artifact],
) -> types.Type:
    return _convert_type(
        wandb_data_types_dtypes.TypeRegistry.type_from_dict(old_type_json, wb_artifact)
    )


# This should ideally match `mediaTable.ts` in Weave0.
def _convert_type(old_type: wandb_data_types_dtypes.Type) -> types.Type:
    is_python_object_type = isinstance(
        old_type, wandb_data_types_dtypes.PythonObjectType
    )
    #
    # Type Type
    #
    if type(old_type) == wandb_data_types_dtypes.Type:
        return types.TypeType()
    #
    # General Types
    #
    elif isinstance(old_type, wandb_data_types_dtypes.AnyType):
        return types.Any()
    elif isinstance(old_type, wandb_data_types_dtypes.UnknownType):
        return types.UnknownType()
    elif isinstance(old_type, wandb_data_types_dtypes.InvalidType):
        return types.Invalid()
    #
    # Primitive Types
    #
    elif isinstance(old_type, wandb_data_types_dtypes.NoneType):
        return types.none_type
    elif isinstance(old_type, wandb_data_types_dtypes.BooleanType):
        return types.Boolean()
    elif isinstance(old_type, wandb_data_types_dtypes.NumberType):
        # TODO: should we try to figure out if its an Int?
        return types.Float()
    elif isinstance(old_type, wandb_data_types_dtypes.StringType):
        return types.String()
    #
    # Special Types
    #
    elif isinstance(old_type, wandb_data_types_dtypes.UnionType):
        return types.UnionType(
            *(_convert_type(old_type) for old_type in old_type.params["allowed_types"])
        )
    elif isinstance(old_type, wandb_data_types_dtypes.ConstType):
        val = old_type.params["val"]
        if old_type.params["is_set"]:
            val = set(val)
        return types.Const(types.TypeRegistry.type_of(val), val)
    #
    # Container Types
    #
    elif isinstance(old_type, wandb_data_types_dtypes.TypedDictType):
        return types.TypedDict(
            {
                prop_name: _convert_type(old_type)
                for prop_name, old_type in old_type.params["type_map"].items()
            }
        )
    elif isinstance(old_type, wandb_data_types_dtypes.ListType):
        return types.List(_convert_type(old_type.params["element_type"]))
    #
    # Domain Types
    #
    elif isinstance(old_type, wandb_data_types_dtypes.TimestampType):
        # TODO: Fix this circular import
        from .ops_domain import wb_domain_types

        return wb_domain_types.Date.WeaveType()  # type: ignore
    elif isinstance(old_type, wandb_data_types_dtypes.NDArrayType):
        # returning None here since the data is serialized as a none. The actual data is stored
        # in the artifact at the path specified in `old_type._params["serialization_path"]`. In Weave0
        # we never attempt to read this data and simply ignore it! For compatibility, we can doe the
        # same here, but in the future we likely want to improve this behavior.
        return types.NoneType()
        # return NumpyArrayType("f", shape=old_type._params.get("shape", (0,)))
    #
    # Media Types
    #
    elif isinstance(old_type, wandb_data_types._ImageFileType) or (
        is_python_object_type and old_type._params.get("class_name") == "Image"
    ):
        return ops.ImageArtifactFileRef.WeaveType()  # type: ignore
    elif isinstance(old_type, wandb_data_types._AudioFileType) or (
        is_python_object_type and old_type._params.get("class_name") == "Audio"
    ):
        return ops.AudioArtifactFileRef.WeaveType()  # type: ignore
    elif isinstance(old_type, wandb_sdk_data_types_html._HtmlFileType) or (
        is_python_object_type and old_type._params.get("class_name") == "Html"
    ):
        return ops.HtmlArtifactFileRef.WeaveType()  # type: ignore
    elif isinstance(old_type, wandb_data_types._BokehFileType) or (
        is_python_object_type and old_type._params.get("class_name") == "Bokeh"
    ):
        return ops.BokehArtifactFileRef.WeaveType()  # type: ignore
    elif isinstance(old_type, wandb_sdk_data_types_video._VideoFileType) or (
        is_python_object_type and old_type._params.get("class_name") == "Video"
    ):
        return ops.VideoArtifactFileRef.WeaveType()  # type: ignore
    elif isinstance(old_type, wandb_sdk_data_types_object_3d._Object3DFileType) or (
        is_python_object_type and old_type._params.get("class_name") == "Object3D"
    ):
        return ops.Object3DArtifactFileRef.WeaveType()  # type: ignore
    elif isinstance(old_type, wandb_sdk_data_types_classes._ClassesIdType):
        # Question: Should we be converting this to a ClassesId type? Maybe a union of const numbers?
        return types.Number()  # type: ignore
    elif is_python_object_type and old_type._params.get("class_name") == "Molecule":
        return ops.MoleculeArtifactFileRef.WeaveType()  # type: ignore
    #
    # Table Types
    #
    elif isinstance(old_type, wandb_data_types._TableType):
        # TODO: this is not implemented in mediaTable.ts, leaving it as a TODO for now
        pass
    elif isinstance(old_type, wandb_data_types._JoinedTableType):
        # TODO: this is not implemented in mediaTable.ts, leaving it as a TODO for now
        pass
    elif isinstance(old_type, wandb_data_types._PartitionedTableType):
        # TODO: this is not implemented in mediaTable.ts, leaving it as a TODO for now
        pass
    elif isinstance(old_type, wandb_data_types._PrimaryKeyType):
        return types.String()
    elif isinstance(old_type, wandb_data_types._ForeignKeyType):
        return types.String()
    elif isinstance(old_type, wandb_data_types._ForeignIndexType):
        return types.Number()
    #
    # Legacy Fallback Types
    #
    elif is_python_object_type:
        return types.UnknownType()
    raise errors.WeaveInternalError(
        "converting old Weave type not yet implemented: %s" % type(old_type)
    )
