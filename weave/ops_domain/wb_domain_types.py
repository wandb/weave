import typing
from .. import weave_types as types
from ..decorator_type import type as weave_type

import json
from dataclasses import field

from ..gql_with_keys import gql_weave_type, GQLTypeMixin, GQLHasWithKeysType

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
l
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


@gql_weave_type("org")
class Org(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


OrgType = Org.WeaveType()  # type: ignore
OrgType = typing.cast(GQLHasWithKeysType, OrgType)


@gql_weave_type("entity")
class Entity(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


EntityType = Entity.WeaveType()  # type: ignore
EntityType = typing.cast(GQLHasWithKeysType, EntityType)


@gql_weave_type("user")
class User(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


UserType = User.WeaveType()  # type: ignore
UserType = typing.cast(GQLHasWithKeysType, UserType)


@gql_weave_type("project")
class Project(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


ProjectType = Project.WeaveType()  # type: ignore
ProjectType = typing.cast(GQLHasWithKeysType, ProjectType)


@gql_weave_type("run")
class Run(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


RunType = Run.WeaveType()  # type: ignore
RunType = typing.cast(GQLHasWithKeysType, RunType)


@gql_weave_type("artifactType")
class ArtifactType(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


ArtifactTypeType = ArtifactType.WeaveType()  # type: ignore
ArtifactTypeType = typing.cast(GQLHasWithKeysType, ArtifactTypeType)


@gql_weave_type("artifact")  # Name and Class mismatch intention due to weave0
class ArtifactCollection(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
        name
    """


ArtifactCollectionType = ArtifactCollection.WeaveType()  # type: ignore
ArtifactCollectionType = typing.cast(GQLHasWithKeysType, ArtifactCollectionType)


@gql_weave_type("artifactVersion")
class ArtifactVersion(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
    """


ArtifactVersionType = ArtifactVersion.WeaveType()  # type: ignore
ArtifactVersionType = typing.cast(GQLHasWithKeysType, ArtifactVersionType)


@gql_weave_type("artifactMembership")  # Name and Class mismatch intention due to weave0
class ArtifactCollectionMembership(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
    """


ArtifactCollectionMembershipType = ArtifactCollectionMembership.WeaveType()  # type: ignore
ArtifactCollectionMembershipType = typing.cast(
    GQLHasWithKeysType, ArtifactCollectionMembershipType
)


@gql_weave_type("artifactAlias")
class ArtifactAlias(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
    """


ArtifactAliasType = ArtifactAlias.WeaveType()  # type: ignore
ArtifactAliasType = typing.cast(GQLHasWithKeysType, ArtifactAliasType)


@gql_weave_type("report")
class Report(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
    """


ReportType = Report.WeaveType()  # type: ignore
ReportType = typing.cast(GQLHasWithKeysType, ReportType)


@gql_weave_type("runQueue")
class RunQueue(GQLTypeMixin):
    REQUIRED_FRAGMENT = """
        id
    """


RunQueueType = RunQueue.WeaveType()  # type: ignore
RunQueueType = typing.cast(GQLHasWithKeysType, RunQueueType)


# Simple types (maybe should be put into primitives?)


@weave_type("link")
class Link:
    name: str
    url: str


LinkType = Link.WeaveType()  # type: ignore
LinkType = typing.cast(types.Type, LinkType)
