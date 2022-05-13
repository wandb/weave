import pyarrow as pa
import typing

from . import mappers
from . import mappers_python
from . import mappers_weave
from . import arrow_util
from . import weave_types as types
from . import storage
from . import errors


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
        # TODO: when implementing for real unions, look at the mappers_python
        # implementation.
        return obj


class ArrowUnionToUnion(mappers_weave.UnionMapper):
    def apply(self, obj):
        # TODO: when implementing for real unions, look at the mappers_python
        # implementation.
        return obj


class IntToArrowInt(mappers_python.IntToPyInt):
    def result_type(self):
        return pa.int64()


class FloatToArrowFloat(mappers.Mapper):
    def result_type(self):
        return pa.float64()

    def apply(self, obj):
        return obj


class ArrowFloatToFloat(mappers.Mapper):
    def result_type(self):
        return types.Float()

    def apply(self, obj):
        return obj


class StringToArrowString(mappers_python.StringToPyString):
    def result_type(self):
        return pa.string()


class NoneToArrowNone(mappers.Mapper):
    def result_type(self):
        return pa.null()


class UnknownToArrowNone(mappers_python.UnknownToPyUnknown):
    def result_type(self):
        return pa.null()


class DefaultToArrow(mappers.Mapper):
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
        elif self.type.name == "ndarray" or self.type.name == "pil-image":
            # Ref type
            return pa.string()

        raise errors.WeaveInternalError(
            "Type not yet handled by mappers_arrow: %s" % self.type
        )

    def apply(self, obj):
        try:
            return self.type.instance_to_dict(obj)
        except NotImplementedError:
            pass
        name = "-".join(self._path)
        ref = storage.save_to_artifact(
            obj, artifact=self._artifact, name=name, type_=self.type
        )
        local_ref_str = ref.local_ref_str()
        return local_ref_str


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
    elif isinstance(type, types.Float):
        return FloatToArrowFloat(type, mapper, artifact, path)
    elif isinstance(type, types.String):
        return StringToArrowString(type, mapper, artifact, path)
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
    elif isinstance(type, types.Float):
        return ArrowFloatToFloat(type, mapper, artifact, path)
    elif isinstance(type, types.String):
        return mappers_python.StringToPyString(type, mapper, artifact, path)
    elif isinstance(type, types.NoneType):
        return mappers_python.NoneToPyNone(type, mapper, artifact, path)
    elif isinstance(type, types.UnknownType):
        return UnknownToArrowNone(type, mapper, artifact, path)
    else:
        return mappers_python.DefaultFromPy(type, mapper, artifact, path)


map_to_arrow = mappers.make_mapper(map_to_arrow_)
map_from_arrow = mappers.make_mapper(map_from_arrow_)
