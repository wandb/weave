from . import mappers
from . import weave_types as types


class TypedDictMapper(mappers.Mapper):
    def __init__(self, type_: types.TypedDict, mapper, artifact, path=[]):
        self.type = type_
        prop_serializers = {}
        for property_key, property_type in type_.property_types.items():
            prop_serializer = mapper(
                property_type, artifact, path=path + [property_key]
            )
            prop_serializers[property_key] = prop_serializer
        self._property_serializers = prop_serializers

    def close(self):
        for property_key, property_serializer in self._property_serializers.items():
            property_serializer.close()


class DictMapper(mappers.Mapper):
    def __init__(self, type_: types.Dict, mapper, artifact, path=[]):
        self.type = type_
        self.key_serializer = mapper(type_.key_type, artifact, path)
        self.value_serializer = mapper(type_.value_type, artifact, path)

    def close(self):
        self.key_serializer.close()
        self.value_serializer.close()


class ObjectMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path=[]):
        self._artifact = artifact
        prop_serializers = {}
        for property_key, property_type in type_.property_types().items():
            prop_serializer = mapper(
                property_type, artifact, path=path + [property_key]
            )
            prop_serializers[property_key] = prop_serializer
        self._obj_type = type_
        self._property_serializers = prop_serializers

    def close(self):
        for property_key, property_serializer in self._property_serializers.items():
            if property_serializer:
                property_serializer.close()


class ObjectDictMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path=[]):
        prop_serializers = {}
        for property_key, property_type in type_.property_types().items():
            prop_serializer = mapper(
                property_type, artifact, path=path + [property_key]
            )
            prop_serializers[property_key] = prop_serializer
        self._obj_type = type_
        self._property_serializers = prop_serializers

    def close(self):
        for property_key, property_serializer in self._property_serializers.items():
            if property_serializer:
                property_serializer.close()


class ListMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path=[]):
        self._object_type = mapper(type_.object_type, artifact, path=path)

    def close(self):
        self._object_type.close()


class UnionMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path=[]):
        self.type = type_
        self._member_mappers = [
            mapper(mem_type, artifact, path=path) for mem_type in type_.members
        ]

    def close(self):
        for mapper in self._member_mappers:
            mapper.close()


class IntMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        pass

    def close(self):
        pass


class FloatMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        pass

    def close(self):
        pass


class StringMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        pass

    def close(self):
        pass


class NoneMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        pass

    def close(self):
        pass


class UnknownMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        pass

    def close(self):
        pass


class FunctionMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        pass

    def close(self):
        pass


class RefMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path=[]):
        self._object_type = type_.object_type

    def close(self):
        pass


class TypeMapper(mappers.Mapper):
    def __init__(self, type_: types.Type, mapper, artifact, path=[]):
        pass

    def close(self):
        pass


class ConstMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        self._type = type_
        self._val_type = mapper(type_.val_type, artifact, path=path)

    def close(self):
        self._val_type.close()
