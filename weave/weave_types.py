import dataclasses
import datetime
import typing
import inspect
import functools
import json
from collections.abc import Iterable


from . import box
from . import errors
from . import mappers_python
from . import timestamp as weave_timestamp


if typing.TYPE_CHECKING:
    from .artifact_fs import FilesystemArtifact
    from . import artifact_base


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


@functools.cache
def type_name_to_type_map():
    res = {}
    type_classes = get_type_classes()
    for type_class in type_classes:
        name = type_class.name
        if name is not None:
            res[name] = type_class
    return res


@functools.cache
def type_name_to_type(type_name):
    mapping = type_name_to_type_map()
    return mapping.get(js_to_py_typename(type_name))


class TypeRegistry:
    @staticmethod
    def has_type(obj):
        return bool(instance_class_to_potential_type(type(obj)))

    @staticmethod
    def type_class_of(obj):
        type_classes = instance_class_to_potential_type(type(obj))
        if not type_classes:
            # return UnknownType()
            raise errors.WeaveTypeError("no Type for obj: %s" % obj)
        return type_classes[-1]

    @staticmethod
    def type_of(obj: typing.Any) -> "Type":
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
        # return UnknownType()
        raise errors.WeaveTypeError("no Type for obj: (%s) %s" % (type(obj), obj))

    @staticmethod
    def type_from_dict(d: typing.Union[str, dict]) -> "Type":
        # The javascript code sends simple types as just strings
        # instead of {'type': 'string'} for example
        type_name = d["type"] if isinstance(d, dict) else d
        type_ = type_name_to_type(type_name)
        if type_ is None:
            raise errors.WeaveSerializeError("Can't deserialize type from: %s" % d)
        return type_.from_dict(d)


def _clear_global_type_class_cache():
    instance_class_to_potential_type.cache_clear()
    type_name_to_type_map.cache_clear()
    type_name_to_type.cache_clear()


def _cached_hash(self):
    try:
        return self.__dict__["_hash"]
    except KeyError:
        hashed = hash((self.__class__, self._hashable()))
        self.__dict__["_hash"] = hashed
        return hashed


class classproperty(object):
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


