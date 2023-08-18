from . import untyped_opaque_dict as uod
from . import mappers
from .mappers_python_def import (
    NoneToPyNone,
    BoolToPyBool,
    IntToPyInt,
    PyFloatToFloat,
    StringToPyString,
    PyTimestampToTimestamp,
    ObjectDictToObject,
    TypedDictToPyDict,
    DictToPyDict,
    ListToPyList,
    PyUnionToUnion,
)

from . import errors
from . import weave_types as types
from .gql_with_keys import GQLHasKeysType


class PyDictToUntypedOpaqueDict(mappers.Mapper):
    def apply(self, obj):
        return uod.DictSavedAsString(obj)


def map_from_gql_payload_(type, mapper, artifact, path=[], mapper_options=None):
    if isinstance(type, uod.DictSavedAsString.WeaveType):
        return PyDictToUntypedOpaqueDict(type, mapper, artifact, path)
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
        return PyTimestampToTimestamp(type, mapper, artifact, path)
    elif isinstance(type, types.ObjectType):
        return ObjectDictToObject(type, mapper, artifact, path)
    elif isinstance(type, types.TypedDict):
        return TypedDictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, types.Dict):
        return DictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, types.List):
        return ListToPyList(type, mapper, artifact, path)
    elif isinstance(type, types.UnionType):
        return PyUnionToUnion(type, mapper, artifact, path)
    raise errors.WeaveValueError(f"Unknown type {type}")


map_from_gql = mappers.make_mapper(map_from_gql_payload_)
