import typing


from . import weave_types as types
from . import errors
from . import ops
from . import ops_domain


class Weave0TypeJson(typing.TypedDict):
    wb_type: str
    params: typing.Any


def weave0_type_json_to_weave1_type(old_type_json: Weave0TypeJson) -> types.Type:
    return _convert_type(old_type_json)


primary_key_type_names = set(["primaryKey", "wandb.TablePrimaryKey"])
foreign_key_type_names = set(["foreignKey", "wandb.TableForeignKey"])
foreign_index_type_names = set(["foreignIndex", "wandb.TableForeignIndex"])


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
        return types.Number()
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
        # if old_type["params"]["is_set"]:
        # TODO is_set is wrong... should be enum probably
        # val = set(val)
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
    # Once Weave1 is fully launched and we don't have shadow mode, we can
    # uncomment the following block. Unfortunately, Weave0 views this as
    # unknown, and in shadow mode we don't use Weave1's type system.
    # elif (
    #     old_type_name == "pythonObject"
    #     and old_type.get("params", {}).get("class_name") == "Timestamp"
    # ):
    #     return types.Timestamp()
    elif (
        old_type_name == "pythonObject"
        and old_type.get("params", {}).get("class_name") == "datetime64"
    ):
        # This is a bit unfortunate. Weave0 interprets this as a number, then calls
        # something like `number-toTimestamp` on it. In the future, this should return
        # timestamp, but for now we'll just return number. Once we convert to Weave1,
        # we can change this because the frontend will be using this type instead of
        # figuring it out itself.
        return types.Int()
    elif old_type_name == "ndarray":
        # return ops.LegacyTableNDArrayType()
        if old_type.get("params", {}).get("serialization_path") is not None:
            # Just return NoneType. The data is None.
            return types.NoneType()

        # SDK converted the array to a pylist
        return types.List(types.UnknownType())

        # return NumpyArrayType("f", shape=old_type._params.get("shape", (0,)))
    #
    # Media Types
    #
    elif (
        old_type_name == "image-file"
        or old_type_name == "wandb.Image"
        or (is_python_object_type and old_type["params"].get("class_name") == "Image")
    ):
        if "params" not in old_type or "class_map" not in old_type["params"]:
            # This is legacy and fixed in `_patch_legacy_image_file_types``
            return ops.LegacyImageArtifactFileRefType()

        boxLayersType = (
            weave0_type_json_to_weave1_type(old_type["params"]["box_layers"]).val  # type: ignore
            if "box_layers" in old_type["params"]
            else None
        )
        boxScoreKeysType = (
            weave0_type_json_to_weave1_type(old_type["params"]["box_score_keys"]).val  # type: ignore
            if "box_score_keys" in old_type["params"]
            else None
        )
        maskLayersType = (
            weave0_type_json_to_weave1_type(old_type["params"]["mask_layers"]).val  # type: ignore
            if "mask_layers" in old_type["params"]
            else None
        )
        classMapType = (
            weave0_type_json_to_weave1_type(old_type["params"]["class_map"]).val  # type: ignore
            if "class_map" in old_type["params"]
            else None
        )
        return ops.ImageArtifactFileRefType(
            boxLayersType,
            boxScoreKeysType,
            maskLayersType,
            classMapType,
        )
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

    elif old_type_name == "wb_trace_tree":
        return ops_domain.trace_tree.WBTraceTree.WeaveType()  # type: ignore

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
    elif old_type_name in primary_key_type_names:
        return types.String()
    elif old_type_name in foreign_key_type_names:
        return types.String()
    elif old_type_name in foreign_index_type_names:
        return types.Number()
    #
    # Legacy Fallback Types
    #
    elif is_python_object_type:
        return types.UnknownType()
    raise errors.WeaveInternalError(
        "converting old Weave type not yet implemented: %s" % type(old_type)
    )
