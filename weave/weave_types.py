# from . import mappers_python
# from . import mappers_arrow
import typing
import typing_extensions
import types
import functools
import pyarrow as pa
import pyarrow.parquet as pq
import json
from collections.abc import Iterable, Mapping

from . import box
from . import errors


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
    return res


@functools.cache
def instance_class_to_potential_type(cls):
    mapping = instance_class_to_potential_type_map()
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
        name = type_class.__dict__.get("name")
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
    def type_of(obj):
        if isinstance(obj, Type):
            return Type()

        # use reversed instance_class_to_potential_type so our result
        # is the most specific type.
        for type_ in reversed(instance_class_to_potential_type(type(obj))):
            obj_type = type_.type_of(obj)
            if obj_type is not None:
                return obj_type
        raise errors.WeaveTypeError("no type for obj: %s" % obj)

    @staticmethod
    def type_from_dict(d):
        from . import weavejs_fixes

        d = weavejs_fixes.unwrap_tag_type(d)
        # The javascript code sends simple types as just strings
        # instead of {'type': 'string'} for example
        type_name = d["type"] if isinstance(d, dict) else d
        if type_name == "type":
            return Type()
        type_ = type_name_to_type(type_name)
        if type_ is None:
            raise errors.WeaveSerializeError("Can't deserialize type from: %s" % d)
        return type_.from_dict(d)


class Type:
    name = "type"
    instance_class: typing.Optional[type]
    instance_classes: typing.Union[type, typing.List[type], None] = None

    @classmethod
    def _instance_classes(cls):
        """Helper to get instance_classes as iterable."""
        if cls.instance_classes is None:
            return ()
        if isinstance(cls.instance_classes, Iterable):
            return cls.instance_classes
        return (cls.instance_classes,)

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

    def assign_type(self, next_type):
        if isinstance(next_type, self.__class__):
            return self
        return Invalid()

    def to_dict(self):
        d = {"type": self.name}
        d.update(self._to_dict())
        return d

    @classmethod
    def from_dict(cls, d):
        return cls()

    # To be overridden
    def _to_dict(self):
        return {}

    # def _ipython_display_(self):
    #     from . import show
    #     return show(self)

    def __eq__(self, other):
        return (
            isinstance(other, Type)
            and self.name == other.name
            and self.__dict__ == other.__dict__
        )

    # save_instance/load_instance on Type are used to save/load actual Types
    # since type_of(types.Int()) == types.Type()
    def save_instance(self, obj, artifact, name):
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

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.object.json") as f:
            d = json.load(f)
        if self.__class__ == Type:
            return TypeRegistry.type_from_dict(d)
        return self.instance_from_dict(d)

    def instance_to_dict(self, obj):
        raise NotImplementedError

    def instance_from_dict(self, d):
        raise NotImplementedError


class BasicType(Type):
    def to_dict(self):
        # A basic type is serialized as just its string name.
        return self.name

    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(obj, f)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.object.json") as f:
            return json.load(f)


class Invalid(BasicType):
    name = "invalid"

    def assign_type(self, next_type):
        return next_type


class UnknownType(BasicType):
    name = "unknown"

    def assign_type(self, next_type):
        return next_type


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
        return Any()


class Const(Type):
    name = "const"

    def __init__(self, type_, val):
        self.val_type = type_
        self.val = val

    @classmethod
    def type_of_instance(cls, obj):
        return cls(obj)

    def assign_type(self, next_type):
        if isinstance(next_type, Const):
            # This does a check on class equality, so won't work for
            # fancier types. We can fix later if we need to.
            if self.__class__ != next_type.__class__:
                return Invalid()
            if self.val == next_type.val:
                return self
        return self.val_type.assign_type(next_type)

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


class Int(Number):
    name = "int"
    instance_classes = int

    @classmethod
    def is_instance(cls, obj):
        # Special case, in Python bool isinstance of obj!
        if type(obj) == bool:
            return False
        return super().is_instance(obj)


class Boolean(BasicType):
    instance_classes = bool
    name = "boolean"

    def save_instance(self, obj, artifact, name):
        # BoxedBool is actually a box, not a subclass of bool, since
        # we can't subclass bool in Python. So we unbox it here.
        if isinstance(obj, box.BoxedBool):
            obj = obj.val
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(obj, f)


