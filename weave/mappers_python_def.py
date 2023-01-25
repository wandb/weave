import dataclasses
import datetime
import inspect
import math


from . import mappers
from . import storage
from . import ref_base
from . import mappers_weave
from . import weave_types as types
from . import errors
from . import box
from . import mappers_python
from . import val_const
from .timestamp import tz_aware_dt
from .language_features.tagging import tagged_value_type


class TypedDictToPyDict(mappers_weave.TypedDictMapper):
    def apply(self, obj):
        result = {}
        for k, prop_serializer in self._property_serializers.items():
            result[k] = prop_serializer.apply(obj.get(k, None))
        return result


class DictToPyDict(mappers_weave.DictMapper):
    def apply(self, obj):
        result = {}
        for k, v in obj.items():
            k = self.key_serializer.apply(k)
            v = self.value_serializer.apply(v)
            result[k] = v
        return result


class ObjectToPyDict(mappers_weave.ObjectMapper):
    def apply(self, obj):
        # Store the type name in the saved object. W&B for example stores
        # {"_type": "table-ref", "artifact_path": "..."} objects in run config and summary
        # fields.
        result = {"_type": self.type.name}
        for prop_name, prop_serializer in self._property_serializers.items():
            if prop_serializer is not None:
                v = prop_serializer.apply(getattr(obj, prop_name))
                result[prop_name] = v
        return result


class ObjectDictToObject(mappers_weave.ObjectMapper):
    def apply(self, obj):
        # Only add keys that are accepted by the constructor.
        # This is used for Panels where we have an Class-level id attribute
        # that we want to include in the serialized representation.
        result = {}
        result_type = self._obj_type

        # TODO: I think these are hacks in my branch. What do they do?
        instance_class = result_type._instance_classes()[0]
        constructor_sig = inspect.signature(instance_class)
        for k, serializer in self._property_serializers.items():
            if k in constructor_sig.parameters:
                # None haxxx
                # TODO: remove
                obj_val = obj.get(k)
                if obj_val is None:
                    result[k] = None
                else:
                    v = serializer.apply(obj_val)
                    result[k] = v

        for prop_name, prop_type in result_type.type_vars.items():
            if isinstance(prop_type, types.Const):
                result[prop_name] = prop_type.val

        if "artifact" in constructor_sig.parameters:
            result["artifact"] = self._artifact
        return instance_class(**result)


class ListToPyList(mappers_weave.ListMapper):
    def apply(self, obj):
        return [self._object_type.apply(item) for item in obj]


class UnionToPyUnion(mappers_weave.UnionMapper):
    def apply(self, obj):
        obj_type = types.TypeRegistry.type_of(obj)
        for i, (member_type, member_mapper) in enumerate(
            zip(self.type.members, self._member_mappers)
        ):

            # TODO: assignment isn't right here (a dict with 'a', 'b' int keys is
            # assignable to a dict with an 'a' int key). We want type equality.
            # But that breaks some stuff
            # TODO: Should types.TypeRegistry.type_of always return a const type??
            if isinstance(member_type, types.Const) and not isinstance(
                obj_type, types.Const
            ):
                obj_type = types.Const(obj_type, obj)
            if member_type.assign_type(obj_type):
                result = member_mapper.apply(obj)
                if isinstance(result, dict):
                    result["_union_id"] = i
                else:
                    result = {"_union_id": i, "_val": result}
                return result
        raise Exception("invalid %s" % obj)


class PyUnionToUnion(mappers_weave.UnionMapper):
    def apply(self, obj):
        member_index = obj["_union_id"]
        if "_val" in obj:
            obj = obj["_val"]
        else:
            obj.pop("_union_id")
        return self._member_mappers[member_index].apply(obj)


class IntToPyInt(mappers.Mapper):
    def apply(self, obj):
        return obj


class BoolToPyBool(mappers.Mapper):
    def apply(self, obj):
        if isinstance(obj, box.BoxedBool):
            return obj.val
        return obj


class FloatToPyFloat(mappers.Mapper):
    def apply(self, obj):
        if math.isnan(obj):
            return "nan"
        return obj


class PyFloatToFloat(mappers.Mapper):
    def apply(self, obj):
        if isinstance(obj, str):
            if obj == "nan":
                return float("nan")
        return obj


class StringToPyString(mappers.Mapper):
    def apply(self, obj):
        return obj


class TimestampToPyTimestamp(mappers.Mapper):
    def apply(self, obj: datetime.datetime):
        return int(tz_aware_dt(obj).timestamp() * 1000)


