import copy
import dataclasses
import typing
import functools
import json
from collections.abc import Iterable

from . import box
from . import errors
from . import mappers_python

if typing.TYPE_CHECKING:
    from .refs import Ref
    from .artifacts_local import Artifact


def to_weavejs_typekey(k: str) -> str:
    if k == "object_type":
        return "objectType"
    elif k == "property_types":
        return "propertyTypes"
    return k


def all_subclasses(cls):
    # Note using a list here... this doesn't dedupe star pattern!
    # But it does preserve tree order.
    return list(cls.__subclasses__()) + [
        s for c in cls.__subclasses__() for s in all_subclasses(c)
    ]


def get_type_classes():
    return all_subclasses(Type)


def instance_class_to_potential_type_map():
    res = {}
    type_classes = get_type_classes()
    for type_class in type_classes:
        for instance_class in type_class._instance_classes():
            res.setdefault(instance_class, []).append(type_class)

    # These are errors and we should fix them
    # TODO
    # for ic, tcs in res.items():
    #     if len(tcs) > 1:
    #         print("LONG TC", ic, tcs)
    return res


@functools.cache
def instance_class_to_potential_type(cls):
    mapping = instance_class_to_potential_type_map()
    exact_type_classes = mapping.get(cls)
    if exact_type_classes is not None:
        return exact_type_classes
    result = []
    for instance_class, type_classes in mapping.items():
        if issubclass(cls, instance_class):
            result += type_classes
    return result


def type_class_type_name(type_class):
    if hasattr(type_class, "class_type_name"):
        return type_class.class_type_name()


@functools.cache
def type_name_to_type_map():
    res = {}
    type_classes = get_type_classes()
    for type_class in type_classes:
        name = type_class_type_name(type_class)
        if name is not None:
            res[name] = type_class
    return res


@functools.cache
def type_name_to_type(type_name):
    mapping = type_name_to_type_map()
    return mapping.get(type_name)


class TypeRegistry:
    @staticmethod
    def has_type(obj):
        return bool(instance_class_to_potential_type(type(obj)))

    @staticmethod
    def type_class_of(obj):
        type_classes = instance_class_to_potential_type(type(obj))
        if not type_classes:
            raise errors.WeaveTypeError("no Type for obj: %s" % obj)
        return type_classes[-1]

    @staticmethod
    def type_of(obj):
        if isinstance(obj, Type):
            return Type()

        # use reversed instance_class_to_potential_type so our result
        # is the most specific type.

        # The type of graph.Node objects is Function, but we also mixin
        # NodeMethodsClass with Node, which may also have a Weave type.
        # Therefore we have multiple valid types. But we need type_of() to
        # be function in that case. Ie when a Node is mixed in, its lazy
        # representation of whatever the type is, not the actual type.
        #
        # TODO: Its a small that we need to hardcode here. Fix this.
        potential_types = instance_class_to_potential_type(type(obj))
        if "function" in (t.name for t in potential_types):
            potential_types = [Function]

        # We can't be sure that Tagged will be last in the tree, so
        # we just force it here. TODO: Fix
        if "tagged" in (t.name for t in potential_types):
            potential_types = [TaggedType]

        # FileType and ArtifactFileVersionFileType are peers because
        # one is an ObjectType and one is a base type, and we don't
        # know python class hierarchy. This is a major major hack
        # to force ArtifactVersionFile in that case.
        # TODO: fix in refactor!!
        for t in potential_types:
            if t.name == "ArtifactVersionFile":
                return t()

        for type_ in reversed(potential_types):
            obj_type = type_.type_of(obj)
            if obj_type is not None:
                return obj_type
        raise errors.WeaveTypeError("no Type for obj: (%s) %s" % (type(obj), obj))

    @staticmethod
    def type_from_dict(d: typing.Union[str, dict]) -> "Type":
        # The javascript code sends simple types as just strings
        # instead of {'type': 'string'} for example
        type_name = d["type"] if isinstance(d, dict) else d
        if type_name == "type":
            return Type()
        type_ = type_name_to_type(type_name)
        if type_ is None:
            raise errors.WeaveSerializeError("Can't deserialize type from: %s" % d)
        return type_.from_dict(d)