class ConstNumber(Type):
    name = "constnumber"

    def __init__(self, val):
        self.val = val

    @classmethod
    def from_dict(cls, d):
        return cls(d["val"])

    def _to_dict(self):
        return {"val": self.val}


class UnionType(Type):
    name = "union"

    members: Type

    def __init__(self, *members):
        all_members = []
        for mem in members:
            if isinstance(mem, UnionType):
                all_members += mem.members
            else:
                all_members.append(mem)
        self.members = all_members

    def assign_type(self, other):
        if isinstance(other, UnionType):
            # TODO: implement me. (We've done this in _dtypes and in js so refer there)
            raise NotImplementedError
        for member in self.members:
            assigned = member.assign_type(other)
            if assigned != Invalid():
                return assigned
        return Invalid()

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

    def __str__(self):
        return "<UnionType %s>" % " | ".join((str(m) for m in self.members))


class ArrowTableList(Iterable):
    def __init__(self, arrow_table, mapper, artifact):
        self._arrow_table = arrow_table
        self._artifact = artifact
        self._deserializer = mapper

    def __getitem__(self, index):
        if index >= self._arrow_table.num_rows:
            return None
        # Very inefficient, we always read the whole row!
        # TODO: We need to make this column access lazy. But we also want
        #     vectorize access generally, which probably happens in a compile
        #     pass. Need to think about it.
        row_dict = {}
        for column in self._arrow_table.column_names:
            row_dict[column] = self._arrow_table.column(column)[index].as_py()
        return self._deserializer.apply(row_dict)

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    index = __getitem__

    def __len__(self):
        return self._arrow_table.num_rows

    count = __len__

    def __eq__(self, other):
        if len(self) != len(other):
            return False
        for x, y in zip(iter(self), iter(other)):
            if x != y:
                return False
        return True


class ArrowArrayList(Iterable):
    def __init__(self, arrow_array):
        self._arrow_array = arrow_array

    def __getitem__(self, index):
        if index >= len(self._arrow_array):
            return None
        return self._arrow_array[index].as_py()

    index = __getitem__

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __eq__(self, other):
        if len(self) != len(other):
            return False
        for s, o in zip(self, other):
            if s != o:
                return False
        return True

    def __len__(self):
        return len(self._arrow_array)

    count = __len__


class List(Type):
    name = "list"
    instance_classes = [set, list, ArrowTableList]

    def __init__(self, object_type):
        self.object_type = object_type

    def _to_dict(self):
        return {"objectType": self.object_type.to_dict()}

    @classmethod
    def from_dict(cls, d):
        return cls(TypeRegistry.type_from_dict(d["objectType"]))

    @classmethod
    def type_of_instance(cls, obj):
        list_obj_type = UnknownType()
        for item in obj:
            obj_type = TypeRegistry.type_of(item)
            if obj_type is None:
                raise Exception("can't detect type for object: %s" % item)
            next_type = list_obj_type.assign_type(obj_type)
            if isinstance(next_type, Invalid):
                next_type = UnionType(list_obj_type, obj_type)
            list_obj_type = next_type
        return cls(list_obj_type)

    def save_instance(self, obj, artifact, name):
        obj_type = self.object_type

        from . import mappers_arrow

        serializer = mappers_arrow.map_to_arrow(obj_type, artifact)

        pyarrow_type = serializer.result_type()

        py_objs = (serializer.apply(o) for o in obj)

        with artifact.new_file(f"{name}.parquet", binary=True) as f:
            arr = pa.array(py_objs, type=pyarrow_type)
            if pa.types.is_struct(arr.type):
                rb = pa.RecordBatch.from_struct_array(
                    arr
                )  # this pivots to columnar layout
                table = pa.Table.from_batches([rb])
            else:
                table = pa.Table.from_arrays(
                    [arr], names=["_singleton"], metadata={"singleton": "1"}
                )
            pq.write_table(table, f)

    def load_instance(self, artifact, name, extra=None):
        from . import mappers_arrow

        with artifact.open(f"{name}.parquet", binary=True) as f:
            table = pq.read_table(f)
            if (
                table.schema.metadata is not None
                and b"singleton" in table.schema.metadata
            ):
                return ArrowArrayList(table.column("_singleton"))

            mapper = mappers_arrow.map_from_arrow(self.object_type, artifact)
            atl = ArrowTableList(pq.read_table(f), mapper, artifact)
            return atl

    def __str__(self):
        return "<ListType %s>" % self.object_type


