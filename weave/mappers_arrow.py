import json
import pyarrow as pa
import typing

from . import box
from . import mappers
from . import mappers_python_def as mappers_python
from . import mappers_weave
from . import arrow_util
from . import weave_types as types
from . import refs
from . import errors
from . import node_ref
from .language_features.tagging import tagged_value_type, tag_store


class TypedDictToArrowStruct(mappers_python.TypedDictToPyDict):
    def result_type(self):
        fields = []
        for property_key, property_serializer in self._property_serializers.items():
            prop_result_type = property_serializer.result_type()
            fields.append(arrow_util.arrow_field(property_key, prop_result_type))
        return pa.struct(fields)


class ObjectToArrowStruct(mappers_python.ObjectToPyDict):
    def result_type(self):
        fields = []
        for property_key, property_serializer in self._property_serializers.items():
            if property_serializer is not None:
                prop_result_type = property_serializer.result_type()
                fields.append(arrow_util.arrow_field(property_key, prop_result_type))
        return pa.struct(fields)


class TaggedValueToArrowStruct(tagged_value_type.TaggedValueToPy):
    def result_type(self):
        return pa.struct(
            [
                arrow_util.arrow_field("_tag", self._tag_serializer.result_type()),
                arrow_util.arrow_field("_value", self._value_serializer.result_type()),
            ]
        )


class ListToArrowArr(mappers_python.ListToPyList):
    def result_type(self):
        return pa.list_(arrow_util.arrow_field("x", self._object_type.result_type()))


class UnionToArrowUnion(mappers_weave.UnionMapper):
    @property
    def non_none_members(self):
        return [
            m for m in self._member_mappers if not isinstance(m.type, types.NoneType)
        ]

    def result_type(self):
        nullable = False
        non_null_mappers: typing.List[mappers.Mapper] = []
        for member_mapper in self._member_mappers:
            if isinstance(member_mapper.type, types.NoneType):
                nullable = True
            else:
                non_null_mappers.append(member_mapper)
        if not nullable or len(non_null_mappers) > 1:
            fields = [
                pa.field(
                    f"{non_null_mappers[i].type.name}_{i}",
                    non_null_mappers[i].result_type(),
                    nullable,
                )
                for i in range(len(non_null_mappers))
            ]
            return pa.union(fields, mode="sparse")
        return arrow_util.arrow_type_with_nullable(non_null_mappers[0].result_type())

    def type_code_of_type(self, type: types.Type) -> int:
        """Return the arrow type code for the given type."""
        for i, member_mapper in enumerate(self._member_mappers):
            if member_mapper.type.assign_type(type) and type.assign_type(
                member_mapper.type
            ):
                return i
        raise errors.WeaveTypeError(f"Could not find type for {type}")

    def type_code_of_obj(self, obj) -> int:
        """Return the arrow type code for the given object."""
        obj_type = types.TypeRegistry.type_of(obj)
        return self.type_code_of_type(obj_type)

    def apply(self, obj):
        obj_type = types.TypeRegistry.type_of(obj)
        for member_mapper in self._member_mappers:
            if member_mapper.type.assign_type(obj_type):
                return member_mapper.apply(obj)
        raise errors.WeaveTypeError(f"Could not find type for {obj}")


class ArrowUnionToUnion(UnionToArrowUnion):
    def apply(self, obj):
        if self.is_single_object_nullable:
            if obj is None:
                return None
            for mapper in self._member_mappers:
                if not isinstance(mapper.type, types.NoneType):
                    return mapper.apply(obj)
        if not isinstance(obj, pa.UnionScalar):
            raise errors.WeaveTypeError(f"Expected UnionScalar, got {type(obj)}: {obj}")
        mapper = self._member_mappers[obj.type_code]
        return mapper.apply(obj.as_py())


class IntToArrowInt(mappers_python.IntToPyInt):
    def result_type(self):
        return pa.int64()


class BoolToArrowBool(mappers_python.BoolToPyBool):
    def result_type(self):
        return pa.bool_()


class DatetimeToArrowTimestamp(mappers_python.DatetimeToPyDatetime):
    def result_type(self):
        return pa.timestamp("ms", tz="+00:00")


class FloatToArrowFloat(mappers.Mapper):
    def result_type(self):
        return pa.float64()

    def apply(self, obj):
        return obj


class ArrowFloatToFloat(mappers.Mapper):
    def apply(self, obj):
        return obj


