import typing

from . import mappers
from . import weave_types as types
from .partial_object import PartialObjectType


class TypedDictMapper(mappers.Mapper):
    def __init__(self, type_: types.TypedDict, mapper, artifact, path=[]):
        self.type = type_
        self._artifact = artifact
        self.path = path
        prop_serializers = {}
        for property_key, property_type in type_.property_types.items():
            prop_serializer = mapper(
                property_type, artifact, path=path + [property_key]
            )
            prop_serializers[property_key] = prop_serializer
        self._property_serializers = prop_serializers


class GQLMapper(mappers.Mapper):
    def __init__(self, type_: types.Type, mapper, artifact, path):
        self.type = typing.cast(PartialObjectType, type_)
        self._artifact = artifact
        self.path = path
        self.mapper = mapper
        prop_serializers = {}
        for property_key, property_type in self.type.keys.items():
            prop_serializer = mapper(
                property_type, artifact, path=path + [property_key]
            )
            prop_serializers[property_key] = prop_serializer
        self._property_serializers: dict[str, mappers.Mapper] = prop_serializers


class DictMapper(mappers.Mapper):
    def __init__(self, type_: types.Dict, mapper, artifact, path=[]):
        self.type = type_
        self.key_serializer = mapper(type_.key_type, artifact, path)
        self.value_serializer = mapper(type_.object_type, artifact, path)


class ObjectMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path=[]):
        self.type = type_
        self._artifact = artifact
        prop_serializers = {}
        for property_key, property_type in type_.property_types().items():
            prop_serializer = mapper(
                property_type, artifact, path=path + [property_key]
            )
            prop_serializers[property_key] = prop_serializer
        self._obj_type = type_
        self._property_serializers = prop_serializers


class ListMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path=[]):
        self.type = type_
        self._object_type = mapper(type_.object_type, artifact, path=path)


class UnionMapper(mappers.Mapper):
    # If true, this is a mapper for an optional type,
    # like <int> | <none> or <str> | <none>
    is_single_object_nullable: bool

    def __init__(self, type_, mapper, artifact, path=[]):
        self.type = type_
        self._member_mappers = [
            mapper(mem_type, artifact, path=path) for mem_type in type_.members
        ]

        self.is_single_object_nullable = False
        for mapper in self._member_mappers:
            if (
                isinstance(mapper.type, types.NoneType)
                and len(self._member_mappers) == 2
            ):
                self.is_single_object_nullable = True


class RefMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path=[]):
        self.type = type_


class ConstMapper(mappers.Mapper):
    def __init__(self, type_, mapper, artifact, path):
        self.type = type_
        self._val_mapper = mapper(type_.val_type, artifact, path=path)