class TypedDict(Type):
    name = "typedDict"
    instance_classes = [dict]

    def __init__(self, property_types):
        self.property_types = property_types

    def assign_type(self, other_type):
        if not isinstance(other_type, TypedDict):
            return Invalid()

        # Compute the intersection of all keys. Its important to use a dict here
        # rather than a set, so that we have a stable ordering in our output dict.
        # (python3.7+ guarantees key ordering of dicts)
        all_keys_dict = {}
        for k in self.property_types.keys():
            all_keys_dict[k] = True
        for k in other_type.property_types.keys():
            all_keys_dict[k] = True

        next_prop_types = {}
        for key in all_keys_dict.keys():
            self_prop_type = self.property_types.get(key, none_type)
            other_prop_type = other_type.property_types.get(key, none_type)
            next_prop_type = self_prop_type.assign_type(other_prop_type)
            if isinstance(next_prop_type, Invalid):
                next_prop_type = UnionType(self_prop_type, other_prop_type)
            next_prop_types[key] = next_prop_type
        return TypedDict(next_prop_types)

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
        from . import mappers_python

        serializer = mappers_python.map_to_python(self, artifact)
        result = serializer.apply(obj)
        with artifact.new_file(f"{name}.typedDict.json") as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(self, artifact, name, extra=None):
        # with artifact.open(f'{name}.type.json') as f:
        #     obj_type = TypeRegistry.type_from_dict(json.load(f))
        with artifact.open(f"{name}.typedDict.json") as f:
            result = json.load(f)
        from . import mappers_python

        mapper = mappers_python.map_from_python(self, artifact)
        return mapper.apply(result)

    def __str__(self):
        property_types = {}
        for key, type_ in self.property_types.items():
            property_types[key] = str(type_)
        return "<TypedDict %s>" % property_types


class Dict(Type):
    name = "dict"

    def __init__(self, key_type, value_type):
        # Note this differs from Python's Dict in that keys are always strings!
        # TODO: consider if we can / should accept key_type. Would make JS side
        # harder since js objects can only have string keys.
        if not isinstance(key_type, String):
            raise Exception("Dict only supports string keys!")
        self.key_type = key_type
        self.value_type = value_type

    def assign_type(self, other_type):
        if isinstance(other_type, Dict):
            next_key_type = self.key_type.assign_type(other_type.key_type)
            if isinstance(next_key_type, Invalid):
                next_key_type = UnionType(self.key_type, other_type.key_type)
            next_value_type = self.value_type.assign_type(other_type.value_type)
            if isinstance(next_value_type, Invalid):
                next_value_type = UnionType(self.value_type, other_type.value_type)
        else:
            # TODO: we could handle TypedDict here.

            return Invalid()

    def _to_dict(self):
        return {
            "keyType": self.key_type.to_dict(),
            "objectType": self.value_type.to_dict(),
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            TypeRegistry.type_from_dict(d["keyType"]),
            TypeRegistry.type_from_dict(d["objectType"]),
        )

    @classmethod
    def type_of_instance(cls, obj):
        value_type = UnknownType()
        for k, v in obj.items():
            if not isinstance(k, str):
                raise Exception("Dict only supports string keys!")
            value_type = value_type.assign_type(TypeRegistry.type_of(v))
        return cls(String(), value_type)

    def __str__(self):
        return "<Dict %s>" % self.value_type


