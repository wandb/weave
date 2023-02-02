import typing


from . import weave_types as types
from . import errors
from . import ops


class Weave0TypeJson(typing.TypedDict):
    wb_type: str
    params: typing.Any


def weave0_type_json_to_weave1_type(old_type_json: Weave0TypeJson) -> types.Type:
    return _convert_type(old_type_json)


# This should ideally match `mediaTable.ts` in Weave0.
def _convert_type(old_type: Weave0TypeJson) -> types.Type:
    old_type_name = old_type["wb_type"]
    is_python_object_type = old_type_name == "pythonObject" or old_type_name == "object"
    #
    # Type Type
    #
    # TODO is this right?
    if old_type_name == "":
        return types.TypeType()
    #
    # General Types
    #
    elif old_type_name == "any":
        return types.Any()
    elif old_type_name == "unknown":
        return types.UnknownType()
    elif old_type_name == "invalid":
        return types.Invalid()
    #
    # Primitive Types
    #
    elif old_type_name == "none":
        return types.none_type
    elif old_type_name == "boolean":
        return types.Boolean()
    elif old_type_name == "number":
        # TODO: should we try to figure out if its an Int?
        return types.Float()
    elif old_type_name == "string":
        return types.String()
    #
    # Special Types
    #
    elif old_type_name == "union":
        return types.union(
            *(
                _convert_type(old_type)
                for old_type in old_type["params"]["allowed_types"]
            )
        )
    elif old_type_name == "const":
        val = old_type["params"]["val"]
        if old_type["params"]["is_set"]:
            # TODO is_set is wrong... shoudl be enum probably
            val = set(val)
        return types.Const(types.TypeRegistry.type_of(val), val)
    #
    # Container Types
    #
    elif old_type_name == "typedDict" or old_type_name == "dictionary":
        return types.TypedDict(
            {
                prop_name: _convert_type(old_type)
                for prop_name, old_type in old_type["params"]["type_map"].items()
            }
        )
    elif old_type_name == "list":
        return types.List(_convert_type(old_type["params"]["element_type"]))
    #
    # Domain Types
    #
    elif old_type_name == "timestamp":
        return types.Timestamp()
    elif old_type_name == "ndarray":
        # returning None here since the data is serialized as a none. The actual data is stored
        # in the artifact at the path specified in `old_type._params["serialization_path"]`. In Weave0
        # we never attempt to read this data and simply ignore it! For compatibility, we can doe the
        # same here, but in the future we likely want to improve this behavior.
        return types.NoneType()
        # return NumpyArrayType("f", shape=old_type._params.get("shape", (0,)))
    #
    # Media Types
    #
    elif (
        old_type_name == "image-file"
        or old_type_name == "wandb.Image"
        or (is_python_object_type and old_type["params"].get("class_name") == "Image")
    ):
        return ops.ImageArtifactFileRef.WeaveType()  # type: ignore
    elif old_type_name == "audio-file" or (
        is_python_object_type and old_type["params"].get("class_name") == "Audio"
    ):
        return ops.AudioArtifactFileRef.WeaveType()  # type: ignore
    elif old_type_name == "html-file" or (
        is_python_object_type and old_type["params"].get("class_name") == "Html"
    ):
        return ops.HtmlArtifactFileRef.WeaveType()  # type: ignore
    elif old_type_name == "bokeh-file" or (
        is_python_object_type and old_type["params"].get("class_name") == "Bokeh"
    ):
        return ops.BokehArtifactFileRef.WeaveType()  # type: ignore
    elif old_type_name == "video-file" or (
        is_python_object_type and old_type["params"].get("class_name") == "Video"
    ):
        return ops.VideoArtifactFileRef.WeaveType()  # type: ignore
    elif old_type_name == "object3D-file" or (
        is_python_object_type and old_type["params"].get("class_name") == "Object3D"
    ):
        return ops.Object3DArtifactFileRef.WeaveType()  # type: ignore
    elif old_type_name == "classesId" or old_type_name == "wandb.Classes_id":
        # Question: Should we be converting this to a ClassesId type? Maybe a union of const numbers?
        # TODO: yes we should! It can be a pointer to a class set!
        return types.Number()  # type: ignore
    elif is_python_object_type and old_type["params"].get("class_name") == "Molecule":
        return ops.MoleculeArtifactFileRef.WeaveType()  # type: ignore
    #
    # Table Types
    #
    elif old_type_name == "table" or old_type_name == "wandb.Table":
        # TODO: this is not implemented in mediaTable.ts, leaving it as a TODO for now
        pass
    elif old_type_name == "joined-table":
        # TODO: this is not implemented in mediaTable.ts, leaving it as a TODO for now
        pass
    elif old_type_name == "partitioned-table":
        # TODO: this is not implemented in mediaTable.ts, leaving it as a TODO for now
        pass
    elif old_type_name == "primaryKey" or old_type_name == "wandb.TablePrimaryKey":
        return types.String()
    elif old_type_name == "foreignKey" or old_type_name == "wandb.TableForeignKey":
        return types.String()
    elif old_type_name == "foreignIndex" or old_type_name == "wandb.TableForeignIndex":
        return types.Number()
    #
    # Legacy Fallback Types
    #
    elif is_python_object_type:
        return types.UnknownType()
    raise errors.WeaveInternalError(
        "converting old Weave type not yet implemented: %s" % type(old_type)
    )
