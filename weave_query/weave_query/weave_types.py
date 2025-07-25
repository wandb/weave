import contextvars
import dataclasses
import datetime
import functools
import inspect
import json
import keyword
import typing
from collections.abc import Iterable

import pydantic
from dateutil.parser import isoparse

from weave_query import (
    box,
    context_state,
    errors,
    mappers_python,
    object_type_ref_util,
)
from weave_query import timestamp as weave_timestamp

if typing.TYPE_CHECKING:
    from weave_query import artifact_base
    from weave_query.artifact_fs import FilesystemArtifact

    from weave_query import weave_inspector


def to_weavejs_typekey(k: str) -> str:
    if k == "object_type":
        return "objectType"
    elif k == "property_types":
        return "propertyTypes"
    return k


def js_to_py_typename(typename: str) -> str:
    # WeaveJS overrides the table column type if the column name is id-like. See
    # use of `SPECIAL_ID_COLUMN_NAMES` in `mediaTypes.ts`. Unlike other types,
    # the "id" type does not describe the underlying data type. Furthermore,
    # there are no ops based on the "id" type. For that reason, I opted to not
    # put the id type in the type system for now, and just hap it to string.
    if typename == "id":
        return "string"
    return typename


def all_subclasses(cls):  # type: ignore
    # Note using a list here... this doesn't dedupe star pattern!
    # But it does preserve tree order.
    return list(cls.__subclasses__()) + [
        s for c in cls.__subclasses__() for s in all_subclasses(c)
    ]


def get_type_classes():  # type: ignore
    return all_subclasses(Type)


def instance_class_to_potential_type_map():  # type: ignore
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
def instance_class_to_potential_type(cls):  # type: ignore
    mapping = instance_class_to_potential_type_map()
    exact_type_classes = mapping.get(cls)
    if exact_type_classes is not None:
        return exact_type_classes
    result = []
    for instance_class, type_classes in mapping.items():
        try:
            if issubclass(cls, instance_class):
                result += [tc.typeclass_of_class(cls) for tc in type_classes]
        except TypeError:
            return [UnknownType()]
    return result


@functools.cache
def type_name_to_type_map():  # type: ignore
    res = {}
    type_classes = get_type_classes()
    for type_class in type_classes:
        name = type_class.name
        if name is not None:
            res[name] = type_class
    return res


@functools.cache
def type_name_to_type(type_name):  # type: ignore
    mapping = type_name_to_type_map()
    return mapping.get(js_to_py_typename(type_name))


# Used to make a modified type_of function that returns RefType for any reffed
# objects. See type_of_with_refs()
_reffed_type_is_ref = contextvars.ContextVar("_reffed_type_is_ref", default=False)


class TypeRegistry:
    @staticmethod
    def has_type(obj):  # type: ignore
        return bool(instance_class_to_potential_type(type(obj)))

    @staticmethod
    def type_class_of(obj):  # type: ignore
        type_classes = instance_class_to_potential_type(type(obj))
        if not type_classes:
            # return UnknownType()
            raise errors.WeaveTypeError("no Type for obj: %s" % obj)
        return type_classes[-1]

    @staticmethod
    def type_of(obj: typing.Any) -> "Type":  # type: ignore
        from weave_query import ref_base

        if (
            context_state.ref_tracking_enabled()
            and _reffed_type_is_ref.get()
            and not isinstance(obj, ref_base.Ref)
        ):
            obj_ref = ref_base.get_ref(obj)
            if obj_ref is not None:
                # Directly construct the RefTypeClass instead of doing
                # type_of(obj_ref), since a) that would recurse and b)
                # type_of(<ref>) calls .type on the ref, which may try to read
                # data to get the data. We already have the obj here, so we can
                # compute its type directly.
                RefTypeClass = instance_class_to_potential_type(obj_ref.__class__)[-1]  # type: ignore
                return RefTypeClass(type_of_without_refs(obj))

        obj_type = type_name_to_type("tagged").type_of(obj)
        if obj_type is not None:
            return obj_type

        # use reversed instance_class_to_potential_type so our result
        # is the most specific type.

        # The type of graph.Node objects is Function, but we also mixin
        # NodeMethodsClass with Node, which may also have a Weave type.
        # Therefore we have multiple valid types. But we need type_of() to
        # be function in that case. Ie when a Node is mixed in, its lazy
        # representation of whatever the type is, not the actual type.
        #
        # TODO: Its a small that we need to hardcode here. Fix this.
        potential_types = instance_class_to_potential_type(type(obj))  # type: ignore
        if "function" in (t.name for t in potential_types):
            potential_types = [Function]

        for type_ in reversed(potential_types):
            obj_type = type_.type_of(obj)
            if obj_type is not None:
                return obj_type
        # No TypeError here, return UnknownType
        return UnknownType()

    @staticmethod
    def type_from_dict(d: typing.Union[str, dict]) -> "Type":  # type: ignore
        if is_relocatable_object_type(d):
            d = typing.cast(dict, d)
            return deserialize_relocatable_object_type(d)
        # The javascript code sends simple types as just strings
        # instead of {'type': 'string'} for example
        type_name = d["type"] if isinstance(d, dict) else d
        type_ = type_name_to_type(type_name)
        if type_ is None:
            # We used to raise WeaveServializeError here. Now we return UnknownType
            # instead, so the server can load types that have types that are not
            # present on the server within them (e.g. a user has defined a type in their
            # code and published a top level object containing an attribute of that type,
            # we want to be able to load the outer object without crashing)
            return UnknownType()
        return type_.from_dict(d)


def _clear_global_type_class_cache():  # type: ignore
    instance_class_to_potential_type.cache_clear()
    type_name_to_type_map.cache_clear()
    type_name_to_type.cache_clear()


def _cached_hash(self):  # type: ignore
    try:
        return self.__dict__["_hash"]
    except KeyError:
        hashed = hash((self.__class__, self._hashable()))
        self.__dict__["_hash"] = hashed
        return hashed


class classproperty(object):
    def __init__(self, f):  # type: ignore
        self.f = f

    def __get__(self, obj, owner):  # type: ignore
        return self.f(owner)


# Addapted from https://stackoverflow.com/questions/18126552/how-to-run-code-when-a-class-is-subclassed
class _TypeSubclassWatcher(type):
    def __init__(cls, name, bases, clsdict):  # type: ignore
        # This code will run whenever `Type` is subclassed!
        # Bust the cache!
        _clear_global_type_class_cache()
        super(_TypeSubclassWatcher, cls).__init__(name, bases, clsdict)

        # Set _base_type to the first base class
        if bases and bases[0] != Type:
            if cls.__dict__.get("_base_type") is None:
                cls._base_type = bases[0]

        # Override the dataclass __hash__ with our own version
        cls.__hash__ = _cached_hash


