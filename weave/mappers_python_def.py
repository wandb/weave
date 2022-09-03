import dataclasses
import inspect
import math

from . import mappers
from . import storage
from . import refs
from . import mappers_weave
from . import weave_types as types
from . import errors
from . import box
from . import mappers_python


class TypedDictToPyDict(mappers_weave.TypedDictMapper):
    def apply(self, obj):
        result = {}
        for k, prop_serializer in self._property_serializers.items():
            result[k] = prop_serializer.apply(obj[k])
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
        result = {}
        for prop_name, prop_serializer in self._property_serializers.items():
            if prop_serializer is not None:
                v = prop_serializer.apply(getattr(obj, prop_name))
                result[prop_name] = v
        return result


class ObjectDictToObject(mappers_weave.ObjectMapper):
    def apply(self, obj):
        result = obj
        for k, serializer in self._property_serializers.items():
            v = serializer.apply(obj[k])
            result[k] = v
        result_type = self._obj_type
        for prop_name, prop_type in result_type.variable_property_types().items():
            if isinstance(prop_type, types.Const):
                result[prop_name] = prop_type.val

        instance_class = result_type._instance_classes()[0]
        constructor_sig = inspect.signature(instance_class)
        if "artifact" in constructor_sig.parameters:
            result["artifact"] = self._artifact
        res = instance_class(**result)
        if not hasattr(res, "artifact"):
            res.artifact = self._artifact
        return res


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
            if member_type.assign_type(obj_type) != types.Invalid():
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
        return obj.uri


class PyRefToRef(mappers_weave.RefMapper):
    def apply(self, obj):
        return refs.Ref.from_str(obj)


class TypeToPyType(mappers.Mapper):
    def apply(self, obj):
        return obj.to_dict()


class PyTypeToType(mappers.Mapper):
    def apply(self, obj):
        return types.TypeRegistry.type_from_dict(obj)


class ConstToPyConst(mappers_weave.ConstMapper):
    def apply(self, obj):
        return obj


class DefaultToPy(mappers.Mapper):
    def __init__(self, type_: types.Type, mapper, artifact, path=[]):
        self.type = type_
        self._artifact = artifact
        self._path = path

    def apply(self, obj):
        try:
            return self.type.instance_to_dict(obj)
        except NotImplementedError:
            pass
        existing_ref = storage._get_ref(obj)
        if existing_ref:
            if existing_ref.is_saved:
                # TODO: should we assert type compatibility here or are they
                #     guaranteed to be equal already?
                return existing_ref.uri
            elif existing_ref.artifact != self._artifact:
                raise errors.WeaveInternalError(
                    "Can't save cross-artifact reference to unsaved artifact. This error was triggered when saving obj %s of type: %s"
                    % (self.obj, self.type)
                )
        name = "-".join(self._path)
        ref = storage.save_to_artifact(obj, self._artifact, name, self.type)
        if ref.artifact == self._artifact:
            return ref.local_ref_str()
        else:
            return ref.uri


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
            ref = refs.Ref.from_str(obj)
            # Note: we are forcing type here, because we already know it
            # We don't save the types for every file in a remote artifact!
            # But you can still reference them, because you have to get that
            # file through an op, and therefore we know the type?
            ref._type = self.type
            return ref.get()
        return refs.LocalArtifactRef.from_local_ref(
            self._artifact, obj, self.type
        ).get()


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
    if py_type(type) == types.Type:
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
    if py_type(type) == types.Type:
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