# Addapted from https://stackoverflow.com/questions/18126552/how-to-run-code-when-a-class-is-subclassed
class _TypeSubclassWatcher(type):
    def __init__(cls, name, bases, clsdict):
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
    instance_classes: typing.ClassVar[
        typing.Union[type, typing.List[type], None]
    ] = None

    _type_attrs = None
    _hash = None

    def _hashable(self):
        return tuple((k, hash(t)) for k, t in self.type_vars_tuple)

    def __lt__(self, other):
        return hash(self) < hash(other)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"

    def __name__(self) -> str:
        return self.__repr__()

    def simple_str(self) -> str:
        return str(self)

    @classmethod
    def _instance_classes(cls):
        """Helper to get instance_classes as iterable."""
        if cls.instance_classes is None:
            return ()
        if isinstance(cls.instance_classes, Iterable):
            return cls.instance_classes
        return (cls.instance_classes,)

    @classmethod
    def type_attrs(cls):
        type_attrs = []
        for field in dataclasses.fields(cls):
            if (inspect.isclass(field.type) and issubclass(field.type, Type)) or (
                field.type.__origin__ == typing.Union
                and any(issubclass(a, Type) for a in field.type.__args__)
            ):
                type_attrs.append(field.name)
        return type_attrs

    @property
    def type_vars_tuple(self):
        type_vars = []
        for field in self.type_attrs():
            type_vars.append((field, getattr(self, field)))
        return tuple(type_vars)

    @property
    def type_vars(self) -> dict[str, "Type"]:
        return dict(self.type_vars_tuple)

    @classmethod
    def is_instance(cls, obj):
        for ic in cls._instance_classes():
            if isinstance(obj, ic):
                return ic
        return None

    @classmethod
    def type_of(cls, obj) -> typing.Optional["Type"]:
        if not cls.is_instance(obj):
            return None
        return cls.type_of_instance(obj)

    @classmethod
    def type_of_instance(cls, obj):
        # Default implementation for Types that take no arguments.
        return cls()

    @classproperty
    def name(cls):
        if cls == Type:
            return "type"
        return cls.__name__.removesuffix("Type")

    @property  # type: ignore
    def instance_class(self):
        return self._instance_classes()[-1]

    def assign_type(self, next_type: "Type") -> bool:
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

    def _is_assignable_to(self, other_type) -> typing.Optional[bool]:
        return None

    def _assign_type_inner(self, next_type: "Type") -> bool:
        # First check that we match next_type class or one of
        # its bases.
        next_type_class = next_type.__class__
        while True:
            if self.__class__ == next_type_class:
                break
            elif next_type_class._base_type is None:
                # nothing left in base chain, no match
                return False
            next_type_class = next_type_class._base_type

        # Now check that all type vars match
        for prop_name in self.type_vars:
            if not hasattr(next_type, prop_name):
                return False
            if not getattr(self, prop_name).assign_type(getattr(next_type, prop_name)):
                return False
        return True

    @classmethod
    def class_to_dict(cls) -> dict[str, typing.Any]:
        d = {"type": cls.name}
        if cls._base_type is not None:
            d["_base_type"] = cls._base_type.class_to_dict()
        return d

    def to_dict(self) -> typing.Union[dict, str]:
        d = {"type": self.name}
        d.update(self._to_dict())
        return d

    def _to_dict(self) -> dict:
        fields = dataclasses.fields(self.__class__)
        type_props = {}
        if self._base_type is not None:
            type_props["_base_type"] = {"type": self._base_type.name}
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
            field_name = to_weavejs_typekey(field.name)
            if field_name in d:
                type_attrs[field.name] = TypeRegistry.type_from_dict(d[field_name])
        return cls(**type_attrs)

    def save_instance(
        self, obj, artifact, name
    ) -> typing.Optional[typing.Union[list[str], "artifact_base.ArtifactRef"]]:
        d = None
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
        self,
        artifact: "FilesystemArtifact",
        name: str,
        extra: typing.Optional[list[str]] = None,
    ) -> typing.Any:
        with artifact.open(f"{name}.object.json") as f:
            d = json.load(f)
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
    def _assign_type_inner(self, next_type):
        return True


# TODO: Tim has this as ConstType(None), but how is that serialized?


class NoneType(BasicType):
    name = "none"
    instance_classes = [type(None), box.BoxedNone]

    # If we're using NoneType in a place where we expect a list, the object_type
    # of that list is also NoneType, due to nullability.
    @property
    def object_type(self):
        return NoneType()

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

    def _assign_type_inner(self, next_type):
        return True


@dataclasses.dataclass(frozen=True)
class Const(Type):
    name = "const"
    val_type: Type
    val: typing.Any

    def __post_init__(self):
        if isinstance(self.val_type, UnionType):
            # Const Unions are invalid. If something is Const, that means we know what its value
            # is, which means it is definitely not a Union. Replace val_type with the actual type
            # here.
            self.__dict__["val_type"] = TypeRegistry.type_of(self.val)

    def _hashable(self):
        val_id = id(self.val)
        try:
            val_id = hash(self.val)
        except TypeError:
            pass
        return (hash(self.val_type), val_id)

    def __getattr__(self, attr):
        return getattr(self.val_type, attr)

    @classmethod
    def type_of_instance(cls, obj):
        return cls(TypeRegistry.type_of(obj.val), obj.val)

    def _is_assignable_to(self, other_type) -> typing.Optional[bool]:
        if other_type.__class__ != Const:
            return other_type.assign_type(self.val_type)
        return None

    def _assign_type_inner(self, next_type):
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
    def from_dict(cls, d):
        w_type = TypeRegistry.type_from_dict(d["valType"])
        val = d["val"]
        # try:
        #     val = w_type.instance_from_dict(val)
        # except NotImplementedError:
        #     pass
        return cls(w_type, val)

    def _to_dict(self):
        val = self.val
        # try:
        #     val = self.val_type.instance_to_dict(val)
        # except NotImplementedError:
        #     pass
        return {"valType": self.val_type.to_dict(), "val": val}

    def __repr__(self):
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

    def _assign_type_inner(self, other_type: Type):
        # Float if either side is a number
        return isinstance(other_type, Number)


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
        return isinstance(other_type, Number) and not isinstance(other_type, Float)


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