@dataclasses.dataclass(frozen=True)
class Type(metaclass=_TypeSubclassWatcher):
    # This is like Typescript "extends", and is populated by default by
    # Python inheritance in our metaclass.
    _base_type: typing.ClassVar[typing.Optional[typing.Type["Type"]]] = None

    instance_class: typing.ClassVar[typing.Optional[type]]
    instance_classes: typing.ClassVar[typing.Union[type, typing.List[type], None]] = (
        None
    )

    _type_attrs = None
    _hash = None

    def _hashable(self):  # type: ignore
        return tuple((k, hash(t)) for k, t in self.type_vars_tuple)

    def __lt__(self, other):  # type: ignore
        return hash(self) < hash(other)

    def __repr__(self) -> str:  # type: ignore
        return f"{self.__class__.__name__}()"

    def __name__(self) -> str:  # type: ignore
        return self.__repr__()

    def simple_str(self) -> str:  # type: ignore
        return str(self)

    @classmethod
    def _instance_classes(cls) -> typing.Sequence[type]:  # type: ignore
        """Helper to get instance_classes as iterable."""
        if cls.instance_classes is None:
            return ()
        if isinstance(cls.instance_classes, Iterable):
            return cls.instance_classes
        return (cls.instance_classes,)

    @classmethod
    def type_attrs(cls):  # type: ignore
        type_attrs = []
        for field in dataclasses.fields(cls):
            if (inspect.isclass(field.type) and issubclass(field.type, Type)) or (
                field.type.__origin__ == typing.Union
                and any(issubclass(a, Type) for a in field.type.__args__)
            ):
                type_attrs.append(field.name)
        return type_attrs

    @property
    def type_vars_tuple(self):  # type: ignore
        type_vars = []
        for field in self.type_attrs():
            type_vars.append((field, getattr(self, field)))
        return tuple(type_vars)

    @property
    def type_vars(self) -> dict[str, "Type"]:  # type: ignore
        return dict(self.type_vars_tuple)

    @classmethod
    def root_type_class(cls) -> type["Type"]:  # type: ignore
        if cls._base_type is None:
            return cls
        base_type_class = cls._base_type.root_type_class()
        if base_type_class.__name__ == "ObjectType":
            return cls
        return base_type_class

    @classmethod
    def is_instance(cls, obj):  # type: ignore
        for ic in cls._instance_classes():
            if isinstance(obj, ic):
                return ic
        return None

    @classmethod
    def typeclass_of_class(cls, check_class):  # type: ignore
        return cls

    @classmethod
    def type_of(cls, obj) -> typing.Optional["Type"]:  # type: ignore
        if not cls.is_instance(obj):  # type: ignore[no-untyped-call]
            return None
        return cls.type_of_instance(obj)  # type: ignore[no-untyped-call]

    @classmethod
    def type_of_instance(cls, obj):  # type: ignore
        # Default implementation for Types that take no arguments.
        return cls()

    @classproperty
    def name(cls):  # type: ignore
        if cls == Type:
            return "type"
        return cls.__name__.removesuffix("Type")

    @property  # type: ignore[no-redef]
    def instance_class(self):  # type: ignore
        return self._instance_classes()[-1]

    def assign_type(self, next_type: "Type") -> bool:  # type: ignore
        # assign_type needs to be as fast as possible, so there are optimizations
        # throughout this code path, like checking for class equality instead of using isinstance

        # Unions or union-like things (tagged unions) must be handled first
        if next_type.name == "tagged":
            next_type = next_type._assignment_form  # type: ignore

        is_assignable_to = next_type._is_assignable_to(self)
        if is_assignable_to:
            return True

        # Check class attribute directly instead of isinstance for performance
        if next_type.__class__ == UnionType:
            return all(self.assign_type(t) for t in next_type.members)  # type: ignore
        if self.__class__ == UnionType:
            return any(t.assign_type(next_type) for t in self.members)  # type: ignore

        return self._assign_type_inner(next_type)

    def _is_assignable_to(self, other_type) -> typing.Optional[bool]:  # type: ignore
        return None

    def _assign_type_inner(self, next_type: "Type") -> bool:  # type: ignore
        # First check that we match next_type class or one of
        # its bases.
        next_type_class = next_type.__class__
        while True:
            # __name__ based comparison instead of class equality, since we
            # dynamically create ObjectType classes when deserializing
            if self.__class__.__name__ == next_type_class.__name__:
                break
            elif next_type_class._base_type is None:
                # nothing left in base chain, no match
                return False
            next_type_class = next_type_class._base_type

        # Now check that all type vars match
        for prop_name in self.type_vars:
            if not hasattr(next_type, prop_name):
                return False
            # Name fixup for ObjectType, see ObjectType comments.
            if prop_name == "name":
                prop_name = "_name"
            if not getattr(self, prop_name).assign_type(getattr(next_type, prop_name)):
                return False
        return True

    @classmethod
    def class_to_dict(cls) -> dict[str, typing.Any]:  # type: ignore
        d = {"type": cls.name}
        if cls._base_type is not None:
            d["_base_type"] = cls._base_type.class_to_dict()
        return d

    def to_dict(self) -> typing.Union[dict, str]:  # type: ignore
        d = {"type": self.name}
        d.update(self._to_dict())
        return d

    def _to_dict(self) -> dict:  # type: ignore
        fields = dataclasses.fields(self.__class__)
        type_props = {}
        if self._base_type is not None:
            type_props["_base_type"] = {"type": self._base_type.name}
            if self._base_type._base_type is not None:
                type_props["_base_type"]["_base_type"] = {
                    "type": self._base_type._base_type.name
                }
        for field in fields:
            # TODO: I really don't like this change. Only needed because
            # FileType has optional fields... Remove?
            attr = getattr(self, field.name)
            if not attr:
                continue
            type_props[to_weavejs_typekey(field.name)] = attr.to_dict()
        return type_props

    @classmethod
    def from_dict(cls, d):  # type: ignore
        fields = dataclasses.fields(cls)
        type_attrs = {}
        for field in fields:
            field_name = to_weavejs_typekey(field.name)
            if field_name in d:
                type_attrs[field.name] = TypeRegistry.type_from_dict(d[field_name])
        return cls(**type_attrs)

    def save_instance(  # type: ignore
        self, obj, artifact, name
    ) -> typing.Optional[typing.Union[list[str], "artifact_base.ArtifactRef"]]:
        d = None
        try:
            d = self.instance_to_dict(obj)  # type: ignore[no-untyped-call]
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

    def load_instance(  # type: ignore
        self,
        artifact: "FilesystemArtifact",
        name: str,
        extra: typing.Optional[list[str]] = None,
    ) -> typing.Any:
        with artifact.open(f"{name}.object.json") as f:
            d = json.load(f)
        return self.instance_from_dict(d)  # type: ignore[no-untyped-call]

    def instance_to_dict(self, obj):  # type: ignore
        raise NotImplementedError

    def instance_from_dict(self, d):  # type: ignore
        raise NotImplementedError

    @classmethod
    def make(cls, kwargs={}):  # type: ignore
        return cls._make(cls, kwargs)

    @staticmethod
    def _make(cls, kwargs={}):  # type: ignore
        raise Exception("Please import `weave` to use `Type.make`.")

    def _inspect(self) -> "weave_inspector.TypeInspector":  # type: ignore
        """Only intended to be used by developers to help debug the graph."""
        # Circular import, so we do it here.
        from weave_query import weave_inspector

        return weave_inspector.TypeInspector(self)


# _PlainStringNamedType should only be used for backward compatibility with
# legacy WeaveJS code.
class _PlainStringNamedType(Type):
    def to_dict(self):  # type: ignore
        # A basic type is serialized as just its string name.
        return self.name


class BasicType(_PlainStringNamedType):
    def save_instance(self, obj, artifact, name):  # type: ignore
        if artifact is None:
            raise errors.WeaveSerializeError(
                "save_instance invalid when artifact is None for type: %s" % self
            )
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(obj, f)

    def load_instance(self, artifact, name, extra=None):  # type: ignore
        with artifact.open(f"{name}.object.json") as f:
            return json.load(f)


class InvalidPy:
    pass


class Invalid(BasicType):
    name = "invalid"

    instance_classes = InvalidPy


class UnknownType(BasicType):
    name = "unknown"

    # TODO: we should strictly define the rules for unknown types. As is, we
    # allow anything to be assigned to unknown, but unknown can't be assigned to
    # anything else. This is effectively the same as Any. Is that correct?
    # Currently we have a single special case in List assign: `if
    # isinstance(next_type, List) and next_type.object_type == UnknownType():`
    #
    # I _think_ we want 'unknown' to be assigned to anything, and this would
    # allow us to remove the `_assign_type_inner` special case in List.
    #
    # This change would need to be implemented in the core `Type.assign_type`
    # method
    def _assign_type_inner(self, next_type):  # type: ignore
        return True


# TODO: Tim has this as ConstType(None), but how is that serialized?