class StringToArrowString(mappers_python.StringToPyString):
    def result_type(self):
        return pa.string()


class FunctionToArrowFunction(mappers.Mapper):
    def result_type(self):
        return pa.string()

    def apply(self, obj):
        ref = node_ref.node_to_ref(obj)
        return str(ref)


class ArrowFunctionToFunction(mappers.Mapper):
    def apply(self, obj):
        ref = refs.Ref.from_str(obj)
        return node_ref.ref_to_node(ref)


class NoneToArrowNone(mappers.Mapper):
    def result_type(self):
        return pa.null()


class UnknownToArrowNone(mappers_python.UnknownToPyUnknown):
    def result_type(self):
        return pa.null()


class DefaultToArrow(mappers_python.DefaultToPy):
    def __init__(self, type_: types.Type, mapper, artifact, path=[]):
        self.type = type_
        self._artifact = artifact
        self._path = path

    def result_type(self):
        # TODO: hard-coding for the moment. Need to generalize this.
        # There are two cases, either there's a instance_to_dict() method
        #     in which case we need to know the types of that dict
        #     (this is similar to ObjectType and should be shared somehow).
        # Or we'll use save_instance which return a RefType (which we encode
        #     as a pyarrow string).

        if self.type.name == "run":
            return pa.struct(
                (
                    pa.field("entity_name", pa.string()),
                    pa.field("project_name", pa.string()),
                    pa.field("run_id", pa.string()),
                )
            )
        elif self.type.name == "artifact":
            return pa.struct(
                (
                    pa.field("entity_name", pa.string()),
                    pa.field("project_name", pa.string()),
                    pa.field("artifact_type_name", pa.string()),
                    pa.field("artifact_name", pa.string()),
                )
            )
        elif self.type.name == "panel":
            return pa.struct(
                (
                    pa.field("id", pa.string()),
                    pa.field("input", pa.string()),
                    pa.field("config", pa.string()),
                )
            )
        elif (
            self.type.name == "ndarray"
            or self.type.name == "pil_image"
            or self.type.name == "ArrowArray"
            or self.type.name == "ArrowTable"
            or self.type.name == "ArrowTableGroupBy"
            or self.type.name == "ArtifactEntry"
        ):
            # Ref type
            return pa.string()
        elif self.type.name == "timestamp":
            return pa.timestamp("ms", tz="+00:00")
        elif self.type.name == "type":
            return pa.string()

        raise errors.WeaveInternalError(
            "Type not yet handled by mappers_arrow: %s" % self.type
        )

    def apply(self, obj):
        # Hacking... when its a panel, we need to json dump the node and config
        res = super().apply(obj)
        if self.type.name == "panel":
            res["input"] = json.dumps(res["input"])
            res["config"] = json.dumps(res["config"])
        return res


class DefaultFromArrow(mappers_python.DefaultFromPy):
    def apply(self, obj):
        # Hacking... when its a panel, we need to json load the node and config
        if self.type.name == "panel":
            obj["input"] = json.loads(obj["input"])
            obj["config"] = json.loads(obj["config"])
        return super().apply(obj)


def map_to_arrow_(type, mapper, artifact, path=[]):
    if isinstance(type, types.Const):
        type = type.val_type
    if isinstance(type, types.TypedDict):
        return TypedDictToArrowStruct(type, mapper, artifact, path)
    elif isinstance(type, types.List):
        return ListToArrowArr(type, mapper, artifact, path)
    elif isinstance(type, types.UnionType):
        return UnionToArrowUnion(type, mapper, artifact, path)
    elif isinstance(type, types.ObjectType):
        return ObjectToArrowStruct(type, mapper, artifact, path)
    elif isinstance(type, tagged_value_type.TaggedValueType):
        return TaggedValueToArrowStruct(type, mapper, artifact, path)
    elif isinstance(type, types.Int):
        return IntToArrowInt(type, mapper, artifact, path)
    elif isinstance(type, types.Boolean):
        return BoolToArrowBool(type, mapper, artifact, path)
    elif isinstance(type, types.Float) or isinstance(type, types.Number):
        return FloatToArrowFloat(type, mapper, artifact, path)
    elif isinstance(type, types.String):
        return StringToArrowString(type, mapper, artifact, path)
    elif isinstance(type, types.Datetime):
        return DatetimeToArrowTimestamp(type, mapper, artifact, path)
    elif isinstance(type, types.Function):
        return FunctionToArrowFunction(type, mapper, artifact, path)
    elif isinstance(type, types.NoneType):
        return NoneToArrowNone(type, mapper, artifact, path)
    elif isinstance(type, types.UnknownType):
        return UnknownToArrowNone(type, mapper, artifact, path)
    else:
        return DefaultToArrow(type, mapper, artifact, path)