def _clear_global_type_class_cache():
    instance_class_to_potential_type.cache_clear()
    type_name_to_type_map.cache_clear()
    type_name_to_type.cache_clear()


# Addapted from https://stackoverflow.com/questions/18126552/how-to-run-code-when-a-class-is-subclassed
class _TypeSubclassWatcher(type):
    def __init__(cls, name, bases, clsdict):
        # This code will run whenever `Type` is subclassed!
        # Bust the cache!
        _clear_global_type_class_cache()
        super(_TypeSubclassWatcher, cls).__init__(name, bases, clsdict)


@dataclasses.dataclass(frozen=True)
class Type(metaclass=_TypeSubclassWatcher):
    NodeMethodsClass: typing.ClassVar[typing.Optional[type]]
    instance_class: typing.ClassVar[typing.Optional[type]]
    instance_classes: typing.ClassVar[
        typing.Union[type, typing.List[type], None]
    ] = None

    def __repr__(self):
        return f"<{self.name}>"

    @classmethod
    def class_type_name(cls):
        if cls == Type:
            return "type"
        if hasattr(cls, "name") and type(cls.name) == str:
            return cls.name
        return cls.__name__.removesuffix("Type")

    @classmethod
    def _instance_classes(cls):
        """Helper to get instance_classes as iterable."""
        if cls.instance_classes is None:
            return ()
        if isinstance(cls.instance_classes, Iterable):
            return cls.instance_classes
        return (cls.instance_classes,)

    @classmethod
    def type_vars(cls):
        type_vars = {}
        for field in dataclasses.fields(cls):
            if issubclass(field.type, Type):
                type_vars[field.name] = field.type
        return type_vars

    @classmethod
    def is_instance(cls, obj):
        for ic in cls._instance_classes():
            if isinstance(obj, ic):
                return ic
        return None

    @classmethod
    def type_of(cls, obj):
        if not cls.is_instance(obj):
            return None
        return cls.type_of_instance(obj)

    @classmethod
    def type_of_instance(cls, obj):
        # Default implementation for Types that take no arguments.
        return cls()

    @property
    def name(self):
        return self.class_type_name()

    @property  # type: ignore
    def instance_class(self):
        return self._instance_classes()[-1]

    def assign_type(self, next_type: "Type") -> bool:
        if isinstance(next_type, Const):
            return self.assign_type(next_type.val_type)
        elif isinstance(next_type, UnionType):
            for t in next_type.members:
                if not self.assign_type(t):
                    return False
            return True
        return self._assign_type_inner(next_type)

    def _assign_type_inner(self, next_type: "Type") -> bool:
        if (
            isinstance(next_type, self.__class__)
            or
            # parent is assignable to child class
            #     when type variables match
            # TODO: only valid when python hiearchy matches type hierarchy!
            #     And no Abstract classes (Type)
            isinstance(self, next_type.__class__)
        ):
            # if isinstance(next_type, self.__class__):
            if callable(self.type_vars):
                type_vars = self.type_vars()
            else:
                type_vars = self.type_vars
            for prop_name in type_vars:
                if not hasattr(next_type, prop_name):
                    return False
                if not getattr(self, prop_name).assign_type(
                    getattr(next_type, prop_name)
                ):
                    return False
            return True
        return False

    def to_dict(self) -> typing.Union[dict, str]:
        if self.__class__ == Type:
            return "type"
        d = {"type": self.name}
        d.update(self._to_dict())
        return d

    def _to_dict(self):
        fields = dataclasses.fields(self.__class__)
        type_props = {}
        for field in fields:
            # TODO: I really don't like this change. Only needed because
            # FileType has optional fields... Remove?
            attr = getattr(self, field.name)
            if not attr:
                continue
            type_props[to_weavejs_typekey(field.name)] = attr.to_dict()
        return type_props

    @classmethod
    def from_dict(cls, d):
        fields = dataclasses.fields(cls)
        type_attrs = {}
        for field in fields:
            type_attrs[field.name] = TypeRegistry.type_from_dict(
                d[to_weavejs_typekey(field.name)]
            )
        return cls(**type_attrs)

    # save_instance/load_instance on Type are used to save/load actual Types
    # since type_of(types.Int()) == types.Type()
    def save_instance(
        self, obj, artifact, name
    ) -> typing.Optional[typing.Union[list[str], "Ref"]]:
        d = None
        if self.__class__ == Type:
            d = obj.to_dict()
        else:
            try:
                d = self.instance_to_dict(obj)
            except NotImplementedError:
                pass
        if d is None:
            raise errors.WeaveSerializeError(
                "Object is not serializable. Provide instance_<to/from>_dict or <save/load>_instance methods on Type: %s"
                % self
            )
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(d, f)
        return None

    def load_instance(
        self, artifact: "Artifact", name: str, extra: typing.Optional[list[str]] = None
    ) -> typing.Any:
        with artifact.open(f"{name}.object.json") as f:
            d = json.load(f)
        if self.__class__ == Type:
            return TypeRegistry.type_from_dict(d)
        return self.instance_from_dict(d)

    def instance_to_dict(self, obj):
        raise NotImplementedError

    def instance_from_dict(self, d):
        raise NotImplementedError

    @classmethod
    def make(cls, kwargs={}):
        return cls._make(cls, kwargs)

    @staticmethod
    def _make(cls, kwargs={}):
        raise Exception("Please import `weave` to use `Type.make`.")