class NoneType(BasicType):
    name = "none"
    instance_classes = [type(None), box.BoxedNone]

    # If we're using NoneType in a place where we expect a list, the object_type
    # of that list is also NoneType, due to nullability.
    @property
    def object_type(self):  # type: ignore
        return NoneType()

    def save_instance(self, obj, artifact, name):  # type: ignore
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

    def _assign_type_inner(self, next_type):  # type: ignore
        return True


@dataclasses.dataclass(frozen=True)
class Const(Type):
    name = "const"
    val_type: Type
    val: typing.Any

    def __post_init__(self):  # type: ignore
        if isinstance(self.val_type, UnionType):
            # Const Unions are invalid. If something is Const, that means we know what its value
            # is, which means it is definitely not a Union. Replace val_type with the actual type
            # here.
            self.__dict__["val_type"] = TypeRegistry.type_of(self.val)

    def _hashable(self):  # type: ignore
        val_id = id(self.val)
        try:
            val_id = hash(self.val)
        except TypeError:
            pass
        return (hash(self.val_type), val_id)

    def __getattr__(self, attr):  # type: ignore
        return getattr(self.val_type, attr)

    @classmethod
    def type_of_instance(cls, obj):  # type: ignore
        return cls(TypeRegistry.type_of(obj.val), obj.val)

    def _is_assignable_to(self, other_type) -> typing.Optional[bool]:  # type: ignore
        if other_type.__class__ != Const:
            return other_type.assign_type(self.val_type)
        return None

    def _assign_type_inner(self, next_type):  # type: ignore
        if isinstance(next_type, Const):
            # This does a check on class equality, so won't work for
            # fancier types. We can fix later if we need to.
            if self.__class__ != next_type.__class__:
                return False
            if self.val == None or self.val == next_type.val:
                return True

        # TODO: should be "return False"! But we allow assign non const
        #     to const now. Because type_of("x") is String, not Const(String, "x").
        #     Why? Because we don't want to detect a column of non-uniform
        #     strings as a giant union.
        #     For example see test_plot_constants_assign
        return self.val_type.assign_type(next_type)

    @classmethod
    def from_dict(cls, d):  # type: ignore
        w_type = TypeRegistry.type_from_dict(d["valType"])
        val = d["val"]
        # try:
        #     val = w_type.instance_from_dict(val)
        # except NotImplementedError:
        #     pass
        return cls(w_type, val)

    def _to_dict(self):  # type: ignore
        val = self.val
        # try:
        #     val = self.val_type.instance_to_dict(val)
        # except NotImplementedError:
        #     pass
        return {"valType": self.val_type.to_dict(), "val": val}

    def __repr__(self):  # type: ignore
        return "Const(%s, %s)" % (self.val_type, self.val)


class String(BasicType):
    name = "string"
    instance_classes = str

    # Just for String, we use a Const Type
    # TODO: this sucks! Maybe we need a const object?
    # but how does user code know to use it?
    # @classmethod
    # def type_of_instance(cls, obj):
    #     return Const(cls(), obj)


# TODO: support this in weave0. for weave1 use only now (dont send over wire)
class Bytes(BasicType):
    name = "bytes"
    instance_classes = bytes


class Number(BasicType):
    name = "number"


class Float(Number):
    instance_classes = float
    name = "float"

    def _assign_type_inner(self, other_type: Type):  # type: ignore
        # Float if either side is a number
        return isinstance(other_type, Number)


class Int(Number):
    name = "int"
    instance_classes = int

    @classmethod
    def is_instance(cls, obj):  # type: ignore
        # Special case, in Python bool isinstance of obj!
        if type(obj) == bool:
            return False
        return super().is_instance(obj)

    def _assign_type_inner(self, other_type: Type):  # type: ignore
        # Become Float if rhs is Float
        return isinstance(other_type, Number) and not isinstance(other_type, Float)


class Boolean(BasicType):
    instance_classes = [bool, box.BoxedBool]
    name = "boolean"

    def save_instance(self, obj, artifact, name):  # type: ignore
        # BoxedBool is actually a box, not a subclass of bool, since
        # we can't subclass bool in Python. So we unbox it here.
        if isinstance(obj, box.BoxedBool):
            obj = obj.val
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(obj, f)


class LegacyDate(Type):
    # TODO: For historic reasons we had "date" and "timestamp" types.  Now we only
    # use "timestamp" but we need to keep this around for backwards compatibility.
    name = "date"

    def save_instance(self, obj, artifact, name):  # type: ignore
        if artifact is None:
            raise errors.WeaveSerializeError(
                "save_instance invalid when artifact is None for type: %s" % self
            )
        with artifact.new_file(f"{name}.object.json") as f:
            v = weave_timestamp.python_datetime_to_ms(obj)
            json.dump(v, f)

    def load_instance(self, artifact, name, extra=None):  # type: ignore
        with artifact.open(f"{name}.object.json") as f:
            v = json.load(f)
            return weave_timestamp.ms_to_python_datetime(v)


class TimeDelta(Type):
    name = "timedelta"
    instance_classes = datetime.timedelta

    def save_instance(self, obj: datetime.timedelta, artifact, name):  # type: ignore
        if artifact is None:
            raise errors.WeaveSerializeError(
                "save_instance invalid when artifact is None for type: %s" % self
            )
        with artifact.new_file(f"{name}.object.json") as f:
            # Uses internal python representation of timedelta for serialization
            v = [obj.days, obj.seconds, obj.microseconds]
            json.dump(v, f)

    def load_instance(self, artifact, name, extra=None):  # type: ignore
        with artifact.open(f"{name}.object.json") as f:
            [days, seconds, microseconds] = json.load(f)
            return datetime.timedelta(days, seconds, microseconds)


class Timestamp(Type):
    name = "timestamp"
    instance_classes = datetime.datetime

    def from_isostring(self, iso: str) -> datetime.datetime:  # type: ignore
        tz_naive = isoparse(iso)
        return tz_naive.replace(tzinfo=datetime.timezone.utc)

    def save_instance(self, obj, artifact, name):  # type: ignore
        if artifact is None:
            raise errors.WeaveSerializeError(
                "save_instance invalid when artifact is None for type: %s" % self
            )
        with artifact.new_file(f"{name}.object.json") as f:
            v = weave_timestamp.python_datetime_to_ms(obj)
            json.dump(v, f)

    def load_instance(self, artifact, name, extra=None):  # type: ignore
        with artifact.open(f"{name}.object.json") as f:
            v = json.load(f)
            return weave_timestamp.ms_to_python_datetime(v)