class LegacyDate(Type):
    # TODO: For historic reasons we had "date" and "timestamp" types.  Now we only
    # use "timestamp" but we need to keep this around for backwards compatibility.
    name = "date"

    def save_instance(self, obj, artifact, name):
        if artifact is None:
            raise errors.WeaveSerializeError(
                "save_instance invalid when artifact is None for type: %s" % self
            )
        with artifact.new_file(f"{name}.object.json") as f:
            v = weave_timestamp.python_datetime_to_ms(obj)
            json.dump(v, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.object.json") as f:
            v = json.load(f)
            return weave_timestamp.ms_to_python_datetime(v)


class TimeDelta(Type):
    name = "timedelta"
    instance_classes = datetime.timedelta

    def save_instance(self, obj: datetime.timedelta, artifact, name):
        if artifact is None:
            raise errors.WeaveSerializeError(
                "save_instance invalid when artifact is None for type: %s" % self
            )
        with artifact.new_file(f"{name}.object.json") as f:
            # Uses internal python representation of timedelta for serialization
            v = [obj.days, obj.seconds, obj.microseconds]
            json.dump(v, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.object.json") as f:
            [days, seconds, microseconds] = json.load(f)
            return datetime.timedelta(days, seconds, microseconds)


class Timestamp(Type):
    name = "timestamp"
    instance_classes = datetime.datetime

    def from_isostring(self, iso: str) -> datetime.datetime:
        # NOTE: This assumes ISO 8601 format from GQL endpoints, it does NOT
        # support RFC 3339 strings with a "Z" at the end before python 3.11
        tz_naive = datetime.datetime.fromisoformat(iso)
        return tz_naive.replace(tzinfo=datetime.timezone.utc)

    def save_instance(self, obj, artifact, name):
        if artifact is None:
            raise errors.WeaveSerializeError(
                "save_instance invalid when artifact is None for type: %s" % self
            )
        with artifact.new_file(f"{name}.object.json") as f:
            v = weave_timestamp.python_datetime_to_ms(obj)
            json.dump(v, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.object.json") as f:
            v = json.load(f)
            return weave_timestamp.ms_to_python_datetime(v)


@dataclasses.dataclass(frozen=True)
class UnionType(Type):
    name = "union"

    members: list[Type]

    def __init__(self, *members: Type) -> None:
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

    def __eq__(self, other):
        if not isinstance(other, UnionType):
            return False
        # Order matters, it affects layout.
        # return self.members == other.members
        return set(self.members) == set(other.members)

    def _hashable(self):
        return tuple(hash(mem) for mem in sorted(self.members))

    def is_simple_nullable(self):
        return len(set(self.members)) == 2 and none_type in set(self.members)

    # def instance_to_py(self, obj):
    #     # Figure out which union member this obj is, and delegate to that
    #     # type.
    #     for member_type in self.members:
    #         if member_type.type_of(obj) is not None:
    #             return member_type.instance_to_py(obj)
    #     raise Exception('invalid')
    @classmethod
    def from_dict(cls, d):
        return merge_many_types(
            [TypeRegistry.type_from_dict(mem) for mem in d["members"]]
        )

    def _to_dict(self):
        return {"members": [mem.to_dict() for mem in self.members]}

    def __getattr__(self, attr):
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
        mapped_result = mapper.apply(result)

        # TODO: scan through for ID
        from .ops_primitives.list_ import object_lookup

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

    def _hashable(self):
        return tuple(
            (k, hash(v), k in self.not_required_keys)
            for k, v in self.property_types.items()
        )

    def __getitem__(self, key: str) -> Type:
        return self.property_types[key]

    def _assign_type_inner(self, other_type):
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
            if k not in other_type.property_types or not ptype.assign_type(
                other_type.property_types[k]
            ):
                return False
        return True

    def _to_dict(self):
        property_types = {}
        for key, type_ in self.property_types.items():
            property_types[key] = type_.to_dict()
        result = {"propertyTypes": property_types}
        if self.not_required_keys:
            result["notRequiredKeys"] = list(self.not_required_keys)
        return result

    @classmethod
    def from_dict(cls, d):
        property_types = {}
        for key, type_ in d["propertyTypes"].items():
            property_types[key] = TypeRegistry.type_from_dict(type_)
        not_required_keys = set()
        if "notRequiredKeys" in d:
            not_required_keys = set(d["notRequiredKeys"])
        return cls(property_types, not_required_keys)

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
        mapped_result = mapper.apply(result)
        if extra is not None:
            return mapped_result[extra[0]]
        return mapped_result


@dataclasses.dataclass(frozen=True)
class Dict(Type):
    name = "dict"

    key_type: Type = String()
    object_type: Type = Any()

    @property
    def property_types(self):
        class DictPropertyTypes:
            def values(_self):
                return [self.object_type]

            def get(_self, _):
                return self.object_type

        return DictPropertyTypes()

    def __post_init__(self):
        # Note this differs from Python's Dict in that keys are always strings!
        # TODO: consider if we can / should accept key_type. Would make JS side
        # harder since js objects can only have string keys.
        if not String().assign_type(self.key_type):
            raise Exception("Dict only supports string keys!")

    def _assign_type_inner(self, other_type):
        if isinstance(other_type, TypedDict):
            return all(
                self.object_type.assign_type(t)
                for t in other_type.property_types.values()
            )
        return super()._assign_type_inner(other_type)

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
    def __init__(self, **attr_types: Type):
        self.__dict__["attr_types"] = attr_types
        for k, v in attr_types.items():
            self.__dict__[k] = v

    @property
    def type_vars(self):
        if self.__class__ == ObjectType:
            return self.attr_types
        else:
            return super().type_vars

    def property_types(self) -> dict[str, Type]:
        return self.type_vars

    @classmethod
    def type_of_instance(cls, obj):
        variable_prop_types = {}
        for prop_name in cls.type_attrs():
            prop_type = TypeRegistry.type_of(getattr(obj, prop_name))
            # print("TYPE_OF", cls, prop_name, prop_type, type(getattr(obj, prop_name)))
            variable_prop_types[prop_name] = prop_type
        return cls(**variable_prop_types)

    def _to_dict(self) -> dict:
        d: dict = {"_is_object": True}
        d = self.class_to_dict()
        # TODO: we don't need _is_object, now that we have base_type everywhere.
        # Remove the check for self._base_type.__class__ != ObjectType, and get
        # rid of _is_object (need to update frontend as well).
        d["_is_object"] = True
        for k, prop_type in self.property_types().items():
            d[to_weavejs_typekey(k)] = prop_type.to_dict()
        return d

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


@dataclasses.dataclass(frozen=True)
class TypeType(ObjectType):
    name = "type"

    instance_classes = [Type]
    attr_types: dict[str, Type] = dataclasses.field(default_factory=dict)

    def property_types(self) -> dict[str, Type]:
        return self.attr_types

    def _hashable(self):
        return tuple((k, hash(v)) for k, v in self.property_types().items())

    @classmethod
    def type_of_instance(cls, obj):
        from . import infer_types

        attr_types = {}
        for field in dataclasses.fields(obj):
            attr_types[field.name] = infer_types.python_type_to_type(field.type)
        return cls(attr_types)

    def _to_dict(self):
        # we ensure we match the layout of ObjectType, so WeaveJS
        # can handle it the same way.
        d = {"_is_object": True}
        for k, t in self.attr_types.items():
            d[k] = t.to_dict()
        return d

    @classmethod
    def from_dict(cls, d):
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

    def _hashable(self):
        return (
            tuple((k, hash(v)) for k, v in self.input_types.items()),
            hash(self.output_type),
        )

    def _is_assignable_to(self, other_type) -> typing.Optional[bool]:
        if other_type.__class__ != Function:
            return other_type.assign_type(self.output_type)
        return None

    def assign_type(self, next_type: Type) -> bool:
        if not self.input_types and not isinstance(next_type, Function):
            # Allow assignment of T to () -> T.
            # Compile handles this in the compile_quote pass.
            return self.output_type.assign_type(next_type)
        return super().assign_type(next_type)

    @classmethod
    def type_of_instance(cls, obj):
        if isinstance(obj.type, Function):
            # Its already a Function type, so just return it.
            # TODO: I'm not sure if this is right, this makes FunctionType
            # a top of sorts...
            return obj.type
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

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(obj.to_json(), f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.object.json") as f:
            # TODO: no circular imports!
            from . import graph

            return graph.Node.node_from_json(json.load(f))


@dataclasses.dataclass(frozen=True)
class RefType(Type):
    object_type: Type = UnknownType()

    @classmethod
    def type_of_instance(cls, obj):
        return cls(obj.type)

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


def string_enum_type(*vals):
    return UnionType(*[Const(String(), v) for v in vals])


def literal(val: typing.Any) -> Const:
    return Const(TypeRegistry.type_of(val), val)


RUN_STATE_TYPE = string_enum_type("pending", "running", "finished", "failed")


# TODO: get rid of all the underscores. This is another
#    conflict with making ops automatically lazy
@dataclasses.dataclass(frozen=True)
class RunType(ObjectType):
    id: Type = String()
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

    def _is_assignable_to(self, other_type) -> typing.Optional[bool]:
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
    from .language_features.tagging import tagged_value_type

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
        if a.name == b.name:
            next_type_attrs = {}
            for key in a.type_attrs():
                next_type_attrs[key] = merge_types(getattr(a, key), getattr(b, key))
            return type(a)(**next_type_attrs)

    if isinstance(a, List) and isinstance(b, List):
        return List(merge_types(a.object_type, b.object_type))

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


def _merge_unknowns_of_type_with_types(of_type: Type, with_types: list[Type]):
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
                of_type.object_type, [t.object_type for t in with_types]  # type: ignore
            )
        )
    elif isinstance(of_type, Dict):
        return Dict(
            of_type.key_type,
            _merge_unknowns_of_type_with_types(
                of_type.value_type, [t.value_type for t in with_types]  # type: ignore
            ),
        )
    elif isinstance(of_type, TypedDict):
        return TypedDict(
            {
                key: _merge_unknowns_of_type_with_types(
                    value_type, [t.property_types.get(key, NoneType()) for t in with_types]  # type: ignore
                )
                for key, value_type in of_type.property_types.items()
            }
        )
    elif isinstance(of_type, TaggedValueType):
        return TaggedValueType(
            _merge_unknowns_of_type_with_types(of_type.tag, [t.tag for t in with_types]),  # type: ignore
            _merge_unknowns_of_type_with_types(
                of_type.value, [t.value for t in with_types]  # type: ignore
            ),
        )
    elif isinstance(of_type, Const):
        return Const(
            _merge_unknowns_of_type_with_types(
                of_type.val_type, [t.val_type for t in with_types]  # type: ignore
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


def is_list_like(t: Type) -> bool:
    return List().assign_type(non_none(t))


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