class ObjectType(Type):
    # TODO: This is not a leaf type so we don't really want this name maybe?
    name = "object_type"

    type_vars: dict[str, Type] = {}

    def property_types(self):
        raise NotImplementedError

    def variable_property_types(self):
        # TODO: must be a subset of property_types
        result = {}
        for property_name in self.type_vars:
            property_val = getattr(self, property_name)
            result[property_name] = property_val
        return result

    def __str__(self):
        result = []
        for k, v in self.property_types().items():
            result.append("%s: %s" % (k, v))
        return "<%s {%s}>" % (self.__class__.__name__, ", ".join(result))

    def _to_dict(self):
        return {
            prop: prop_type.to_dict()
            for prop, prop_type in self.variable_property_types().items()
        }

    @classmethod
    def from_dict(cls, d):
        d = {i: d[i] for i in d if i != "type"}
        type_args = {
            prop: TypeRegistry.type_from_dict(prop_type)
            for prop, prop_type in d.items()
        }
        return cls(**type_args)

    @classmethod
    def type_of_instance(cls, obj):
        variable_prop_types = {}
        for prop_name in cls.type_vars:
            prop_type = TypeRegistry.type_of(getattr(obj, prop_name))
            # print("TYPE_OF", cls, prop_name, prop_type, type(getattr(obj, prop_name)))
            variable_prop_types[prop_name] = prop_type
        return cls(**variable_prop_types)

    def save_instance(self, obj, artifact, name):
        from . import mappers_python

        serializer = mappers_python.map_to_python(self, artifact)

        # TODO: do we inject the artifact here?
        #    Or maybe we do it in the mapper, and add the artifact
        #    prop to the object there as well?
        obj.artifact = artifact  # ??
        result = serializer.apply(obj)
        with artifact.new_file(f"{name}.object.json") as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.object.json") as f:
            result = json.load(f)
        from . import mappers_python

        mapper = mappers_python.map_from_python(self, artifact)
        return mapper.apply(result)


class Function(Type):
    name = "function"

    def __init__(self, input_types, output_type):
        self.input_types = input_types
        self.output_type = output_type

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


class LocalArtifactRefType(Type):
    name = "ref-type"

    def __init__(self, object_type):
        self.object_type = object_type

    def _to_dict(self):
        return {"objectType": self.object_type.to_dict()}

    @classmethod
    def from_dict(cls, d):
        return cls(TypeRegistry.type_from_dict(d["objectType"]))

    @classmethod
    def type_of_instance(cls, obj):
        return LocalArtifactRefType(obj.type)

    def __str__(self):
        return "<LocalArtifactRefType %s>" % self.object_type


# TODO: placeholders for now, and a place for table.py
#     to attach its methods. But we probably don't want this
#     to be in the core basic types file.


class Table(Type):
    name = "table"
    # TODO: don't default to Any?

    def __init__(self, object_type=Any()):
        self.object_type = object_type


class WBTable(Type):
    name = "wbtable"


# :( resolve circular imports by doing these at the bottom
# TODO: keep considering removing save_instance/load_instance from
# types themselves, and move to serializers/mappers somehow


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
class RunType(ObjectType):
    name = "run-type"
    type_vars = {
        "_inputs": TypedDict({}),
        "_history": List(Any()),
        "_output": Any(),
    }

    def __init__(self, _inputs, _history, _output):
        self._inputs = _inputs
        self._history = _history
        self._output = _output

    def property_types(self):
        return {
            "_id": String(),
            "_op_name": String(),
            "_state": RUN_STATE_TYPE,
            "_prints": List(String()),
            "_inputs": self._inputs,
            "_history": self._history,
            "_output": self._output,
        }


class FileType(ObjectType):
    name = "file"

    type_vars = {"extension": String()}

    def __init__(self, extension=String()):
        self.extension = extension

    def _to_dict(self):
        # NOTE: js_compat
        # In the js Weave code, file is a non-standard type that
        # puts a const string at extension as just a plain string.
        d = super()._to_dict()
        if isinstance(self.extension, Const):
            d["extension"] = self.extension.val
        return d

    @classmethod
    def from_dict(cls, d):
        # NOTE: js_compat
        # In the js Weave code, file is a non-standard type that
        # puts a const string at extension as just a plain string.
        d = {i: d[i] for i in d if i != "type"}
        if "extension" in d:
            d["extension"] = {
                "type": "const",
                "valType": "string",
                "val": d["extension"],
            }
        return super().from_dict(d)

    def property_types(self):
        return {
            "extension": self.extension,
        }


class SubDirType(ObjectType):
    # TODO doesn't match frontend
    name = "subdir"

    type_vars = {"file_type": FileType()}

    def __init__(self, file_type):
        self.file_type = file_type

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


# Ensure numpy types are loaded
from . import types_numpy