# _PlainStringNamedType should only be used for backward compatibility with
# legacy WeaveJS code.
class _PlainStringNamedType(Type):
    def to_dict(self):
        # A basic type is serialized as just its string name.
        return self.name


class BasicType(_PlainStringNamedType):
    def save_instance(self, obj, artifact, name):
        if artifact is None:
            raise errors.WeaveSerializeError(
                "save_instance invalid when artifact is None for type: %s" % self
            )
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.object.json") as f:
            return json.load(f)

    def __repr__(self):
        return "<%s>" % self.__class__.name


class Invalid(BasicType):
    name = "invalid"

    def assign_type(self, next_type):
        return False


class UnknownType(BasicType):
    name = "unknown"

    def _assign_type_inner(self, next_type):
        return True


# TODO: Tim has this as ConstType(None), but how is that serialized?


class NoneType(BasicType):
    name = "none"
    instance_classes = [type(None), box.BoxedNone]

    def save_instance(self, obj, artifact, name):
        # BoxedNone is actually a box, not a subclass of bool, since
        # we can't subclass bool in Python. So we unbox it here.
        if isinstance(obj, box.BoxedNone):
            obj = obj.val
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(obj, f)


# TODO: use this seminal value all the time! We use it in is_optional()
#     to check if something is unioned with NoneType. But its too easy for
#     users to instantiate a different version of this. Maybe could muck
#     with Python's __new__ to fix that
none_type = NoneType()


class Any(BasicType):
    name = "any"

    def assign_type(self, next_type):
        return True


@dataclasses.dataclass(frozen=True)
class Const(Type):
    name = "const"
    val_type: Type
    val: typing.Any

    def __getattr__(self, attr):
        return getattr(self.val_type, attr)

    @classmethod
    def type_of_instance(cls, obj):
        return cls(obj)

    def assign_type(self, next_type):
        if isinstance(next_type, Const):
            # This does a check on class equality, so won't work for
            # fancier types. We can fix later if we need to.
            if self.__class__ != next_type.__class__:
                return False
            if self.val == next_type.val:
                return True
        return False

    @classmethod
    def from_dict(cls, d):
        return cls(TypeRegistry.type_from_dict(d["valType"]), d["val"])

    def _to_dict(self):
        return {"valType": self.val_type.to_dict(), "val": self.val}

    def __str__(self):
        return "<Const %s %s>" % (self.val_type, self.val)

    def __repr__(self):
        return "<Const %s %s>" % (self.val_type, self.val)