class PyTimestampToTimestamp(mappers.Mapper):
    def apply(self, obj):
        # This is here to support the legacy "date" type, the frontend passes
        # RFC 3339 formatted strings
        if isinstance(obj, dict):
            if obj.get("type") != "date":
                raise errors.WeaveInternalError(
                    f'expected object with type date but got "{obj}"'
                )
            return datetime.datetime.strptime(obj["val"], "%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            return datetime.datetime.fromtimestamp(obj / 1000, tz=datetime.timezone.utc)


class NoneToPyNone(mappers.Mapper):
    def apply(self, obj):
        return None


class UnknownToPyUnknown(mappers.Mapper):
    def apply(self, obj):
        # This should never be called. Unknown for the object type
        # of empty lists
        raise Exception("invalid %s" % obj)


class RefToPyRef(mappers_weave.RefMapper):
    def apply(self, obj):
        try:
            return obj.uri
        except NotImplementedError:
            raise errors.WeaveSerializeError('Cannot serialize ref "%s"' % obj)


class PyRefToRef(mappers_weave.RefMapper):
    def apply(self, obj):
        return ref_base.Ref.from_str(obj)


class TypeToPyType(mappers.Mapper):
    def apply(self, obj):
        return obj.to_dict()


class PyTypeToType(mappers.Mapper):
    def apply(self, obj):
        return types.TypeRegistry.type_from_dict(obj)


class ConstToPyConst(mappers_weave.ConstMapper):
    def apply(self, obj):
        val = obj
        if isinstance(obj, val_const.Const):
            return val.val
        return self._val_mapper.apply(obj)


class DefaultToPy(mappers.Mapper):
    def __init__(self, type_: types.Type, mapper, artifact, path=[]):
        self.type = type_
        self._artifact = artifact
        self._path = path
        self._row_id = 0

    def apply(self, obj):
        try:
            return self.type.instance_to_dict(obj)
        except NotImplementedError:
            pass
        # If the ref exists elsewhere, just return its uri.
        # TODO: This doesn't deal with MemArtifactRef!
        existing_ref = storage._get_ref(obj)
        if existing_ref:
            if existing_ref.is_saved:
                return str(existing_ref)

        # This defines the artifact layout!
        name = "/".join(self._path + [str(self._row_id)])
        self._row_id += 1

        ref = self._artifact.set(name, self.type, obj)
        if ref.artifact == self._artifact:
            return ref.local_ref_str()
        else:
            return str(ref)


class DefaultFromPy(mappers.Mapper):
    def __init__(self, type_: types.Type, mapper, artifact, path=[]):
        self.type = type_
        self._artifact = artifact
        self._path = path

    def apply(self, obj):
        if isinstance(obj, dict):
            return self.type.instance_from_dict(obj)
        # else its a ref string
        # TODO: this does not use self.artifact, can we just drop it?
        # Do we need the type so we can load here? No...
        if ":" in obj:
            ref = ref_base.Ref.from_str(obj)
            # Note: we are forcing type here, because we already know it
            # We don't save the types for every file in a remote artifact!
            # But you can still reference them, because you have to get that
            # file through an op, and therefore we know the type?
            ref._type = self.type
            return ref.get()
        return self._artifact.get(obj, self.type)


py_type = type


@dataclasses.dataclass
class RegisteredMapper:
    type_class: type[types.Type]
    to_mapper: type[mappers.Mapper]
    from_mapper: type[mappers.Mapper]


_additional_mappers: list[RegisteredMapper] = []


def add_mapper(
    type_class: type[types.Type],
    to_mapper: type[mappers.Mapper],
    from_mapper: type[mappers.Mapper],
):
    _additional_mappers.append(RegisteredMapper(type_class, to_mapper, from_mapper))


def map_to_python_(type, mapper, artifact, path=[]):
    if isinstance(type, types.TypeType):
        # If we're actually serializing a type itself
        return TypeToPyType(type, mapper, artifact, path)
    elif isinstance(type, types.TypedDict):
        return TypedDictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, types.Dict):
        return DictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, types.List):
        return ListToPyList(type, mapper, artifact, path)
    elif isinstance(type, types.UnionType):
        return UnionToPyUnion(type, mapper, artifact, path)
    elif isinstance(type, types.ObjectType):
        return ObjectToPyDict(type, mapper, artifact, path)
    elif isinstance(type, tagged_value_type.TaggedValueType):
        return tagged_value_type.TaggedValueToPy(type, mapper, artifact, path)
    elif isinstance(type, types.Boolean):
        return BoolToPyBool(type, mapper, artifact, path)
    elif isinstance(type, types.Int):
        return IntToPyInt(type, mapper, artifact, path)
    elif isinstance(type, types.Float):
        return FloatToPyFloat(type, mapper, artifact, path)
    elif isinstance(type, types.Number):
        return FloatToPyFloat(type, mapper, artifact, path)
    elif isinstance(type, types.String):
        return StringToPyString(type, mapper, artifact, path)
    elif isinstance(type, types.Timestamp):
        return TimestampToPyTimestamp(type, mapper, artifact, path)
    elif isinstance(type, types.Const):
        return ConstToPyConst(type, mapper, artifact, path)
    elif isinstance(type, types.NoneType):
        return NoneToPyNone(type, mapper, artifact, path)
    elif isinstance(type, types.UnknownType):
        return UnknownToPyUnknown(type, mapper, artifact, path)
    elif isinstance(type, types.RefType):
        return RefToPyRef(type, mapper, artifact, path)
    else:
        for m in _additional_mappers:
            if isinstance(type, m.type_class):
                return m.to_mapper(type, mapper, artifact, path)
        return DefaultToPy(type, mapper, artifact, path)


def map_from_python_(type: types.Type, mapper, artifact, path=[]):
    if isinstance(type, types.TypeType):
        # If we're actually serializing a type itself
        return PyTypeToType(type, mapper, artifact, path)
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
    elif isinstance(type, tagged_value_type.TaggedValueType):
        return tagged_value_type.TaggedValueFromPy(type, mapper, artifact, path)
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
    elif isinstance(type, types.LegacyDate):
        return PyTimestampToTimestamp(type, mapper, artifact, path)
    elif isinstance(type, types.Const):
        return ConstToPyConst(type, mapper, artifact, path)
    elif isinstance(type, types.NoneType):
        return NoneToPyNone(type, mapper, artifact, path)
    elif isinstance(type, types.UnknownType):
        return UnknownToPyUnknown(type, mapper, artifact, path)
    elif isinstance(type, types.RefType):
        return PyRefToRef(type, mapper, artifact, path)
    else:
        for m in _additional_mappers:
            if isinstance(type, m.type_class):
                return m.from_mapper(type, mapper, artifact, path)
        return DefaultFromPy(type, mapper, artifact, path)


mappers_python.map_to_python = mappers.make_mapper(map_to_python_)
mappers_python.map_from_python = mappers.make_mapper(map_from_python_)