@dataclasses.dataclass(frozen=True)
class UnionType(Type):
    name = "union"

    members: list[Type]

    def __init__(self, *members: Type) -> None:  # type: ignore
        all_members = []
        for mem in members:
            if isinstance(mem, UnionType):
                for memmem in mem.members:
                    if memmem not in all_members:
                        all_members.append(memmem)
            else:
                if mem not in all_members:
                    all_members.append(mem)
        # # Remove UnknownType if there are other types
        # non_unknown_members = [
        #     mem for mem in all_members if not isinstance(mem, UnknownType)
        # ]
        # if non_unknown_members:
        #     all_members = non_unknown_members
        if not all_members:
            raise errors.WeaveInternalError("Attempted to construct empty union")
        if len(all_members) == 1:
            raise errors.WeaveInternalError(
                "Attempted to construct union with only one member, did you mean to use union()?"
            )
        object.__setattr__(self, "members", all_members)

    # def __repr__(self):
    #     return "UnionType(%s)" % ", ".join(repr(mem) for mem in self.members)

    def __eq__(self, other):  # type: ignore
        if not isinstance(other, UnionType):
            return False
        # Order matters, it affects layout.
        # return self.members == other.members
        return set(self.members) == set(other.members)

    def _hashable(self):  # type: ignore
        return tuple(hash(mem) for mem in sorted(self.members))

    def is_simple_nullable(self):  # type: ignore
        return len(set(self.members)) == 2 and none_type in set(self.members)

    # def instance_to_py(self, obj):
    #     # Figure out which union member this obj is, and delegate to that
    #     # type.
    #     for member_type in self.members:
    #         if member_type.type_of(obj) is not None:
    #             return member_type.instance_to_py(obj)
    #     raise Exception('invalid')
    @classmethod
    def from_dict(cls, d):  # type: ignore
        return merge_many_types(
            [TypeRegistry.type_from_dict(mem) for mem in d["members"]]
        )

    def _to_dict(self):  # type: ignore
        return {"members": [mem.to_dict() for mem in self.members]}

    def __getattr__(self, attr):  # type: ignore
        has_none = False
        results = []
        for mem in self.members:
            if mem == none_type:
                has_none = True
            else:
                results.append(getattr(mem, attr))
        if len(results) == 0:
            raise errors.WeaveTypeError(
                f"Attempt to get attribute {attr} from UnionType with no non-none members"
            )
        first_result = results[0]
        if isinstance(first_result, Type):
            if any((not isinstance(res, Type)) for res in results):
                raise errors.WeaveTypeError(
                    f"Attempt to get attribute {attr} from UnionType with inconsistent types"
                )
            if has_none:
                results.append(none_type)
            return union(*results)
        if isinstance(first_result, dict):
            if any((not isinstance(res, dict)) for res in results):
                raise errors.WeaveTypeError(
                    f"Attempt to get attribute {attr} from UnionType with inconsistent types"
                )
            all_keys = set(k for res in results for k in res.keys())
            if has_none:
                results.append({})
            return {
                k: union(*[res.get(k, NoneType()) for res in results]) for k in all_keys
            }
        raise errors.WeaveTypeError(
            f"Attempt to get attribute {attr} from UnionType resulted in type {type(first_result)}, expected Type or dict"
        )


@dataclasses.dataclass(frozen=True)
class List(Type):
    name = "list"
    instance_classes = [set, list]

    object_type: Type = dataclasses.field(default_factory=Any)

    @classmethod
    def type_of_instance(cls, obj):  # type: ignore
        if not obj:
            return cls(UnknownType())
        list_obj_type = TypeRegistry.type_of(obj[0])
        for item in obj[1:]:
            obj_type = TypeRegistry.type_of(item)
            if obj_type is None:
                raise Exception("can't detect type for object: %s" % item)
            list_obj_type = merge_types(list_obj_type, obj_type)
        return cls(list_obj_type)

    def _assign_type_inner(self, next_type):  # type: ignore
        if isinstance(next_type, List) and next_type.object_type == UnknownType():
            return True
        return super()._assign_type_inner(next_type)

    def save_instance(self, obj, artifact, name):  # type: ignore
        serializer = mappers_python.map_to_python(self, artifact)
        result = serializer.apply(obj)
        with artifact.new_file(f"{name}.list.json") as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(self, artifact, name, extra=None):  # type: ignore
        with artifact.open(f"{name}.list.json") as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        mapped_result = mapper.apply(result)

        # TODO: scan through for ID

        if extra is not None:
            # return object_lookup.resolve_fn(mapped_result, extra[0])
            return mapped_result[int(extra[0])]
        return mapped_result


@dataclasses.dataclass(frozen=True)
class TypedDict(Type):
    name = "typedDict"
    instance_classes = [dict]
    property_types: dict[str, Type] = dataclasses.field(default_factory=dict)

    # See: https://peps.python.org/pep-0655/
    # in Typescript this is like key?: value
    not_required_keys: set[str] = dataclasses.field(default_factory=set)

    def _hashable(self):  # type: ignore
        return tuple(
            (k, hash(v), k in self.not_required_keys)
            for k, v in self.property_types.items()
        )

    def __getitem__(self, key: str) -> Type:  # type: ignore
        return self.property_types[key]

    def _assign_type_inner(self, other_type):  # type: ignore
        if isinstance(other_type, Dict):
            for ptype in self.property_types.values():
                if not ptype.assign_type(other_type.object_type):
                    return False
            return True

        if not isinstance(other_type, TypedDict):
            return False

        for k, ptype in self.property_types.items():
            if k in self.not_required_keys and k not in other_type.property_types:
                continue
            ## In the case where we have a required key, but the key is not required for 
            ## the other type, we need to fail assignability. Example: 
            ## t1 = {"a": int, "b": int}
            ## t2 = {"a": int, "b": int, not_required_keys: ["b"]}
            ## t1.assign_type(t2) should fail
            if k in other_type.not_required_keys and k not in self.not_required_keys:
                return False

            if k not in other_type.property_types or not ptype.assign_type(
                other_type.property_types[k]
            ):
                return False
        
        return True

    def _to_dict(self):  # type: ignore
        property_types = {}
        for key, type_ in self.property_types.items():
            property_types[key] = type_.to_dict()
        result = {"propertyTypes": property_types}
        if self.not_required_keys:
            result["notRequiredKeys"] = list(self.not_required_keys)
        return result

    @classmethod
    def from_dict(cls, d):  # type: ignore
        property_types = {}
        for key, type_ in d["propertyTypes"].items():
            property_types[key] = TypeRegistry.type_from_dict(type_)
        not_required_keys = set()
        if "notRequiredKeys" in d:
            not_required_keys = set(d["notRequiredKeys"])
        return cls(property_types, not_required_keys)

    @classmethod
    def type_of_instance(cls, obj):  # type: ignore
        property_types = {}
        for k, v in obj.items():
            property_types[k] = TypeRegistry.type_of(v)
        return cls(property_types)

    def save_instance(self, obj, artifact, name):  # type: ignore
        serializer = mappers_python.map_to_python(self, artifact)
        result = serializer.apply(obj)
        with artifact.new_file(f"{name}.typedDict.json") as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(self, artifact, name, extra=None):  # type: ignore
        # with artifact.open(f'{name}.type.json') as f:
        #     obj_type = TypeRegistry.type_from_dict(json.load(f))
        with artifact.open(f"{name}.typedDict.json") as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        mapped_result = mapper.apply(result)
        return mapped_result


@dataclasses.dataclass(frozen=True)
class Dict(Type):
    name = "dict"

    key_type: Type = String()
    object_type: Type = Any()

    @property
    def property_types(self):  # type: ignore
        class DictPropertyTypes:
            def values(_self):  # type: ignore
                return [self.object_type]

            def get(_self, _):  # type: ignore
                return self.object_type

            def __getitem__(_self, _):  # type: ignore
                return self.object_type

        return DictPropertyTypes()

    def __post_init__(self):  # type: ignore
        # Note this differs from Python's Dict in that keys are always strings!
        # TODO: consider if we can / should accept key_type. Would make JS side
        # harder since js objects can only have string keys.
        if not String().assign_type(self.key_type):
            raise errors.WeaveTypeError("Dict only supports string keys!")

    def _assign_type_inner(self, other_type):  # type: ignore
        if isinstance(other_type, TypedDict):
            return all(
                self.object_type.assign_type(t)
                for t in other_type.property_types.values()
            )
        return super()._assign_type_inner(other_type)

    @classmethod
    def type_of_instance(cls, obj):  # type: ignore
        value_type = UnknownType()
        for k, v in obj.items():
            if not isinstance(k, str):
                raise errors.WeaveTypeError("Dict only supports string keys!")
            value_type = value_type.assign_type(TypeRegistry.type_of(v))
        return cls(String(), value_type)


