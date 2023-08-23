import json
import pyarrow as pa
import typing
from contextlib import contextmanager

from . import box
from . import mappers
from . import mappers_python_def as mappers_python
from . import mappers_weave
from . import arrow_util
from . import weave_types as types
from . import ref_base
from . import errors
from . import node_ref
from . import artifact_base
from .language_features.tagging import tagged_value_type
import contextvars

from . import partial_object


_in_tagging_context = contextvars.ContextVar("in_tagging_context", default=False)


@contextmanager
def _strings_as_dictionaries():
    token = _in_tagging_context.set(True)
    try:
        yield
    finally:
        _in_tagging_context.reset(token)


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


class StringToArrow(mappers_python.StringToPyString):
    def result_type(self):
        if _in_tagging_context.get():
            return pa.dictionary(pa.int64(), pa.string(), False)
        return pa.string()


class TaggedValueToArrowStruct(tagged_value_type.TaggedValueToPy):
    def result_type(self):
        with _strings_as_dictionaries():
            tag_type = self._tag_serializer.result_type()
        value_type = self._value_serializer.result_type()

        return pa.struct(
            [
                arrow_util.arrow_field("_tag", tag_type),
                arrow_util.arrow_field("_value", value_type),
            ]
        )


class ListToArrowArr(mappers_python.ListToPyList):
    def result_type(self):
        # It is important to use `item` here since pyarrow auto assigns the
        # inner field name of a list to `item`. Anything else can cause issues
        # with concatenation or other pyarrow operations that need type
        # equality.
        return pa.list_(arrow_util.arrow_field("item", self._object_type.result_type()))


class UnionToArrowUnion(mappers_weave.UnionMapper):
    def __init__(self, type_, mapper, artifact, path=[]):
        super().__init__(type_, mapper, artifact, path)
        if not self.is_single_object_nullable:
            self._type_codes: dict[types.Type, int] = {}
            self._type_code_to_member_mapper: dict[int, mappers.Mapper] = {}

            i: int = 0
            for member_mapper in self._member_mappers:
                member_type = member_mapper.type
                if isinstance(member_type, types.NoneType):
                    continue
                self._type_codes[member_type] = i
                self._type_code_to_member_mapper[i] = member_mapper
                i += 1

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
                    str(i),
                    non_null_mappers[i].result_type(),
                    nullable,
                )
                for i in range(len(non_null_mappers))
            ]
            return pa.union(fields, mode="dense")
        return arrow_util.arrow_type_with_nullable(non_null_mappers[0].result_type())

    def type_code_of_type(self, type: types.Type) -> int:
        """Return the arrow type code for the given type."""
        if self.is_single_object_nullable:
            raise errors.WeaveTypeError(
                "Cannot get type code of type in a union that is nullable"
            )
        elif isinstance(type, types.NoneType):
            raise errors.WeaveTypeError("Cannot get type code of NoneType")
        else:
            try:
                return self._type_codes[type]
            except KeyError:
                for member_type, member_type_code in self._type_codes.items():
                    if not isinstance(
                        types.merge_types(member_type, type), types.UnionType
                    ):
                        return member_type_code
                raise errors.WeaveTypeError(f"Could not find type code for {type}")

    def type_code_of_obj(self, obj) -> int:
        """Return the arrow type code for the given object."""
        obj_type = types.TypeRegistry.type_of(obj)
        return self.type_code_of_type(obj_type)

    def mapper_of_type_code(self, type_code: int) -> mappers.Mapper:
        """Return the mapper for the given type code."""
        if self.is_single_object_nullable:
            raise errors.WeaveTypeError(
                "Cannot get mapper of type code in a union that is nullable"
            )
        try:
            return self._type_code_to_member_mapper[type_code]
        except KeyError:
            raise errors.WeaveTypeError(
                f"Could not find mapper for type code {type_code}"
            )

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


class TimestampToArrowTimestamp(mappers_python.TimestampToPyTimestamp):
    def result_type(self):
        return pa.timestamp("ms", tz="UTC")


class FloatToArrowFloat(mappers.Mapper):
    def result_type(self):
        return pa.float64()

    def apply(self, obj):
        return obj


class ArrowFloatToFloat(mappers.Mapper):
    def apply(self, obj):
        return obj


class ArrowStringToString(mappers.Mapper):
    def apply(self, obj):
        return obj


class FunctionToArrowFunction(mappers.Mapper):
    def result_type(self):
        return pa.string()

    def apply(self, obj):
        ref = node_ref.node_to_ref(obj)
        return str(ref)


