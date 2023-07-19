import json
import functools
from dataclasses import field, dataclass
import typing
from .. import mappers_python
from .. import weave_types as types
from ..decorator_type import type as weave_type

"""
This file contains all the "W&B Domain Types". Each domain type should
correspond to exactly 1 type/interface in the WB GQL schema. Not all types are
represented as we only have implemented the subset that is required for Weave1
compatibility. Each type follows the same pattern for declaration. Consider
User:

@weave_type("user", True)                       # Sets the Weave type to be a plain string called "user"
class User(GQLTypeMixin):                       # Creates the Weave type in Weave1 and adds the GQLTypeMixin
    REQUIRED_FRAGMENT = "id name"               # Declares a minimum GQL fragment that should be used whenever loading this type from GQL

UserType = User.WeaveType()  # type: ignore     # Exports a casted singleton type for easier construction in domain ops.
UserType = typing.cast(types.Type, UserType) .  # Note: the type: ignore and cast could be removed if we fix the .pyi file for decorator_type

There are two main concepts to grasp:
    1. The `REQUIRED_FRAGMENT` is used to specify the minimum GQL fragment that
       should be used when loading this type from GQL. In most cases
        this is just the ID and name, but in some cases we need more
        information. For example, when loading a Run, we also load the Project
        (and extension, the project's Entity).
    2. The data is currently stored in `User.gql` - which gets serialized as an
       untyped string, but can be accessed like a dictionary. See
       `UntypedOpaqueDict` for details.

TODO: Decide if the nested fragments are really necessary. If not, it will
require changing a few of the ops to fetch such info as well
      as updating the mocked tests.

"""


class GQLClassWithKeysType(types.Type):
    # Has no instance classes or instance class - type of is performed in
    # original weave type

    def __init__(self, keyless_weave_type: types.Type, keys: dict[str, types.Type]):
        self.keyless_weave_type = keyless_weave_type
        self.keys = keys

    def _assign_type_inner(self, other_type) -> bool:
        return isinstance(other_type, GQLClassWithKeysType)

    def _str_repr(self) -> str:
        keys_repr = dict(sorted([(k, v.__repr__()) for k, v in self.keys.items()]))
        return f"{self.keyless_weave_type.__class__.name}WithKeys({keys_repr})"

    def __repr__(self) -> str:
        return self._str_repr()

    def _to_dict(self):
        property_types = {}
        for key, type_ in self.keys().items():
            property_types[key] = type_.to_dict()
        result = {"keys": property_types}
        return result

    @classmethod
    def from_dict(cls, d):
        property_types = {}
        for key, type_ in d["keys"].items():
            property_types[key] = types.TypeRegistry.type_from_dict(type_)
        NewClass = cls.instance_class.WeaveType.with_keys(property_types)
        return NewClass()

    @classmethod
    def type_of_instance(cls, obj):
        property_types = {}
        for k, v in obj.items():
            property_types[k] = types.TypeRegistry.type_of(v)
        return cls(property_types)

    def save_instance(self, obj, artifact, name):
        serializer = mappers_python.map_to_python(self, artifact)
        result = serializer.apply(obj)
        with artifact.new_file(
            f"{name}.{self.keyless_weave_type.__class__.__name__}WithKeys.json"
        ) as f:
            json.dump(result, f, allow_nan=False)

    def load_instance(self, artifact, name, extra=None):
        # with artifact.open(f'{name}.type.json') as f:
        #     obj_type = TypeRegistry.type_from_dict(json.load(f))
        with artifact.open(
            f"{name}.{self.keyless_weave_type.__class__.__name__}WithKeys.json"
        ) as f:
            result = json.load(f)
        mapper = mappers_python.map_from_python(self, artifact)
        mapped_result = mapper.apply(result)
        if extra is not None:
            return mapped_result[extra[0]]
        return mapped_result


def with_keys(self, keys: dict[str, types.Type]) -> types.Type:
    """Creates a new Weave Type that is assignable to the original Weave Type, but
    also has the specified keys. This is used during the compile pass for creating a Weave Type
    to represent the exact output type of a specific GQL query, and for communicating the
    data shape to arrow."""

    return GQLClassWithKeysType(self, keys)


def type_of_instance(self, obj: "GQLTypeMixin") -> types.Type:
    if obj.gql == {} or obj.gql is None:
        return self

    gql_type = typing.cast(types.TypedDict, types.TypeRegistry.type_of(obj.gql))
    return self.with_keys(gql_type.property_types)


def gql_weave_type(
    name,
) -> typing.Callable[[typing.Type["GQLTypeMixin"]], typing.Type["GQLTypeMixin"]]:
    """Decorator that emits a Weave Type for the decorated GQL instance type."""

    def _gql_weave_type(
        _instance_class: typing.Type["GQLTypeMixin"],
    ) -> typing.Type["GQLTypeMixin"]:
        decorator = weave_type(
            name,
            True,
            None,
            {"with_keys": with_keys, "type_of_instance": type_of_instance},
        )
        return decorator(_instance_class)

    return _gql_weave_type


