import json
import typing
import hashlib

from dataclasses import dataclass, field
from . import weave_types as types
from . import artifact_fs
from . import gql_op_plugin


from .decorator_type import type as weave_type
from .input_provider import InputProvider


T = typing.TypeVar("T", bound="PartialObject")


class AbstractPartialObjectType(types.Type):
    """Base class for types like projectType(), runType(), etc. Instances of this class do not have keys,
    but they have a method called with_keys() that allows them to generate instances of the type with
    keys. E.g.,

    projectType().with_keys({"name": String()}) -> projectTypeWithKeys({"name": String()})

    Assignability rules:
    --------------------

    projectType() <- projectTypeWithKeys({"name": String()})  VALID
    projectTypeWithKeys({"name": Int()}) <- projectType()     INVALID
    """

    @classmethod
    def with_keys(cls, keys: dict[str, types.Type]) -> "PartialObjectType":
        """Creates a new Weave Type that is assignable to the original Weave Type, but
        also has the specified keys. This is used during the compile pass for creating a Weave Type
        to represent the exact output type of a specific GQL query, and for communicating the
        data shape to arrow."""

        return PartialObjectType(cls, keys)

    @classmethod
    def type_of_instance(cls, obj: "PartialObject") -> types.Type:
        if obj.gql == {} or obj.gql is None:
            return cls()

        gql_type = typing.cast(types.TypedDict, types.TypeRegistry.type_of(obj.gql))
        return cls.with_keys(gql_type.property_types)


def gql_weave_type(
    name: str,
) -> typing.Callable[[typing.Type[T]], typing.Type[T]]:
    """Decorator that emits a Weave Type for the decorated GQL instance type. Classes decorated
    with this decorator also emit a keyless weavetype. E.g.,

    @gql_weave_type("project")
    class Project(GQLTypeMixin):
        ...

    will emit a Weave Type for projectType(). Instances of projectType() have a method called
    with_keys() that allows them to generate instances of projectTypeWithKeys({...}).
    """

    def _gql_weave_type(_instance_class: typing.Type[T]) -> typing.Type[T]:
        decorator = weave_type(
            name,
            True,
            None,
            [AbstractPartialObjectType],
        )
        return decorator(_instance_class)

    return _gql_weave_type


@dataclass
class PartialObject:
    gql: dict = field(default_factory=dict)

    @classmethod
    def from_gql(cls: typing.Type[T], gql_dict: dict) -> T:
        return cls(gql=gql_dict)


