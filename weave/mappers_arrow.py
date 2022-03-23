import json
import pyarrow as pa

from . import mappers
from . import mappers_python
from . import mappers_numpy
from . import arrow_util
from . import weave_types as types
from . import types_numpy


class TypedDictToArrowStruct(mappers_python.TypedDictToPyDict):
    def result_type(self):
        fields = []
        for property_key, property_serializer in self._property_serializers.items():
            prop_result_type = property_serializer.result_type()
            fields.append(arrow_util.arrow_field(property_key, prop_result_type))
        return pa.struct(fields)


class ArrowStructMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        prop_serializers = {}
        for field in type_:
            prop_serializers[field.name] = mapper(field, artifact, path)
        self._property_serializers = prop_serializers

    def close(self):
        for ser in self._property_serializers.values():
            ser.close()


class ArrowStructToTypedDict(ArrowStructMapper):
    def result_type(self):
        return types.TypedDict(self._property_serializers)

    def apply(self, obj):
        result = {}
        for k, v in obj.items():
            v = self._property_serializers[k].apply(v)
            result[k] = v
        return result


class ObjectToArrowStruct(mappers_python.ObjectToPyDict):
    def result_type(self):
        fields = []
        for property_key, property_serializer in self._property_serializers.items():
            if property_serializer is not None:
                prop_result_type = property_serializer.result_type()
                fields.append(arrow_util.arrow_field(property_key, prop_result_type))
        arrow_type = pa.struct(fields)

        metadata = {"weave_type": json.dumps(self._obj_type.to_dict())}
        return arrow_util.arrow_type_with_metadata(arrow_type, metadata)


class ArrowWeaveFieldToObject(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        if type_.metadata is None or b"weave_type" not in type_.metadata:
            raise Exception("invalid")
        self._type_dict = json.loads(type_.metadata[b"weave_type"])
        prop_serializers = {}
        for field in type_.type:
            prop_serializers[field.name] = mapper(field, artifact, path)
        self._property_serializers = prop_serializers

    def result_type(self):
        return types.TypeRegistry.type_from_dict(self._type_dict)

    def close(self):
        # TODO: This needs to call close on children
        pass

    def apply(self, obj):
        result = {}
        for k, v in obj.items():
            v = self._property_serializers[k].apply(v)
            result[k] = v
        result_type = self.result_type()
        for prop_name, prop_type in result_type.variable_property_types().items():
            # TODO: need a base Const type
            if isinstance(prop_type, types.ConstString) or isinstance(
                prop_type, types.ConstNumber
            ):
                result[prop_name] = prop_type.val
        return self.result_type().instance_class(**result)


class ListToArrowArr(mappers_python.ListToPyList):
    def result_type(self):
        return pa.list_(arrow_util.arrow_field("x", self._object_type.result_type()))


class ArrowListMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        object_type = mapper(type_.value_type, artifact, path)
        value_field = type_.value_field
        if value_field.metadata is not None and b"weave_type" in value_field.metadata:
            object_type = ArrowWeaveFieldToObject(value_field, mapper, artifact, path)
        self._object_type = object_type

    def close(self):
        self._object_type.close()


class ArrowArrToList(ArrowListMapper):
    def result_type(self):
        return types.List(self._object_type)

    def apply(self, obj):
        return [self._object_type.apply(item) for item in obj]


class IntToArrowInt(mappers_python.IntToPyInt):
    def result_type(self):
        return pa.int64()


class ArrowIntMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        pass

    def close(self):
        pass


class ArrowIntToInt(ArrowIntMapper):
    def result_type(self):
        return types.Int()

    def apply(self, obj):
        return obj


class FloatToArrowFloat(mappers_python.FloatToPyFloat):
    def result_type(self):
        return pa.float64()


class ArrowFloatMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        pass

    def close(self):
        pass


class ArrowFloatToFloat(ArrowFloatMapper):
    def result_type(self):
        return types.Float()

    def apply(self, obj):
        return obj


class StringToArrowString(mappers_python.StringToPyString):
    def result_type(self):
        return pa.string()


class ArrowStringMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        pass

    def close(self):
        pass


class ArrowStringToString(ArrowStringMapper):
    def result_type(self):
        return types.String()

    def apply(self, obj):
        return obj


class NoneToArrowNone(mappers.Mapper):
    def result_type(self):
        return pa.null()


class ArrowNoneToNone(mappers.Mapper):
    def result_type(self):
        return types.none_type


class UnknownToArrowNone(mappers_python.UnknownToPyUnknown):
    def result_type(self):
        return pa.null()


def map_to_arrow_(type, mapper, artifact, path=[]):
    if isinstance(type, pa.DataType) or isinstance(
        type, arrow_util.ArrowTypeWithFieldInfo
    ):
        return None
    elif isinstance(type, types.TypedDict):
        return TypedDictToArrowStruct(type, mapper, artifact, path)
    elif isinstance(type, types.List):
        return ListToArrowArr(type, mapper, artifact, path)
    elif isinstance(type, types.ObjectType):
        return ObjectToArrowStruct(type, mapper, artifact, path)
    elif isinstance(type, types_numpy.NumpyArrayType):
        return mappers_numpy.NumpyArraySaver(type, mapper, artifact, path)
    elif isinstance(type, types.Int):
        return IntToArrowInt(type, mapper, artifact, path)
    elif isinstance(type, types.Float):
        return FloatToArrowFloat(type, mapper, artifact, path)
    elif isinstance(type, types.Number):
        return IntToArrowInt(type, mapper, artifact, path)
    elif isinstance(type, types.String):
        return StringToArrowString(type, mapper, artifact, path)
    elif isinstance(type, types.NoneType):
        return NoneToArrowNone(type, mapper, artifact, path)
    elif isinstance(type, types.UnknownType):
        return UnknownToArrowNone(type, mapper, artifact, path)
    elif isinstance(type, types.ConstString):
        return None
    else:
        raise Exception("not implemented", type)


def map_from_arrow_(arrow_type, mapper, artifact, path=[]):
    if isinstance(arrow_type, types.Type):
        if isinstance(arrow_type, types_numpy.NumpyArrayRefType):
            return mappers_numpy.NumpyArrayLoader(arrow_type, mapper, artifact, path)
        return None
    elif isinstance(arrow_type, pa.Field):
        if arrow_type.metadata is not None and b"weave_type" in arrow_type.metadata:
            return ArrowWeaveFieldToObject(arrow_type, mapper, artifact, path)
        else:
            return mapper(arrow_type.type, artifact, path)
    elif isinstance(arrow_type, pa.Schema) or pa.types.is_struct(arrow_type):
        return ArrowStructToTypedDict(arrow_type, mapper, artifact, path)
    elif pa.types.is_list(arrow_type):
        return ArrowArrToList(arrow_type, mapper, artifact, path)
    elif pa.types.is_integer(arrow_type):
        return ArrowIntToInt(arrow_type, mapper, artifact, path)
    elif pa.types.is_float64(arrow_type):
        return ArrowFloatToFloat(arrow_type, mapper, artifact, path)
    elif pa.types.is_string(arrow_type):
        return ArrowStringToString(type, mapper, artifact, path)
    elif pa.types.is_null(arrow_type):
        return ArrowNoneToNone(type, mapper, artifact, path)
    else:
        raise Exception("not implemented", type)


map_to_arrow = mappers.make_mapper(map_to_arrow_)
map_from_arrow = mappers.make_mapper(map_from_arrow_)