class String(BasicType):
    name = "string"
    instance_classes = str


class Number(BasicType):
    name = "number"


class Float(Number):
    instance_classes = float
    name = "float"

    def _assign_type_inner(self, other_type: Type):
        # Float if either side is a number
        if isinstance(other_type, Float) or isinstance(other_type, Int):
            return True
        else:
            return False


class Int(Number):
    name = "int"
    instance_classes = int

    @classmethod
    def is_instance(cls, obj):
        # Special case, in Python bool isinstance of obj!
        if type(obj) == bool:
            return False
        return super().is_instance(obj)

    def _assign_type_inner(self, other_type: Type):
        # Become Float if rhs is Float
        if isinstance(other_type, Float):
            return True
        elif isinstance(other_type, Int):
            return True
        else:
            return False


class Boolean(BasicType):
    instance_classes = [bool, box.BoxedBool]
    name = "boolean"

    def save_instance(self, obj, artifact, name):
        # BoxedBool is actually a box, not a subclass of bool, since
        # we can't subclass bool in Python. So we unbox it here.
        if isinstance(obj, box.BoxedBool):
            obj = obj.val
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(obj, f)


@dataclasses.dataclass(frozen=True)
class UnionType(Type):
    name = "union"

    members: list[Type]

    def __init__(self, *members):
        all_members = []
        for mem in members:
            if isinstance(mem, UnionType):
                for memmem in mem.members:
                    if memmem not in all_members:
                        all_members.append(memmem)
            else:
                if mem not in all_members:
                    all_members.append(mem)
        object.__setattr__(self, "members", all_members)

    def __eq__(self, other):
        if not isinstance(other, UnionType):
            return False
        return set(self.members) == set(other.members)

    def _assign_type_inner(self, other):
        if isinstance(other, UnionType):
            if not all(self.assign_type(member) for member in other.members):
                return False
            return True
        if any(member.assign_type(other) for member in self.members):
            return True
        return False

    # def instance_to_py(self, obj):
    #     # Figure out which union member this obj is, and delegate to that
    #     # type.
    #     for member_type in self.members:
    #         if member_type.type_of(obj) is not None:
    #             return member_type.instance_to_py(obj)
    #     raise Exception('invalid')
    @classmethod
    def from_dict(cls, d):
        return cls(*[TypeRegistry.type_from_dict(mem) for mem in d["members"]])

    def _to_dict(self):
        return {"members": [mem.to_dict() for mem in self.members]}


@dataclasses.dataclass(frozen=True)
class List(Type):
    name = "list"
    instance_classes = [set, list]

    object_type: Type

    @classmethod
    def type_of_instance(cls, obj):
        if not obj:
            return cls(UnknownType())
        list_obj_type = TypeRegistry.type_of(obj[0])
        for item in obj[1:]:
            obj_type = TypeRegistry.type_of(item)
            if obj_type is None:
                raise Exception("can't detect type for object: %s" % item)
            list_obj_type = merge_types(list_obj_type, obj_type)
        return cls(list_obj_type)

    def _assign_type_inner(self, next_type):
        if isinstance(next_type, List) and next_type.object_type == UnknownType():
            return True
        return super()._assign_type_inner(next_type)

    def save_instance(self, obj, artifact, name):
        serializer = mappers_python.map_to_python(self, artifact)
        result = serializer.apply(obj)
        with artifact.new_file(f"{name}.list.json") as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.list.json") as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        return mapper.apply(result)