@dataclasses.dataclass(frozen=True)
class ObjectType(Type):
    # If True, object is relocatable, meaning it can be saved in one python runtime
    # and loaded in another. (reloctable false means that we need the original
    # object definition to load the object, ie it's a built-in)
    _relocatable = False
    instance_classes = pydantic.BaseModel

    # ObjectType gets its attribute types from actual attributes that
    # attached to subclasses. Which means that ObjectTypes can't have
    # attributes that collide with methods or other attributes of the
    # class itself. We do a bunch of fixups here specifically for the
    # "name" attribute (which would collide with Type.name) since we
    # want objects to be able to have a "name" attribute.
    # NOTE: These fixups should not "leak" out into the rest of the code
    # base. All interactions with types go through methods here, so
    # fixups can be contained.

    def __init__(self, **attr_types: Type):  # type: ignore
        fixed_attr_types = {}
        for k, v in attr_types.items():
            if k == "name":
                fixed_attr_types["_name"] = v
            else:
                fixed_attr_types[k] = v
        self.__dict__["attr_types"] = fixed_attr_types
        for k, v in fixed_attr_types.items():
            self.__dict__[k] = v

    @property
    def type_vars(self):  # type: ignore
        if hasattr(self, "attr_types"):
            tv = self.attr_types
        else:
            tv = super().type_vars
        result = {}
        for k, v in tv.items():
            if k == "_name":
                k = "name"
            result[k] = v
        return result

    def property_types(self) -> dict[str, Type]:  # type: ignore
        return self.type_vars

    @classmethod
    def typeclass_of_class(cls, check_class):  # type: ignore
        from weave_query import weave_pydantic

        if not issubclass(check_class, pydantic.BaseModel):
            return cls

        bases = check_class.__bases__
        base_type = ObjectType
        if len(bases) > 0:
            base0 = bases[0]
            if (
                issubclass(base0, pydantic.BaseModel)
                and base0.__name__ != "BaseModel"
                and base0.__name__ != "Object"
            ):
                base_type = cls.typeclass_of_class(base0)

        type_attrs = {}
        for k, v in weave_pydantic.pydantic_class_to_attr_types(check_class).items():
            if k == "name":
                type_attrs["_name"] = v
            else:
                type_attrs[k] = v

        attr_types = {
            "_relocatable": True,
            "instance_classes": check_class,
            "__annotations__": {k: Type for k in type_attrs.keys()},
        }

        attr_types.update(type_attrs)

        # TODO: need to use type class cache
        new_cls = type(check_class.__name__, (base_type,), attr_types)
        return dataclasses.dataclass(frozen=True)(new_cls)

    @classmethod
    def type_of_instance(cls, obj):  # type: ignore
        if isinstance(obj, pydantic.BaseModel):
            type_class = cls.typeclass_of_class(obj.__class__)
            attr_types = {}
            for k, field in obj.model_fields.items():
                set_k = k
                if set_k == "name":
                    set_k = "_name"
                attr_types[set_k] = TypeRegistry.type_of(getattr(obj, k))
            return type_class(**attr_types)

        variable_prop_types = {}
        for prop_name in cls.type_attrs():
            get_k = prop_name
            if get_k == "_name":
                get_k = "name"
            prop_type = TypeRegistry.type_of(getattr(obj, get_k))
            # print("TYPE_OF", cls, prop_name, prop_type, type(getattr(obj, prop_name)))
            variable_prop_types[prop_name] = prop_type
        return cls(**variable_prop_types)

    def _to_dict(self) -> dict:  # type: ignore
        d = self.class_to_dict()

        if self._relocatable:
            d["_relocatable"] = True
        # TODO: we don't need _is_object, now that we have base_type everywhere.
        # Remove the check for self._base_type.__class__ != ObjectType, and get
        # rid of _is_object (need to update frontend as well).
        d["_is_object"] = True
        for k, prop_type in self.property_types().items():
            d[to_weavejs_typekey(k)] = prop_type.to_dict()
        return d

    def save_instance(self, obj, artifact, name):  # type: ignore
        serializer = mappers_python.map_to_python(self, artifact)

        result = serializer.apply(obj)
        if "_type" in result:
            del result["_type"]
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(self, artifact, name, extra=None):  # type: ignore
        with artifact.open(f"{name}.object.json") as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        return mapper.apply(result)

    def __eq__(self, other) -> bool:  # type: ignore
        return (
            type(self) == type(other)
            and self.property_types() == other.property_types()
        )


def is_serialized_object_type(t: dict) -> bool:  # type: ignore
    if "_base_type" not in t:
        return False
    if t["_base_type"]["type"] == "Object":
        return True
    return is_serialized_object_type(t["_base_type"])


def is_relocatable_object_type(t: typing.Union[str, dict]) -> bool:  # type: ignore
    if not isinstance(t, dict):
        return False
    if not t.get("_relocatable"):
        return False
    if t.get("_relocatable") and t.get("_is_object"):
        # relocatable base object case
        return True
    return is_serialized_object_type(t)


# We need to ensure we only create new classes for each new unique
# type seen. Otherwise we get a class explosion, and for one thing, type_of
# gets really slow.
DESERIALIZED_OBJECT_TYPE_CLASSES: dict[str, type[ObjectType]] = {}


def validate_kwarg_name(name: str) -> bool:  # type: ignore
    """Return True if name is a valid python kwarg name"""
    if name in keyword.kwlist:
        raise ValueError(
            f"{name} is a Python keyword and cannot be used as a kwarg name"
        )
    if not name.isidentifier():
        raise ValueError(
            f"{name} is not a valid Python identifier and cannot be used as a kwarg name"
        )
    return True


def deserialize_relocatable_object_type(t: dict) -> ObjectType:  # type: ignore
    key = json.dumps(t)
    if key in DESERIALIZED_OBJECT_TYPE_CLASSES:
        return DESERIALIZED_OBJECT_TYPE_CLASSES[key]()
    object_class_name = t["type"]
    type_class_name = object_class_name + "Type"

    type_attr_types = {}
    for k, v in t.items():
        if k == "name":
            type_attr_types["_name"] = TypeRegistry.type_from_dict(v)
        elif k != "type" and not k.startswith("_"):
            type_attr_types[k] = TypeRegistry.type_from_dict(v)
    import textwrap

    object_constructor_arg_names = [
        k if k != "_name" else "name"
        for k, t in type_attr_types.items()
        if t.name != "OpDef"
    ]
    # Sanitize
    for k in object_constructor_arg_names:
        if not validate_kwarg_name(k):
            raise ValueError(f"Invalid kwarg name: {k}")

    object_init_code = textwrap.dedent(
        f"""
        def loaded_object_init(self, {', '.join(object_constructor_arg_names)}):
            for k, v in locals().items():
                if k != 'self':
                    setattr(self, k, v)
        """
    )
    exec(object_init_code)

    object_getattribute = object_type_ref_util.make_object_getattribute(
        list(type_attr_types.keys())
    )
    object_lookup_path = object_type_ref_util.make_object_lookup_path()

    new_object_class = type(
        object_class_name,
        (),
        {
            "__init__": locals()["loaded_object_init"],
            "__getattribute__": object_getattribute,
            "_lookup_path": object_lookup_path,
            "_weave_obj_fields": object_constructor_arg_names,
        },
    )

    all_attr_types: dict[str, typing.Union[Type, type[Type]]] = {
        **type_attr_types,
        "instance_classes": new_object_class,
    }
    if "_base_type" in t:
        all_attr_types["_base_type"] = deserialize_relocatable_object_type(
            t["_base_type"]
        )
    new_type_class = type(type_class_name, (ObjectType,), all_attr_types)
    setattr(new_type_class, "_relocatable", True)
    setattr(new_type_class, "__annotations__", {})
    for k, v in type_attr_types.items():
        setattr(new_type_class, k, v)
        new_type_class.__dict__["__annotations__"][k] = Type
    new_type_dataclass: type[ObjectType] = dataclasses.dataclass(frozen=True)(
        new_type_class
    )
    DESERIALIZED_OBJECT_TYPE_CLASSES[key] = new_type_dataclass
    return new_type_dataclass()