class ArrowFunctionToFunction(mappers.Mapper):
    def apply(self, obj):
        ref = ref_base.Ref.from_str(obj)
        return node_ref.ref_to_node(ref)


class NoneToArrowNone(mappers.Mapper):
    def result_type(self):
        return pa.null()


class UnknownToArrowNone(mappers_python.UnknownToPyUnknown):
    def result_type(self):
        return pa.null()


class ArrowDateTimeToDateTime(mappers.Mapper):
    def apply(self, obj):
        return obj


class DefaultToArrow(mappers_python.DefaultToPy):
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
            self.type.name == "WeaveNDArray"
            or self.type.name == "pil_image"
            or self.type.name == "ArrowArray"
            or self.type.name == "ArrowTable"
            or self.type.name == "FilesystemArtifact"
            or self.type.name == "file"
        ):
            # Ref type
            return pa.string()
        elif self.type.name == "timestamp":
            return pa.timestamp("ms", tz="+00:00")
        elif self.type.name == "date":
            return pa.timestamp("ms", tz="+00:00")
        elif self.type.name == "type":
            return pa.string()
        elif self.type.name == "ndarray":
            return pa.null()

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


class ArrowToArrowWeaveListOrPylist(mappers_python.ListToPyList):
    def apply(self, obj):
        from .ops_arrow import arrow

        if isinstance(self.type, arrow.ArrowWeaveListType):
            # we're already mapped - no need to go further
            return obj

        return super().apply(obj)


class GQLHasKeysToArrowStruct(mappers_python.GQLClassWithKeysToPyDict):
    def result_type(self):
        return pa.struct(
            [
                pa.field(key, self._property_serializers[key].result_type())
                for key in self.type.keys
            ]
        )

    def as_typeddict_mapper(self):
        typed_dict_type = types.TypedDict(self.type.keys)
        return TypedDictToArrowStruct(
            typed_dict_type, self.mapper, self._artifact, self.path
        )


def map_to_arrow_(
    type, mapper, artifact: artifact_base.Artifact, path=[], mapper_options=None
):
    from .ops_arrow import arrow

    if isinstance(type, types.Const):
        type = type.val_type
    if isinstance(type, types.TypedDict):
        return TypedDictToArrowStruct(type, mapper, artifact, path)
    elif isinstance(type, types.List) or isinstance(type, arrow.ArrowWeaveListType):
        return ListToArrowArr(type, mapper, artifact, path)
    elif isinstance(type, types.UnionType):
        return UnionToArrowUnion(type, mapper, artifact, path)
    elif isinstance(type, partial_object.PartialObjectType):
        return GQLHasKeysToArrowStruct(type, mapper, artifact, path)
    elif isinstance(type, types.ObjectType):
        return ObjectToArrowStruct(type, mapper, artifact, path)
    elif isinstance(type, tagged_value_type.TaggedValueType):
        return TaggedValueToArrowStruct(type, mapper, artifact, path)  # type: ignore
    elif isinstance(type, types.Int):
        return IntToArrowInt(type, mapper, artifact, path)
    elif isinstance(type, types.Boolean):
        return BoolToArrowBool(type, mapper, artifact, path)
    elif isinstance(type, types.Float) or isinstance(type, types.Number):
        return FloatToArrowFloat(type, mapper, artifact, path)
    elif isinstance(type, types.String):
        return StringToArrow(type, mapper, artifact, path)
    elif isinstance(type, types.Timestamp):
        return TimestampToArrowTimestamp(type, mapper, artifact, path)
    elif isinstance(type, types.Function):
        return FunctionToArrowFunction(type, mapper, artifact, path)
    elif isinstance(type, types.NoneType):
        return NoneToArrowNone(type, mapper, artifact, path)
    elif isinstance(type, types.UnknownType):
        return UnknownToArrowNone(type, mapper, artifact, path)
    else:
        return DefaultToArrow(type, mapper, artifact, path)


def map_from_arrow_(type, mapper, artifact, path=[], mapper_options=None):
    from .ops_arrow import arrow

    if isinstance(type, types.TypedDict):
        return mappers_python.TypedDictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, (types.List, arrow.ArrowWeaveListType)):
        return ArrowToArrowWeaveListOrPylist(type, mapper, artifact, path)
    elif isinstance(type, types.UnionType):
        return ArrowUnionToUnion(type, mapper, artifact, path)
    elif isinstance(type, partial_object.PartialObjectType):
        return mappers_python.GQLClassWithKeysToPyDict(type, mapper, artifact, path)
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
        return ArrowStringToString(type, mapper, artifact, path)
    elif isinstance(type, types.Timestamp):
        return ArrowDateTimeToDateTime(type, mapper, artifact, path)
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