@dataclasses.dataclass(frozen=True)
class TypedDict(Type):
    name = "typedDict"
    instance_classes = [dict]
    property_types: dict[str, Type]

    def __hash__(self):
        # Can't hash property_types by default because dict is not hashable
        return hash(tuple((k, v) for k, v in self.property_types.items()))

    def _assign_type_inner(self, other_type):
        if not isinstance(other_type, TypedDict):
            return False

        for k, ptype in self.property_types.items():
            if k not in other_type.property_types or not ptype.assign_type(
                other_type.property_types[k]
            ):
                return False
        return True

    def _to_dict(self):
        property_types = {}
        for key, type_ in self.property_types.items():
            property_types[key] = type_.to_dict()
        return {"propertyTypes": property_types}

    @classmethod
    def from_dict(cls, d):
        property_types = {}
        for key, type_ in d["propertyTypes"].items():
            property_types[key] = TypeRegistry.type_from_dict(type_)
        return cls(property_types)

    @classmethod
    def type_of_instance(cls, obj):
        property_types = {}
        for k, v in obj.items():
            property_types[k] = TypeRegistry.type_of(v)
        return cls(property_types)

    def save_instance(self, obj, artifact, name):
        serializer = mappers_python.map_to_python(self, artifact)
        result = serializer.apply(obj)
        with artifact.new_file(f"{name}.typedDict.json") as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(self, artifact, name, extra=None):
        # with artifact.open(f'{name}.type.json') as f:
        #     obj_type = TypeRegistry.type_from_dict(json.load(f))
        with artifact.open(f"{name}.typedDict.json") as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        return mapper.apply(result)


@dataclasses.dataclass(frozen=True)
class Dict(Type):
    name = "dict"

    key_type: Type
    object_type: Type

    def __post_init__(self):
        # Note this differs from Python's Dict in that keys are always strings!
        # TODO: consider if we can / should accept key_type. Would make JS side
        # harder since js objects can only have string keys.
        if not isinstance(self.key_type, String):
            raise Exception("Dict only supports string keys!")

    def _assign_type_inner(self, other_type):
        if isinstance(other_type, Dict):
            next_key_type = self.key_type.assign_type(other_type.key_type)
            if not next_key_type:
                return False
            next_value_type = self.object_type.assign_type(other_type.object_type)
            if not next_value_type:
                return False
            return True
        else:
            # TODO: we could handle TypedDict here.
            return False

    @classmethod
    def type_of_instance(cls, obj):
        value_type = UnknownType()
        for k, v in obj.items():
            if not isinstance(k, str):
                raise Exception("Dict only supports string keys!")
            value_type = value_type.assign_type(TypeRegistry.type_of(v))
        return cls(String(), value_type)


@dataclasses.dataclass(frozen=True)
class ObjectType(Type):
    # TODO: Maybe this belongs on Type?
    _base_type: typing.ClassVar[Type] = Invalid()

    def property_types(self):
        return {}

    @classmethod
    def type_of_instance(cls, obj):
        variable_prop_types = {}
        for prop_name in cls.type_vars():
            prop_type = TypeRegistry.type_of(getattr(obj, prop_name))
            # print("TYPE_OF", cls, prop_name, prop_type, type(getattr(obj, prop_name)))
            variable_prop_types[prop_name] = prop_type
        return cls(**variable_prop_types)

    def _to_dict(self):
        d = super()._to_dict()

        # NOTE: we unnecessarily store all property_types in the serialized
        # type! We actually only need to store type_vars() which super() takes
        # care of, but WeaveJS does not currently have a type registry in which
        # to lookup a named type to figure out its property types. So just
        # serialize all property types all the time for now. This adds a lot
        # of redundant information that needs to go over the network.
        # TODO: Fix
        property_types = {}
        for k, prop_type in self.property_types().items():
            property_types[to_weavejs_typekey(k)] = prop_type.to_dict()
        d["_property_types"] = property_types

        if not isinstance(self._base_type, Invalid):
            d["_base_type"] = self._base_type.to_dict()
        return d

    # def assign_type(self):
    #     # TODO
    #     pass

    def save_instance(self, obj, artifact, name):
        serializer = mappers_python.map_to_python(self, artifact)

        result = serializer.apply(obj)
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.object.json") as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        return mapper.apply(result)