@dataclasses.dataclass(frozen=True)
class TypeType(ObjectType):
    name = "type"

    instance_classes = [Type]
    attr_types: dict[str, Type] = dataclasses.field(default_factory=dict)

    def property_types(self) -> dict[str, Type]:  # type: ignore
        return self.attr_types

    def _hashable(self):  # type: ignore
        return tuple((k, hash(v)) for k, v in self.property_types().items())

    @classmethod
    def type_of_instance(cls, obj):  # type: ignore
        from weave_query import infer_types

        attr_types = {}
        for field in dataclasses.fields(obj):
            attr_types[field.name] = infer_types.python_type_to_type(field.type)
        return cls(attr_types)

    def _to_dict(self):  # type: ignore
        # we ensure we match the layout of ObjectType, so WeaveJS
        # can handle it the same way.
        d = {"_is_object": True}
        for k, t in self.attr_types.items():
            d[k] = t.to_dict()
        return d

    @classmethod
    def from_dict(cls, d):  # type: ignore
        # weavejs fix: weavejs uses the plain string 'type' for now.
        if d == "type":
            return cls()
        res = {}
        for k, t in d.items():
            if k != "type" and not k.startswith("_"):
                res[k] = TypeRegistry.type_from_dict(t)
        return cls(res)


@dataclasses.dataclass(frozen=True)
class Function(Type):
    name = "function"

    instance_classes: typing.ClassVar[typing.List[type]] = []

    input_types: dict[str, Type] = dataclasses.field(default_factory=dict)
    output_type: Type = dataclasses.field(default_factory=lambda: UnknownType())

    def _hashable(self):  # type: ignore
        return (
            tuple((k, hash(v)) for k, v in self.input_types.items()),
            hash(self.output_type),
        )

    def _is_assignable_to(self, other_type) -> typing.Optional[bool]:  # type: ignore
        if other_type.__class__ != Function:
            return other_type.assign_type(self.output_type)
        return None

    def assign_type(self, next_type: Type) -> bool:  # type: ignore
        if not self.input_types and not isinstance(next_type, Function):
            # Allow assignment of T to () -> T.
            # Compile handles this in the compile_quote pass.
            return self.output_type.assign_type(next_type)
        return super().assign_type(next_type)

    @classmethod
    def type_of_instance(cls, obj):  # type: ignore
        if isinstance(obj.type, Function):
            # Its already a Function type, so just return it.
            # TODO: I'm not sure if this is right, this makes FunctionType
            # a top of sorts...
            return obj.type
        # TODO: get input variable types!
        return cls({}, obj.type)

    @classmethod
    def from_dict(cls, json):  # type: ignore
        input_types = {
            pname: TypeRegistry.type_from_dict(ptype)
            for (pname, ptype) in json["inputTypes"].items()
        }
        return cls(input_types, TypeRegistry.type_from_dict(json["outputType"]))

    def _to_dict(self):  # type: ignore
        input_types = {k: v.to_dict() for (k, v) in self.input_types.items()}
        return {"inputTypes": input_types, "outputType": self.output_type.to_dict()}

    def save_instance(self, obj, artifact, name):  # type: ignore
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(obj.to_json(), f)

    def load_instance(self, artifact, name, extra=None):  # type: ignore
        with artifact.open(f"{name}.object.json") as f:
            # TODO: no circular imports!
            from weave_query import graph

            return graph.Node.node_from_json(json.load(f))


@dataclasses.dataclass(frozen=True)
class RefType(Type):
    object_type: Type = Any()

    @classmethod
    def type_of_instance(cls, obj):  # type: ignore
        return cls(obj.type)

    def _is_assignable_to(self, other_type) -> typing.Optional[bool]:  # type: ignore
        # Use issubclass, we have RunLocalType defined as a subclass of RunType
        if not issubclass(other_type.__class__, RefType):
            if self.object_type == NoneType():
                # If output is None, we don't want to be assignable to basically
                # all ops (since ops are nullable)
                return None
            return other_type.assign_type(self.object_type)
        return None

    def save_instance(self, obj, artifact, name):  # type: ignore
        from weave_query import ref_base

        obj_ref = ref_base.get_ref(obj)
        if obj_ref is None:
            raise errors.WeaveSerializeError(
                "save_instance invalid when ref is None for type: %s" % self
            )
        return obj_ref

    # TODO: Address this comment. I'm sure this introduced the same type
    #     blowup as before again. Slows everything down. But in this PR
    #     I've put object_type back into RefType for now.
    # RefType intentionally does not include the type of the object it
    # points to. Doing so naively results in a type explosion. We may
    # want to include it in the future, but we'll need to shrink it, for
    # example by disallowing unions (replacing with them with unknown or a
    # type variable)
    # def __repr__(self):
    #     return "<%s>" % self.__class__.name


@dataclasses.dataclass(frozen=True)
class FilesystemArtifactRefType(RefType):
    pass


@dataclasses.dataclass(frozen=True)
class LocalArtifactRefType(FilesystemArtifactRefType):
    pass


@dataclasses.dataclass(frozen=True)
class WandbArtifactRefType(FilesystemArtifactRefType):
    def load_instance(self, artifact, name, extra=None):  # type: ignore
        from weave_query import artifact_wandb

        return artifact_wandb.WandbArtifactRef(artifact, name)


class WBTable(Type):
    name = "wbtable"


def is_json_compatible(type_):  # type: ignore
    if isinstance(type_, List):
        return is_json_compatible(type_.object_type)
    elif isinstance(type_, Dict):
        return is_json_compatible(type_.object_type)
    elif isinstance(type_, TypedDict):
        return all(t for t in type_.property_types.values())
    else:
        return isinstance(type_, BasicType)


def optional(type_: Type) -> Type:
    # TODO: This is not a complete implementation, it doesn't handle
    # Const for example. Although why would we have a Const optional,
    # that doesn't make sense (if its a const, we know the concrete type,
    # its not a union).
    return union(none_type, type_)


def is_optional(type_: Type) -> bool:
    TaggedValueType = type_name_to_type("tagged")

    if isinstance(type_, Const):
        return is_optional(type_.val_type)

    if isinstance(type_, TaggedValueType):
        return is_optional(type_.value)

    return isinstance(type_, UnionType) and any(
        (none_type.assign_type(m)) for m in type_.members
    )


def simple_non_none(type_: Type) -> Type:
    if not isinstance(type_, UnionType):
        return type_
    new_members = [m for m in type_.members if m != NoneType()]
    return union(*new_members)


def non_none(type_: Type) -> Type:
    TaggedValueType = type_name_to_type("tagged")

    if type_ == none_type:
        return Invalid()

    if isinstance(type_, Const):
        val_type = non_none(type_.val_type)
        if val_type == type_.val_type:
            return type_
        return val_type

    if isinstance(type_, TaggedValueType):
        return TaggedValueType(type_.tag, non_none(type_.value))

    if is_optional(type_):
        type_ = typing.cast(UnionType, type_)
        new_members = [
            non_none(m) for m in type_.members if not none_type.assign_type(m)
        ]
        # Can happen if there are Nones and Tagged Nones
        if len(new_members) == 0:
            return Invalid()
        elif len(new_members) == 1:
            return new_members[0]
        else:
            return union(*new_members)
    return type_


def string_enum_type(*vals):  # type: ignore
    return UnionType(*[Const(String(), v) for v in vals])


def literal(val: typing.Any) -> Const:  # type: ignore
    return Const(TypeRegistry.type_of(val), val)


RUN_STATE_TYPE = string_enum_type("pending", "running", "finished", "failed")  # type: ignore[no-untyped-call]


# TODO: get rid of all the underscores. This is another
#    conflict with making ops automatically lazy
@dataclasses.dataclass(frozen=True)
class RunType(ObjectType):
    id: Type = String()
    inputs: Type = TypedDict({})
    history: Type = List(TypedDict({}))
    output: Type = Any()

    def property_types(self):  # type: ignore
        return {
            "id": String(),
            "op_name": String(),
            "state": RUN_STATE_TYPE,
            "prints": List(String()),
            "inputs": self.inputs,
            "history": self.history,
            "output": self.output,
        }

    def _is_assignable_to(self, other_type) -> typing.Optional[bool]:  # type: ignore
        # Use issubclass, we have RunLocalType defined as a subclass of RunType
        if not issubclass(other_type.__class__, RunType):
            if self.output == NoneType():
                # If output is None, we don't want to be assignable to basically
                # all ops (since ops are nullable)
                return None
            return other_type.assign_type(self.output)
        return None