@dataclass
class UntypedOpaqueDict:
    """
    UntypedOpaqueDict is a Weave Type that is used to store arbitrary JSON data.
    Unlike `Dict` or `TypedDict`, this Type does not need to define the keys/fields.
    This is useful in particular for storing GQL responses where the response schema
    may change over time. Usage:

    # From JSON String
    d = UntypedOpaqueDict(json_str='{"a": 1, "b": 2}')
    d["a"]  # 1

    # From Dictionary
    d = UntypedOpaqueDict.from_dict({"a": 1, "b": 2})
    d["a"]  # 1

    Importantly, this will serialize the data as a JSON string, so it can be stored and
    loaded using the Weave Type system.
    """

    json: dict = field(default_factory=dict)

    @classmethod
    def from_json_dict(cls, json_dict: dict):
        return cls(json_dict)

    def get(self, key, default=None):
        return self.json.get(key, default)

    def __eq__(self, other):
        return self.json == other.json

    def __getitem__(self, key):
        return self.json[key]

    def __setitem__(self, key, value):
        raise NotImplementedError("UntypedOpaqueDict is immutable")

    def __delitem__(self, key):
        raise NotImplementedError("UntypedOpaqueDict is immutable")

    def __iter__(self):
        return iter(self.json)

    def __len__(self):
        return len(self.json)


class UntypedOpaqueDictType(types.Type):
    instance_class = UntypedOpaqueDict
    instance_classes = [UntypedOpaqueDict]

    def instance_to_dict(self, obj: UntypedOpaqueDict):
        return obj.json

    def instance_from_dict(self, obj):
        return UntypedOpaqueDict(json=obj)


@dataclass
class GQLTypeMixin:
    gql: UntypedOpaqueDict = field(default_factory=UntypedOpaqueDict)

    def with_keys(self, *keys) -> "GQLTypeMixin":
        return self.__class__(
            gql=UntypedOpaqueDict(json={k: self.gql[k] for k in keys})
        )

    @classmethod
    def from_gql(cls, gql_dict: dict):
        return cls(gql=UntypedOpaqueDict(gql_dict))


@gql_weave_type("org")
class Org(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
        name
    """


OrgType = Org.WeaveType()  # type: ignore
OrgType = typing.cast(types.Type, OrgType)


@gql_weave_type("entity")
class Entity(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
        name
    """


EntityType = Entity.WeaveType()  # type: ignore
EntityType = typing.cast(types.Type, EntityType)


@gql_weave_type("user")
class User(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
        name
    """


UserType = User.WeaveType()  # type: ignore
UserType = typing.cast(types.Type, UserType)


@gql_weave_type("project")
class Project(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
        name
    """


ProjectType = Project.WeaveType()  # type: ignore
ProjectType = typing.cast(types.Type, ProjectType)


@gql_weave_type("run")
class Run(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
        name
    """


RunType = Run.WeaveType()  # type: ignore
RunType = typing.cast(types.Type, RunType)


@gql_weave_type("artifactType")
class ArtifactType(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
        name
    """


ArtifactTypeType = ArtifactType.WeaveType()  # type: ignore
ArtifactTypeType = typing.cast(types.Type, ArtifactTypeType)


@gql_weave_type("artifact")  # Name and Class mismatch intention due to weave0
class ArtifactCollection(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
        name
    """


ArtifactCollectionType = ArtifactCollection.WeaveType()  # type: ignore
ArtifactCollectionType = typing.cast(types.Type, ArtifactCollectionType)


@gql_weave_type("artifactVersion")
class ArtifactVersion(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
    """


ArtifactVersionType = ArtifactVersion.WeaveType()  # type: ignore
ArtifactVersionType = typing.cast(types.Type, ArtifactVersionType)


@gql_weave_type("artifactMembership")  # Name and Class mismatch intention due to weave0
class ArtifactCollectionMembership(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
    """


ArtifactCollectionMembershipType = ArtifactCollectionMembership.WeaveType()  # type: ignore
ArtifactCollectionMembershipType = typing.cast(
    types.Type, ArtifactCollectionMembershipType
)


@gql_weave_type("artifactAlias")
class ArtifactAlias(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
    """


ArtifactAliasType = ArtifactAlias.WeaveType()  # type: ignore
ArtifactAliasType = typing.cast(types.Type, ArtifactAliasType)


@gql_weave_type("report")
class Report(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
    """


ReportType = Report.WeaveType()  # type: ignore
ReportType = typing.cast(types.Type, ReportType)


@gql_weave_type("runQueue")
class RunQueue(GQLTypeMixin):
    REQUIRED_FRAGMENT = f"""
        id
    """


RunQueueType = RunQueue.WeaveType()  # type: ignore
RunQueueType = typing.cast(types.Type, RunQueueType)


# Simple types (maybe should be put into primitives?)


@weave_type("link")
class Link:
    name: str
    url: str


LinkType = Link.WeaveType()  # type: ignore
LinkType = typing.cast(types.Type, LinkType)