class TaggedValue:
    tag: dict[str, typing.Any]
    value: typing.Any

    def __new__(cls, tag: dict[str, typing.Any], value: typing.Any):
        if isinstance(value, TaggedValue):
            tag = {**value.tag, **tag}
            value = value.value
        obj_cls = value.__class__
        copy_obj = box.box(copy.copy(value))
        copy_obj.__class__ = type(
            f"Tagged{obj_cls.__name__}",
            (
                TaggedValue,
                copy_obj.__class__,
            ),
            {},
        )
        copy_obj = typing.cast(TaggedValue, copy_obj)
        copy_obj.value = value
        copy_obj.tag = tag
        return copy_obj

    def __init__(self, *args, **kwargs):
        pass


@dataclasses.dataclass(frozen=True)
class TaggedType(ObjectType):
    name = "tagged"
    tag: TypedDict = TypedDict({})
    value: Type = Any()

    instance_classes = [TaggedValue]

    def property_types(self):
        return {"tag": self.tag, "value": self.value}

    @classmethod
    def from_dict(cls, d):
        return cls(
            TypeRegistry.type_from_dict(d["tag"]),
            TypeRegistry.type_from_dict(d["value"]),
        )


@dataclasses.dataclass(frozen=True)
class Function(Type):
    name = "function"

    input_types: dict[str, Type]
    output_type: Type

    @classmethod
    def type_of_instance(cls, obj):
        # instance is graph.Node
        # TODO: get input variable types!
        return cls({}, obj.type)

    @classmethod
    def from_dict(cls, json):
        input_types = {
            pname: TypeRegistry.type_from_dict(ptype)
            for (pname, ptype) in json["inputTypes"].items()
        }
        return cls(input_types, TypeRegistry.type_from_dict(json["outputType"]))

    def _to_dict(self):
        input_types = {k: v.to_dict() for (k, v) in self.input_types.items()}
        return {"inputTypes": input_types, "outputType": self.output_type.to_dict()}


@dataclasses.dataclass(frozen=True)
class RefType(Type):
    # RefType intentionally does not include the type of the object it
    # points to. Doing so naively results in a type explosion. We may
    # want to include it in the future, but we'll need to shrink it, for
    # example by disallowing unions (replacing with them with uknown or a
    # type variable)
    def __repr__(self):
        return "<%s>" % self.__class__.name


@dataclasses.dataclass(frozen=True)
class LocalArtifactRefType(RefType):
    pass


@dataclasses.dataclass(frozen=True)
class WandbArtifactRefType(RefType):
    pass


class WBTable(Type):
    name = "wbtable"


def is_json_compatible(type_):
    if isinstance(type_, List):
        return is_json_compatible(type_.object_type)
    elif isinstance(type_, Dict):
        return is_json_compatible(type_.object_type)
    elif isinstance(type_, TypedDict):
        return all(t for t in type_.property_types.values())
    else:
        return isinstance(type_, BasicType)


def optional(type_):
    return UnionType(none_type, type_)


def is_optional(type_):
    return isinstance(type_, UnionType) and none_type in type_.members


def non_none(type_):
    if type_ == none_type:
        return Invalid()
    if is_optional(type_):
        new_members = [m for m in type_.members if m != none_type]
        # TODO: could put this logic in UnionType.from_members ?
        if len(new_members) == 0:
            # Should never have a length one union to start with
            raise Exception("programming error")
        elif len(new_members) == 1:
            return new_members[0]
        else:
            return UnionType(new_members)
    return type_


def string_enum_type(*vals):
    return UnionType(*[Const(String(), v) for v in vals])


RUN_STATE_TYPE = string_enum_type("pending", "running", "finished", "failed")

# TODO: get rid of all the underscores. This is another
#    conflict with making ops automatically lazy
@dataclasses.dataclass(frozen=True)
class RunType(ObjectType):
    inputs: Type = TypedDict({})
    history: Type = List(TypedDict({}))
    output: Type = Any()

    def property_types(self):
        return {
            "id": String(),
            "op_name": String(),
            "state": RUN_STATE_TYPE,
            "prints": List(String()),
            "inputs": self.inputs,
            "history": self.history,
            "output": self.output,
        }