def map_from_arrow_(type, mapper, artifact, path=[]):
    if isinstance(type, types.TypedDict):
        return mappers_python.TypedDictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, types.List):
        return mappers_python.ListToPyList(type, mapper, artifact, path)
    elif isinstance(type, types.UnionType):
        return ArrowUnionToUnion(type, mapper, artifact, path)
    elif isinstance(type, types.ObjectType):
        return mappers_python.ObjectDictToObject(type, mapper, artifact, path)
    elif isinstance(type, tagged_value_type.TaggedValueType):
        return tagged_value_type.TaggedValueFromPy(type, mapper, artifact, path)
    elif isinstance(type, types.Int):
        return mappers_python.IntToPyInt(type, mapper, artifact, path)
    elif isinstance(type, types.Boolean):
        return mappers_python.BoolToPyBool(type, mapper, artifact, path)
    elif isinstance(type, types.Float) or isinstance(type, types.Number):
        return ArrowFloatToFloat(type, mapper, artifact, path)
    elif isinstance(type, types.String):
        return mappers_python.StringToPyString(type, mapper, artifact, path)
    elif isinstance(type, types.Datetime):
        return mappers_python.PyDatetimeToDatetime(type, mapper, artifact, path)
    elif isinstance(type, types.Function):
        return ArrowFunctionToFunction(type, mapper, artifact, path)
    elif isinstance(type, types.NoneType):
        return mappers_python.NoneToPyNone(type, mapper, artifact, path)
    elif isinstance(type, types.UnknownType):
        return UnknownToArrowNone(type, mapper, artifact, path)
    else:
        return DefaultFromArrow(type, mapper, artifact, path)


map_to_arrow = mappers.make_mapper(map_to_arrow_)
map_from_arrow = mappers.make_mapper(map_from_arrow_)


def map_from_arrow_scalar(value: pa.Scalar, type_: types.Type, artifact):
    if isinstance(type_, types.Const):
        return map_from_arrow_scalar(value, type_.val, artifact)
    if isinstance(type_, (types.Number, types.String, types.Boolean, types.NoneType)):
        return value.as_py()
    elif isinstance(type_, types.List):
        return [map_from_arrow_scalar(v, type_.object_type, artifact) for v in value]
    elif isinstance(type_, tagged_value_type.TaggedValueType):
        val = box.box(map_from_arrow_scalar(value["_value"], type_.value, artifact))
        tag = map_from_arrow_scalar(value["_tag"], type_.tag, artifact)
        return tag_store.add_tags(val, tag)
    elif isinstance(type_, types.TypedDict):
        return {
            k: map_from_arrow_scalar(value[k], type_.property_types[k], artifact)
            for k in type_.property_types
        }
    elif isinstance(type_, types.ObjectType):
        return type_.instance_class(  # type: ignore
            **map_from_arrow_scalar(
                value, types.TypedDict(type_.property_types()), artifact
            ),
        )
    elif isinstance(type_, types.UnionType):
        if type_.is_simple_nullable():
            if pa.compute.is_null(value).as_py():
                return None
            return map_from_arrow_scalar(value, types.non_none(type_), artifact)
        else:
            # we have a real union type
            type_code = value.type_code
            current_type = type_.members[type_code]
            return map_from_arrow_scalar(value.value, current_type, artifact)
    elif isinstance(type_, types.Function):
        obj: str = value.as_py()
        ref = refs.Ref.from_str(obj)
        return node_ref.ref_to_node(ref)
    else:
        # default
        obj = value.as_py()
        if isinstance(obj, dict):
            return type_.instance_from_dict(obj)
        # else its a ref string
        # TODO: this does not use self.artifact, can we just drop it?
        # Do we need the type so we can load here? No...
        if ":" in obj:
            ref = refs.Ref.from_str(obj)
            # Note: we are forcing type here, because we already know it
            # We don't save the types for every file in a remote artifact!
            # But you can still reference them, because you have to get that
            # file through an op, and therefore we know the type?
            ref._type = type_
            return ref.get()
        return refs.LocalArtifactRef.from_local_ref(artifact, obj, type_).get()