def merge_many_types(types: list[Type]) -> Type:
    if len(types) == 0:
        return Invalid()
    if len(types) == 1:
        return types[0]
    t = types[0]
    for t2 in types[1:]:
        t = merge_types(t, t2)
    return t


def merge_types(a: Type, b: Type) -> Type:
    """Compute the next list object type.

    list[a].append(b) -> merge_types(a, b)

    This is used at run-time, to figure out the type of existing objects!
    So we can do things like drop UnknownType (UnknownType doesn't make
    sense at run time)

    Note: we don't guarantee that the resulting type can be assigned to
    by either of the inputs! Consider TypedDict[{"a": int}].merge_types(TypedDict[{"b": int}])
    The result is TypedDict[{"a": optional[int], "b": optional[int]}],
    but neither of the inputs can be assigned to it.

    Our decisions about how to merge types here are made to reduce overall
    type size for lists.

    This implementation must match list.concat implementations (which is the only
    way to extend a list in Weave). Ie list.concat(list[a], [b]) -> list[merge_types(a, b)]
    """
    from weave_query.language_features.tagging import tagged_value_type

    if a == b:
        return a
    if isinstance(a, Number) and isinstance(b, Number):
        if a.__class__ == Number or b.__class__ == Number:
            return Number()
        if a.__class__ == Float or b.__class__ == Float:
            return Float()
        return Int()
    if isinstance(a, tagged_value_type.TaggedValueType) and isinstance(
        b, tagged_value_type.TaggedValueType
    ):
        merged_tag_type: TypedDict = typing.cast(TypedDict, merge_types(a.tag, b.tag))
        merged_value_type: Type = merge_types(a.value, b.value)
        return tagged_value_type.TaggedValueType(merged_tag_type, merged_value_type)
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
            next_prop_types[key] = merge_types(self_prop_type, other_prop_type)
        return TypedDict(next_prop_types)
    if isinstance(a, ObjectType) and isinstance(b, ObjectType):
        if a.name == b.name and not set(a.type_attrs()).difference(b.type_attrs()):  # type: ignore[no-untyped-call]
            next_type_attrs = {}
            for key in a.type_attrs():  # type: ignore[no-untyped-call]
                next_type_attrs[key] = merge_types(getattr(a, key), getattr(b, key))
            return type(a)(**next_type_attrs)

    if isinstance(a, List) and isinstance(b, List):
        return List(merge_types(a.object_type, b.object_type))

    if isinstance(a, RefType) and isinstance(b, RefType) and a.__class__ == b.__class__:
        return a.__class__(merge_types(a.object_type, b.object_type))

    if isinstance(a, UnknownType):
        return b
    if isinstance(b, UnknownType):
        return a

    if isinstance(a, UnionType) or isinstance(b, UnionType):
        new_union = UnionType(a, b)
        final_members = [new_union.members[0]]
        for mem in new_union.members[1:]:
            for i, final_mem in enumerate(final_members):
                merged_m = merge_types(final_mem, mem)
                if not isinstance(merged_m, UnionType):
                    final_members[i] = merged_m
                    break
            else:
                final_members.append(mem)

        # for i in range(len(new_union.members)):
        #     for j in range(i + 1, len(new_union.members)):
        #         merged_m = merge_types(new_union.members[i], new_union.members[j])
        #         if not isinstance(merged_m, UnionType):
        #             final_members.append(merged_m)
        #         else:
        #             final_members.append(new_union.members[i])
        return union(*final_members)
    return union(a, b)


def types_are_mergeable(a: Type, b: Type) -> bool:
    """True if merge_types actually merges a and b.

    This is used to maintain the invariant that types should not be mergeable
    within a union inside an ArrowWeaveList.
    """
    return not isinstance(split_none(merge_types(a, b))[1], UnionType)


def unknown_coalesce(in_type: Type) -> Type:
    """
    Recursively removes unknowns from a type. Whenever a union is encountered,
    we do 2 operations:
    1) reduce the union members to only non-unknowns
    2) for each container-type member, attempt to remove any unknowns that are
        known by a peer member.

    For example:

    Union<
        Unknown,
        List<Union<Unknown, Int>>,
        TypedDict<{'a': Unknown}>,
        TypedDict<{'a': Int}>,
    >

    would reduce to

    Union<
        List<Int>,
        TypedDict<{'a': Int}>,
    >

    This is particularly useful when a nested field in an AWL is empty - the
    type will be Unknown. However, when merging for concatenation, we want to
    remove such unknowns since we know the type from a another list.
    """
    # In this function, there are 3 cases:
    # 1) in_type is a union type - in this case we delegate to _unknown_coalesce_on_union
    # 2) Each of the container types calls this function recursively
    # 3) the base case just returns the type
    TaggedValueType = type_name_to_type("tagged")
    if isinstance(in_type, UnionType):
        return _unknown_coalesce_on_union(in_type)
    elif isinstance(in_type, UnknownType):
        return UnknownType()
    elif isinstance(in_type, List):
        return List(unknown_coalesce(in_type.object_type))
    elif isinstance(in_type, Dict):
        return Dict(in_type.key_type, unknown_coalesce(in_type.object_type))
    elif isinstance(in_type, TypedDict):
        return TypedDict(
            {
                key: unknown_coalesce(value_type)
                for key, value_type in in_type.property_types.items()
            }
        )
    elif isinstance(in_type, TaggedValueType):
        return TaggedValueType(
            unknown_coalesce(in_type.tag),  # type: ignore
            unknown_coalesce(in_type.value),
        )
    elif isinstance(in_type, Const):
        return Const(unknown_coalesce(in_type.val_type), in_type.value)
    elif isinstance(in_type, ObjectType):
        # TODO: This is hard due to image type being non-standard.
        pass
    return in_type


def _filter_unknowns(types: list[Type]) -> list[Type]:
    return [t for t in types if not isinstance(t, UnknownType)]


def _unknown_coalesce_on_union(u_type: UnionType) -> Type:
    # This helper function will remove all the unknowns from a a union's members,
    # then apply the `unknown_coalesce` function to each known member. This ensures
    # that each member is processed before comparing to it's peers.
    known_members = [
        unknown_coalesce(member) for member in _filter_unknowns(u_type.members)
    ]

    if len(known_members) == 0:
        return UnknownType()

    final_types: list[Type] = []
    for ndx in range(len(known_members)):
        final_types.append(
            _merge_unknowns_of_type_with_types(
                known_members[ndx], known_members[:ndx] + known_members[ndx + 1 :]
            )
        )

    return union(*final_types)


