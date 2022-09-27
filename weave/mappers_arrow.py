import json
import pyarrow as pa
import typing

from . import mappers
from . import mappers_python_def as mappers_python
from . import mappers_weave
from . import arrow_util
from . import weave_types as types
from . import refs
from . import errors
from . import node_ref


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


class ListToArrowArr(mappers_python.ListToPyList):
    def result_type(self):
        return pa.list_(arrow_util.arrow_field("x", self._object_type.result_type()))


class UnionToArrowUnion(mappers_weave.UnionMapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        non_none_members = [
            m for m in self._member_mappers if not isinstance(m.type, types.NoneType)
        ]
        if len(non_none_members) != 1:
            raise errors.WeaveInternalError("Unions not yet supported in Weave arrow")
        self._member_mapper = non_none_members[0]

    def result_type(self):
        nullable = False
        non_null_mappers: typing.List[mappers.Mapper] = []
        for member_mapper in self._member_mappers:
            if isinstance(member_mapper.type, types.NoneType):
                nullable = True
            else:
                non_null_mappers.append(member_mapper)
        if not nullable or len(non_null_mappers) > 1:
            raise errors.WeaveInternalError(
                "full union handling not yet implement in mappers_arrow. Type: %s"
                % self.type
            )
        return arrow_util.arrow_type_with_nullable(non_null_mappers[0].result_type())

    def apply(self, obj):
        return self._member_mapper.apply(obj)


class ArrowUnionToUnion(UnionToArrowUnion):
    pass


class IntToArrowInt(mappers_python.IntToPyInt):
    def result_type(self):
        return pa.int64()


class BoolToArrowBool(mappers_python.BoolToPyBool):
    def result_type(self):
        return pa.bool_()


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
    if isinstance(type, types.TypedDict):
        return TypedDictToArrowStruct(type, mapper, artifact, path)
    elif isinstance(type, types.List):
        return ListToArrowArr(type, mapper, artifact, path)
    elif isinstance(type, types.UnionType):
        return UnionToArrowUnion(type, mapper, artifact, path)
    elif isinstance(type, types.ObjectType):
        return ObjectToArrowStruct(type, mapper, artifact, path)
    elif isinstance(type, types.Int):
        return IntToArrowInt(type, mapper, artifact, path)
    elif isinstance(type, types.Boolean):
        return BoolToArrowBool(type, mapper, artifact, path)
    elif isinstance(type, types.Float) or isinstance(type, types.Number):
        return FloatToArrowFloat(type, mapper, artifact, path)
    elif isinstance(type, types.String):
        return StringToArrowString(type, mapper, artifact, path)
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
    elif isinstance(type, types.Int):
        return mappers_python.IntToPyInt(type, mapper, artifact, path)
    elif isinstance(type, types.Boolean):
        return mappers_python.BoolToPyBool(type, mapper, artifact, path)
    elif isinstance(type, types.Float) or isinstance(type, types.Number):
        return ArrowFloatToFloat(type, mapper, artifact, path)
    elif isinstance(type, types.String):
        return mappers_python.StringToPyString(type, mapper, artifact, path)
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
