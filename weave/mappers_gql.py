import datetime

from . import untyped_opaque_dict as uod
from . import mappers
from .mappers_python_def import (
    NoneToPyNone,
    BoolToPyBool,
    IntToPyInt,
    PyFloatToFloat,
    StringToPyString,
    ObjectDictToObject,
    TypedDictToPyDict,
    DictToPyDict,
    ListToPyList,
)

from .mappers_weave import UnionMapper

from . import errors
from . import weave_types as types
from .gql_with_keys import GQLHasKeysType


class GQLDictToUntypedOpaqueDict(mappers.Mapper):
    def apply(self, obj):
        return uod.UntypedOpaqueDict.from_json_dict(obj)


class GQLUnionToUnion(UnionMapper):
    def apply(self, obj):
        if self.is_single_object_nullable:
            if obj is None:
                return None
            non_null_mapper = next(
                filter(
                    lambda m: not types.NoneType().assign_type(m.type),
                    self._member_mappers,
                )
            )
            return non_null_mapper.apply(obj)
        elif "__typename" in obj:
            typename = obj["__typename"]
            for mapper in self._member_mappers:
                if isinstance(mapper.type, types.TypedDict):
                    typename_type = mapper.type.property_types.get("__typename", None)
                    if typename_type is not None:
                        assert isinstance(typename_type, types.Const)
                        mapper_typename = typename_type.val
                        if mapper_typename == typename:
                            return mapper.apply(obj)
        raise errors.WeaveValueError(
            f"Cant find a member of union {self.type} with typename {typename}"
        )


class GQLTimestampToTimestamp(mappers.Mapper):
    def apply(self, obj):
        assert isinstance(self.type, types.Timestamp)
        return self.type.from_isostring(obj)


class GQLConstToConst(mappers.Mapper):
    def apply(self, obj):
        return obj


def map_from_gql_payload_(type, mapper, artifact, path=[], mapper_options=None):
    if isinstance(type, uod.UntypedOpaqueDictType):
        return GQLDictToUntypedOpaqueDict(type, mapper, artifact, path)
    elif isinstance(type, GQLHasKeysType):
        return DictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, types.NoneType):
        return NoneToPyNone(type, mapper, artifact, path)
    elif isinstance(type, types.Boolean):
        return BoolToPyBool(type, mapper, artifact, path)
    elif isinstance(type, types.Int):
        return IntToPyInt(type, mapper, artifact, path)
    elif isinstance(type, types.Float):
        return PyFloatToFloat(type, mapper, artifact, path)
    elif isinstance(type, types.Number):
        return PyFloatToFloat(type, mapper, artifact, path)
    elif isinstance(type, types.String):
        return StringToPyString(type, mapper, artifact, path)
    elif isinstance(type, types.Timestamp):
        return GQLTimestampToTimestamp(type, mapper, artifact, path)
    elif isinstance(type, types.ObjectType):
        return ObjectDictToObject(type, mapper, artifact, path)
    elif isinstance(type, types.TypedDict):
        return TypedDictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, types.Dict):
        return DictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, types.List):
        return ListToPyList(type, mapper, artifact, path)
    elif isinstance(type, types.UnionType):
        return GQLUnionToUnion(type, mapper, artifact, path)
    elif isinstance(type, types.Const):
        return GQLConstToConst(type, mapper, artifact, path)
    raise errors.WeaveValueError(f"Unknown type {type}")


map_from_gql = mappers.make_mapper(map_from_gql_payload_)
