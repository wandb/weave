import json
from dataclasses import field, dataclass
import typing
from ..decorator_type import type as weave_type
from .. import weave_types as types

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

TODO: Refactor how the opaque dict works - I think we can remove it and make
each type feel/look like a a json blob.
"""


@weave_type("UntypedOpaqueDict", True)
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

    json_str: str = field(default="{}")

    @classmethod
    def from_json_dict(cls, json_dict: dict):
        inst = cls(json_str=json.dumps(json_dict, separators=(",", ":")))
        inst._json_dict = json_dict
        return inst

    def get(self, key, default=None):
        return self.json_dict.get(key, default)

    def __eq__(self, other):
        return self.json_dict == other.json_dict

    def __getitem__(self, key):
        return self.json_dict[key]

    def __setitem__(self, key, value):
        raise NotImplementedError("UntypedOpaqueDict is immutable")

    def __delitem__(self, key):
        raise NotImplementedError("UntypedOpaqueDict is immutable")

    def __iter__(self):
        return iter(self.json_dict)

    def __len__(self):
        return len(self.json_dict)

    @property
    def json_dict(self):
        if not hasattr(self, "_json_dict"):
            self._json_dict = json.loads(self.json_str)
        return self._json_dict


@dataclass
class GQLTypeMixin:
    gql: UntypedOpaqueDict = field(default_factory=UntypedOpaqueDict)

    @classmethod
    def from_gql(cls, gql_dict: dict):
        return cls(UntypedOpaqueDict.from_json_dict(gql_dict))


@weave_type("org", True)
class Org(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


OrgType = Org.WeaveType()  # type: ignore
OrgType = typing.cast(types.Type, OrgType)


@weave_type("entity", True)
class Entity(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


EntityType = Entity.WeaveType()  # type: ignore
EntityType = typing.cast(types.Type, EntityType)


@weave_type("user", True)
class User(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


UserType = User.WeaveType()  # type: ignore
UserType = typing.cast(types.Type, UserType)


@weave_type("project", True)
class Project(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


ProjectType = Project.WeaveType()  # type: ignore
ProjectType = typing.cast(types.Type, ProjectType)


@weave_type("run", True)
class Run(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


RunType = Run.WeaveType()  # type: ignore
RunType = typing.cast(types.Type, RunType)


@weave_type("artifactType", True)
class ArtifactType(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


ArtifactTypeType = ArtifactType.WeaveType()  # type: ignore
ArtifactTypeType = typing.cast(types.Type, ArtifactTypeType)


@weave_type("artifact", True)  # Name and Class mismatch intention due to weave0
class ArtifactCollection(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


ArtifactCollectionType = ArtifactCollection.WeaveType()  # type: ignore
ArtifactCollectionType = typing.cast(types.Type, ArtifactCollectionType)


@weave_type("artifactVersion", True)
class ArtifactVersion(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
    """


ArtifactVersionType = ArtifactVersion.WeaveType()  # type: ignore
ArtifactVersionType = typing.cast(types.Type, ArtifactVersionType)


@weave_type(
    "artifactMembership", True
)  # Name and Class mismatch intention due to weave0
class ArtifactCollectionMembership(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
    """


ArtifactCollectionMembershipType = ArtifactCollectionMembership.WeaveType()  # type: ignore
ArtifactCollectionMembershipType = typing.cast(
    types.Type, ArtifactCollectionMembershipType
)


@weave_type("artifactAlias", True)
class ArtifactAlias(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
    """


ArtifactAliasType = ArtifactAlias.WeaveType()  # type: ignore
ArtifactAliasType = typing.cast(types.Type, ArtifactAliasType)


@weave_type("report", True)
class Report(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
    """


ReportType = Report.WeaveType()  # type: ignore
ReportType = typing.cast(types.Type, ReportType)


@weave_type("runQueue", True)
class RunQueue(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
    """


RunQueueType = RunQueue.WeaveType()  # type: ignore
RunQueueType = typing.cast(types.Type, RunQueueType)


# Simple types (maybe should be put into primitives?)


@weave_type("link", True)
class Link:
    name: str
    url: str


LinkType = Link.WeaveType()  # type: ignore
LinkType = typing.cast(types.Type, LinkType)