class PartialObjectType(types.Type):
    """Base class for types like projectTypeWithKeys({...}), runTypeWithKeys({...}), etc.

    Assignability rules:
    --------------------

    projectType() <- projectTypeWithKeys({"name": String()})  VALID
    projectTypeWithKeys({"name": Int()}) <- projectType()     INVALID
    """

    # e.g., Project.WeaveType. Note: this property is the class itself, not an instance of the class.
    keyless_weave_type_class: typing.Type[types.Type]
    keys: dict[str, types.Type]  # e.g., {"name": String()}

    def __init__(
        self,
        keyless_weave_type_class: typing.Type[types.Type],
        keys: typing.Union[dict[str, types.Type], types.TypedDict],
    ):
        self.keyless_weave_type_class = keyless_weave_type_class
        if isinstance(keys, types.TypedDict):
            keys = keys.property_types
        self.keys = keys

    def _assign_type_inner(self, other_type: types.Type) -> bool:
        # TODO: think more about how this will work with tags - might need to be modified
        return (
            isinstance(other_type, PartialObjectType)
            and self.keyless_weave_type_class == other_type.keyless_weave_type_class
            and self.keys == other_type.keys
        )

    def _is_assignable_to(self, other_type: types.Type) -> typing.Optional[bool]:
        if other_type.__class__ is self.keyless_weave_type_class:
            return True

        if isinstance(other_type, PartialObjectType):
            if self.keyless_weave_type_class != other_type.keyless_weave_type_class:
                return False

            other_td = types.TypedDict(other_type.keys)
            self_td = types.TypedDict(self.keys)
            return other_td.assign_type(self_td)

        return False

    def _str_repr(self) -> str:
        keys_repr = dict(sorted([(k, v.__repr__()) for k, v in self.keys.items()]))
        return f"{self.keyless_weave_type_class.__name__}WithKeys({keys_repr})"

    def __repr__(self) -> str:
        return self._str_repr()

    def _to_dict(self) -> dict:
        property_types = {}
        for key, type_ in self.keys.items():
            property_types[key] = type_.to_dict()
        result = {
            "keys": property_types,
            "keyless_weave_type_class": self.keyless_weave_type_class().to_dict(),
        }
        return result

    def __eq__(self, other: typing.Any) -> bool:
        if isinstance(other, PartialObjectType):
            return (
                self.keyless_weave_type_class == other.keyless_weave_type_class
                and self.keys == other.keys
            )
        return False

    @classmethod
    def from_dict(cls, d: dict) -> "PartialObjectType":
        property_types = {}
        for key, type_ in d["keys"].items():
            property_types[key] = types.TypeRegistry.type_from_dict(type_)
        keyless_weave_type_class = types.TypeRegistry.type_from_dict(
            d["keyless_weave_type_class"]
        ).__class__

        return cls(keyless_weave_type_class, property_types)

    def save_instance(
        self, obj: PartialObject, artifact: artifact_fs.FilesystemArtifact, name: str
    ) -> None:
        from . import mappers_python

        serializer = mappers_python.map_to_python(self, artifact)
        result = serializer.apply(obj)
        with artifact.new_file(
            f"{name}.{self.keyless_weave_type_class.__name__}WithKeys.json"
        ) as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(
        self,
        artifact: artifact_fs.FilesystemArtifact,
        name: str,
        extra: typing.Optional[list] = None,
    ) -> PartialObject:
        from . import mappers_python

        with artifact.open(
            f"{name}.{self.keyless_weave_type_class.__name__}WithKeys.json"
        ) as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        mapped_result = mapper.apply(result)
        if extra is not None:
            return mapped_result[extra[0]]
        return typing.cast(PartialObject, mapped_result)

    def instance_to_dict(self, obj: PartialObject) -> dict[str, typing.Any]:
        return obj.gql

    def instance_from_dict(self, d: dict[str, typing.Any]) -> PartialObject:
        instance_class = typing.cast(
            typing.Type[PartialObject], self.keyless_weave_type_class.instance_class
        )
        return instance_class.from_gql(d)


ParamStrFn = typing.Callable[[InputProvider], str]


def _make_alias(*args: str, prefix: str = "alias") -> str:
    inputs = "_".join([str(arg) for arg in args])
    digest = hashlib.md5(inputs.encode()).hexdigest()
    return f"{prefix}_{digest}"


def _param_str(inputs: InputProvider, param_str_fn: typing.Optional[ParamStrFn]) -> str:
    param_str = ""
    if param_str_fn:
        param_str = param_str_fn(inputs)
    return param_str


def _alias(
    inputs: InputProvider,
    param_str_fn: typing.Optional[ParamStrFn],
    prop_name: str,
) -> str:
    alias = ""
    param_str = _param_str(inputs, param_str_fn)
    if param_str_fn:
        alias = f"{_make_alias(param_str, prefix=prop_name)}"
    return alias


def make_root_op_gql_op_output_type(
    prop_name: str,
    param_str_fn: ParamStrFn,
    output_type: AbstractPartialObjectType,
    use_alias: bool = False,
) -> gql_op_plugin.GQLOutputTypeFn:
    """Creates a GQLOutputTypeFn for a root op that returns a list of objects with keys."""

    def _root_op_gql_op_output_type(
        inputs: InputProvider, input_type: types.Type
    ) -> types.Type:
        key = (
            prop_name
            if not use_alias
            else _alias(
                inputs,
                param_str_fn,
                prop_name,
            )
        )

        key_type: types.Type = typing.cast(types.TypedDict, input_type)
        keys = ["instance", key, "edges", "node"]
        for key in keys:
            if isinstance(key_type, types.List):
                key_type = key_type.object_type
            if isinstance(key_type, types.TypedDict):
                key_type = key_type.property_types[key]

        object_type = output_type.with_keys(
            typing.cast(types.TypedDict, key_type).property_types
        )
        return types.List(object_type)

    return _root_op_gql_op_output_type