@dataclasses.dataclass(frozen=True)
class FileType(ObjectType):
    name = "file"

    extension: String = String()
    wb_object_type: dataclasses.InitVar[String] = String()

    def _to_dict(self):
        # NOTE: js_compat
        # In the js Weave code, file is a non-standard type that
        # puts a const string at extension as just a plain string.
        d = super()._to_dict()
        if isinstance(self.extension, Const):
            d["extension"] = self.extension.val
        if isinstance(self.wb_object_type, Const):
            d["wbObjectType"] = {"type": self.wb_object_type.val}
        return d

    @classmethod
    def from_dict(cls, d):
        # NOTE: js_compat
        # In the js Weave code, file is a non-standard type that
        # puts a const string at extension as just a plain string.
        d = {i: d[i] for i in d if i != "type"}
        extension = String()
        if "extension" in d:
            extension = TypeRegistry.type_from_dict(
                {
                    "type": "const",
                    "valType": "string",
                    "val": d["extension"],
                }
            )
        wb_object_type = None
        if "wbObjectType" in d:
            wb_object_type = TypeRegistry.type_from_dict(
                {
                    "type": "const",
                    "valType": "string",
                    "val": d["wbObjectType"]["type"],
                }
            )
        return cls(extension, wb_object_type)

    def property_types(self):
        return {
            "extension": self.extension,
            "wb_object_type": self.extension,
        }


@dataclasses.dataclass(frozen=True)
class SubDirType(ObjectType):
    # TODO doesn't match frontend
    name = "subdir"

    file_type: FileType = FileType()

    def property_types(self):
        return {
            "fullPath": String(),
            "size": Int(),
            "dirs": Dict(String(), Int()),
            "files": Dict(String(), self.file_type),
        }


class DirType(ObjectType):
    # Fronend src/model/types.ts switches on this (and PanelDir)
    # TODO: We actually want to be localdir here. But then the
    # frontend needs to use a different mechanism for type checking
    name = "dir"

    def __init__(self):
        pass

    def property_types(self):
        return {
            "fullPath": String(),
            "size": Int(),
            "dirs": Dict(String(), SubDirType()),
            "files": Dict(String(), FileType()),
        }


def merge_types(a: Type, b: Type) -> Type:
    """Given two types return a new type that both are assignable to

    There are design decisions we can make here. We could choose to produce
    a less specific type when merging TypedDicts for example, to keep
    the type size smaller.
    """
    if a == b:
        return a
    if isinstance(a, TypedDict) and isinstance(b, TypedDict):
        all_keys_dict = {}
        for k in a.property_types.keys():
            all_keys_dict[k] = True
        for k in b.property_types.keys():
            all_keys_dict[k] = True

        next_prop_types = {}
        for key in all_keys_dict.keys():
            self_prop_type = a.property_types.get(key, none_type)
            other_prop_type = b.property_types.get(key, none_type)
            next_prop_type = self_prop_type
            if not self_prop_type.assign_type(other_prop_type):
                next_prop_type = UnionType(self_prop_type, other_prop_type)
            next_prop_types[key] = next_prop_type
        return TypedDict(next_prop_types)
    return UnionType(a, b)


def union(*members: Type) -> Type:
    t = UnionType(*members)
    if len(t.members) == 1:
        return t.members[0]
    return t


def is_list_like(t: Type) -> bool:
    non_none_t = non_none(t)
    return isinstance(non_none_t, List) or non_none_t.name == "ArrowWeaveList"


def is_custom_type(t: Type) -> bool:
    return not (
        isinstance(t, BasicType)
        or isinstance(t, ObjectType)
        or isinstance(t, TypedDict)
        or isinstance(t, List)
        or isinstance(t, UnionType)
    )


NumberBinType = TypedDict({"start": Float(), "stop": Float()})
