import json
from . import mappers
from .mappers_python_def import (
    NoneToPyNone,
    BoolToPyBool,
    IntToPyInt,
    PyFloatToFloat,
    ObjectDictToObject,
    TypedDictToPyDict,
    DictToPyDict,
    ListToPyList,
)

from .mappers_weave import UnionMapper

from . import errors
from . import weave_types as types
from .partial_object import PartialObjectType

from . import gql_json_cache


class GQLTypedDictToTypedDict(TypedDictToPyDict):
    def apply(self, obj):
        # Hack!! Our output types throughout GQL are all wrong. They are non-nullable
        # when in reality GQL responses can frequently be optional.
        if obj is None:
            return None
        return super().apply(obj)


class GQLUnionToUnion(UnionMapper):
    def apply(self, obj):
        if obj is None:
            return None
        if self.is_single_object_nullable:
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


class GQLStringToString(mappers.Mapper):
    def apply(self, obj):
        if isinstance(obj, str):
            return obj

        # the weave type of the graphql JSON type is a string, so here we
        # convert the json object to a string, but we also cache the python
        # object, in case we need to use it later in an op (like history or summary)
        serialized = json.dumps(obj)
        gql_json_cache.cache_json(serialized, obj)
        return serialized


class GQLTimestampToTimestamp(mappers.Mapper):
    def apply(self, obj):
        assert isinstance(self.type, types.Timestamp)
        return self.type.from_isostring(obj)


class GQLConstToConst(mappers.Mapper):
    def apply(self, obj):
        return obj


def map_from_gql_payload_(type, mapper, artifact, path=[], mapper_options=None):
    if isinstance(type, PartialObjectType):
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
        return GQLStringToString(type, mapper, artifact, path)
    elif isinstance(type, types.Timestamp):
        return GQLTimestampToTimestamp(type, mapper, artifact, path)
    elif isinstance(type, types.ObjectType):
        return ObjectDictToObject(type, mapper, artifact, path)
    elif isinstance(type, types.TypedDict):
        return GQLTypedDictToTypedDict(type, mapper, artifact, path)
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
