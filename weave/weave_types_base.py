import dataclasses
import functools
import json
import typing
from collections.abc import Iterable

from . import errors


if typing.TYPE_CHECKING:
    from .refs import Ref
    from .artifacts_local import Artifact


def js_to_py_typename(typename: str) -> str:
    # WeaveJS overrides the table column type if the column name is id-like. See
    # use of `SPECIAL_ID_COLUMN_NAMES` in `mediaTypes.ts`. Unlike other types,
    # the "id" type does not describe the underlying data type. Furthermore,
    # there are no ops based on the "id" type. For that reason, I opted to not
    # put the id type in the type system for now, and just hap it to string.
    if typename == "id":
        return "string"
    return typename


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
    return mapping.get(js_to_py_typename(type_name))


def _clear_global_type_class_cache():
    instance_class_to_potential_type.cache_clear()
    type_name_to_type_map.cache_clear()
    type_name_to_type.cache_clear()


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
        if isinstance(obj, Type):
            return Type()

        obj_type = type_name_to_type("tagged").type_of(obj)
        if obj_type is not None:
            return obj_type

        potential_types = instance_class_to_potential_type(type(obj))  # type: ignore

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
        # return UnknownType()
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


# Adapted from https://stackoverflow.com/questions/18126552/how-to-run-code-when-a-class-is-subclassed
class _TypeSubclassWatcher(type):
    def __init__(cls, name, bases, clsdict):
        # This code will run whenever `Type` is subclassed!
        # Bust the cache!
        _clear_global_type_class_cache()
        super(_TypeSubclassWatcher, cls).__init__(name, bases, clsdict)

        # Set _base_type to the first base class
        if bases and bases[0] != Type:
            if cls.__dict__.get("_base_type") is None:
                cls._base_type = bases[0]()


@dataclasses.dataclass(frozen=True)
class Type(metaclass=_TypeSubclassWatcher):
    # This is like Typescript "extends", and is populated by default by
    # Python inheritance in our metaclass.
    _base_type: typing.ClassVar[typing.Optional["Type"]] = None

    instance_class: typing.ClassVar[typing.Optional[type]]
    instance_classes: typing.ClassVar[
        typing.Union[type, typing.List[type], None]
    ] = None

    def __repr__(self) -> str:
        return f"<{self.name}>"

    # This orders types by specificity.
    # A < B if A is assignable to B.
    # A == B if A is assignable to B and B is assignable to A.
    # If the types are not mutually assignable then an order is not defined, so __lt__
    # returns none.
    def __lt__(self, other: "Type") -> typing.Optional[bool]:
        self_assignable_to_other = other.assign_type(self)
        if self_assignable_to_other:
            other_assignable_to_self = self.assign_type(other)
            if other_assignable_to_self:
                return False
            return True
        return None

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
    def type_attrs(cls):
        type_attrs = []
        for field in dataclasses.fields(cls):
            if issubclass(field.type, Type):
                type_attrs.append(field.name)
        return type_attrs

    def type_vars(self) -> dict[str, "Type"]:
        type_vars = {}
        for field in dataclasses.fields(self.__class__):
            if issubclass(field.type, Type):
                type_vars[field.name] = getattr(self, field.name)
        return type_vars

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

    @property
    def name(self):
        return self.class_type_name()

    @property  # type: ignore
    def instance_class(self):
        return self._instance_classes()[-1]

    def assign_type(self, next_type: "Type") -> bool:
        # Union logic has to come before everything else.
        UnionType = type_name_to_type("union")
        if isinstance(next_type, UnionType):
            for t in next_type.members:
                if not self.assign_type(t):
                    return False
            return True
        elif isinstance(self, UnionType):
            return self._assign_type_inner(next_type)

        try:
            return next_type._is_assignable_to(self)
        except NotImplementedError:
            pass

        return self._assign_type_inner(next_type)

    def _is_assignable_to(self, assign_to: "Type") -> bool:
        raise NotImplementedError

    def _assign_type_inner(self, next_type: "Type") -> bool:
        if self.__class__ == next_type.__class__ or (
            next_type._base_type is not None
            and isinstance(next_type._base_type, self.__class__)
        ):
            if callable(self.type_vars):
                type_vars = self.type_vars()
            else:
                type_vars = self.type_vars
            for prop_name in type_vars:
                if not hasattr(next_type, prop_name):
                    raise errors.WeaveInternalError(
                        "type %s missing attributes of base type %s" % (next_type, self)
                    )
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
        if self._base_type is not None:
            type_props["_base_type"] = self._base_type.to_dict()
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