def _merge_unknowns_of_type_with_types(of_type: Type, with_types: list[Type]):  # type: ignore
    # At this stage, we have a starting type and a list of peer candidate types.
    # These types have already been coalesced individually. This step is similar to
    # the outer `unknown_coalesce` function, except that rather than operating on the
    # single incoming type, we must select the correct type from the list of peers.
    TaggedValueType = type_name_to_type("tagged")

    # First, we filter out any unknowns from the list of peers.
    with_types = _filter_unknowns(with_types)
    if len(with_types) == 0:
        return of_type

    # If the current type itself is a union, then we need to recurse into it
    if isinstance(of_type, UnionType):
        return union(
            *[
                _merge_unknowns_of_type_with_types(member, with_types)
                for member in of_type.members
            ]
        )

    # if the current type is unknown, then we just return the next peer type.
    elif isinstance(of_type, UnknownType):
        return with_types[0]

    # Next, we filter down to peer types that have the same type class, and recurse
    # into each container type.
    with_types = [
        member for member in with_types if member.__class__ == of_type.__class__
    ]
    if isinstance(of_type, List):
        return List(
            _merge_unknowns_of_type_with_types(
                of_type.object_type,
                [t.object_type for t in with_types],  # type: ignore
            )
        )
    elif isinstance(of_type, Dict):
        return Dict(
            of_type.key_type,
            _merge_unknowns_of_type_with_types(
                of_type.value_type,  # type: ignore
                [t.value_type for t in with_types],  # type: ignore
            ),
        )
    elif isinstance(of_type, TypedDict):
        return TypedDict(
            {
                key: _merge_unknowns_of_type_with_types(
                    value_type,
                    [t.property_types.get(key, NoneType()) for t in with_types],  # type: ignore
                )
                for key, value_type in of_type.property_types.items()
            }
        )
    elif isinstance(of_type, TaggedValueType):
        return TaggedValueType(
            _merge_unknowns_of_type_with_types(
                of_type.tag,
                [t.tag for t in with_types],  # type: ignore
            ),  # type: ignore
            _merge_unknowns_of_type_with_types(
                of_type.value,
                [t.value for t in with_types],  # type: ignore
            ),
        )
    elif isinstance(of_type, Const):
        return Const(
            _merge_unknowns_of_type_with_types(
                of_type.val_type,
                [t.val_type for t in with_types],  # type: ignore
            ),
            of_type.value,
        )
    elif isinstance(of_type, ObjectType):
        # TODO: This is hard due to image type being non-standard.
        pass

    # Finally, return the type.
    return of_type


def union(*members: Type) -> Type:
    if not members:
        return UnknownType()
    final_members = []
    for member in members:
        if isinstance(member, UnionType):
            for sub_member in member.members:
                if sub_member not in final_members:
                    final_members.append(sub_member)
        elif member not in final_members:
            final_members.append(member)
    # Unknown "takes over" in a union.
    if any(isinstance(m, UnknownType) for m in final_members):
        return UnknownType()
    if len(final_members) == 1:
        return final_members[0]
    return UnionType(*final_members)


def unwrap_type(t: Type) -> Type:
    """Removes any transparent types from the type."""
    if isinstance(t, RefType):
        return t.object_type
    # TODO: TaggedValue
    return t


def simple_type(t: Type) -> Type:
    """Type without nullable and transparent types"""
    t = unwrap_type(t)
    _, non_none_t = split_none(t)
    return non_none_t


def is_list_like(t: Type) -> bool:
    return is_type_like(t, List())


def is_type_like(t: Type, of_type: Type) -> bool:
    return of_type.assign_type(non_none(t))


def is_custom_type(t: Type) -> bool:
    return not (
        isinstance(t, BasicType)
        or isinstance(t, ObjectType)
        or isinstance(t, TypedDict)
        or isinstance(t, List)
        or isinstance(t, UnionType)
        or isinstance(t, Timestamp)
        or t.name == "tagged"
    )


def type_is_variable(t: Type) -> bool:
    # not concrete
    if isinstance(t, Any):
        # Any is currently the equivalent Weave Type for any Python
        # TypeVar
        return True
    elif isinstance(t, UnionType):
        return True
    elif isinstance(t, ObjectType):
        return True
    elif isinstance(t, Dict):
        # Tim: This was `true` before weaveflow.
        return type_is_variable(t.object_type)
    elif isinstance(t, TypedDict):
        # Should we just make type_vars for TypedDict be its property types?
        # That would simplify a lot.
        return any(type_is_variable(sub_t) for sub_t in t.property_types.values())
    elif isinstance(t, Const):
        return type_is_variable(t.val_type)
    else:
        return any(type_is_variable(sub_t) for sub_t in t.type_vars.values())


NumberBinType = TypedDict({"start": Float(), "stop": Float()})
TimestampBinType = TypedDict({"start": Timestamp(), "stop": Timestamp()})


def map_leaf_types(t: Type, fn: typing.Callable[[Type], typing.Optional[Type]]) -> Type:
    """
    This function will recursively apply `fn` to all leaf types in `t`. A leaf type is
    a basic type, object type, or const. If `fn` returns None, then the original type
    will be used.
    """

    def null_safe_fn(t: Type) -> Type:
        fn_res = fn(t)
        return t if fn_res is None else fn_res

    return _map_leaf_types_null_safe(t, null_safe_fn)


def _map_leaf_types_null_safe(t: Type, fn: typing.Callable[[Type], Type]) -> Type:
    TaggedValueType = type_name_to_type("tagged")
    if isinstance(t, List):
        return List(_map_leaf_types_null_safe(t.object_type, fn))
    elif isinstance(t, TypedDict):
        return TypedDict(
            {k: _map_leaf_types_null_safe(v, fn) for k, v in t.property_types.items()}
        )
    elif isinstance(t, Dict):
        return Dict(t.key_type, _map_leaf_types_null_safe(t.object_type, fn))
    elif isinstance(t, ObjectType):
        pass
    elif isinstance(t, UnionType):
        return union(*[_map_leaf_types_null_safe(t, fn) for t in t.members])
    elif isinstance(t, Const):
        pass
    elif isinstance(t, TaggedValueType):
        return TaggedValueType(
            _map_leaf_types_null_safe(t.tag, fn),  # type: ignore
            _map_leaf_types_null_safe(t.value, fn),
        )
    return fn(t)


# parse_const_type and const_type_to_json are a new concept used only
# by the weave0 ImageArtifactRefFileType. That stores for example
# boxScores as {box1: [2, 3, 5], box2: [0]} where the lists are
# class ids. This is a way to convert those literal representations
# to types, making assignability work. The above becomes
# TypedDict<box1: List<Union<Const<2>, Const<3>, Const<5>>>, box2: List<Const<0>>>.
# We can update the names and standardize this more if we find it useful
# outside of weave0 support.


def parse_constliteral_type(val: typing.Any) -> Type:
    if isinstance(val, Type):
        return val
    elif isinstance(val, dict):
        return TypedDict({k: parse_constliteral_type(v) for k, v in val.items()})
    elif isinstance(val, list):
        return List(union(*[parse_constliteral_type(v) for v in val]))
    else:
        return Const(TypeRegistry.type_of(val), val)


def constliteral_type_to_json(t: Type) -> typing.Any:
    t = simple_non_none(t)
    if isinstance(t, Const):
        return t.val
    elif isinstance(t, TypedDict):
        return {k: constliteral_type_to_json(v) for k, v in t.property_types.items()}
    elif isinstance(t, Dict):
        return {}
    elif isinstance(t, List):
        object_type = t.object_type
        members = [object_type]
        if isinstance(object_type, UnionType):
            members = object_type.members
        members = [m for m in members if isinstance(m, Const)]
        return [constliteral_type_to_json(mem) for mem in members]
    raise ValueError(f"Cannot convert {t} to a JSON value")


def split_none(t: Type) -> tuple[bool, Type]:
    """Returns (is_optional, non_none_type)"""
    if t == NoneType():
        return True, UnknownType()
    if not isinstance(t, UnionType):
        return False, t
    non_none_members = [m for m in t.members if not isinstance(m, NoneType)]
    if len(non_none_members) < len(t.members):
        return True, union(*non_none_members)
    return False, t


def type_of(obj: typing.Any) -> Type:
    return TypeRegistry.type_of(obj)


# A modified type_of that returns RefType<O> for any object that
# has a ref. This is used when serializing, so that we save refs
# instead of copying.
def type_of_with_refs(obj: typing.Any) -> Type:
    token = _reffed_type_is_ref.set(True)
    try:
        return TypeRegistry.type_of(obj)
    finally:
        _reffed_type_is_ref.reset(token)


def type_of_without_refs(obj: typing.Any) -> Type:
    token = _reffed_type_is_ref.set(False)
    try:
        return TypeRegistry.type_of(obj)
    finally:
        _reffed_type_is_ref.reset(token)
