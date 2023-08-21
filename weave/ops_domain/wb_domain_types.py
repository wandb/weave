import typing
from .. import weave_types as types
from ..decorator_type import type as weave_type
from ..gql_with_keys import (
    gql_weave_type,
    PartialObject,
    GeneratePartialMixin,
)

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


@gql_weave_type("org")
class Org(PartialObject):
    REQUIRED_FRAGMENT = """
        id
        name
    """


OrgType = Org.WeaveType()  # type: ignore
OrgType = typing.cast(GeneratePartialMixin, OrgType)


@gql_weave_type("entity")
class Entity(PartialObject):
    REQUIRED_FRAGMENT = """
        id
        name
    """


EntityType = Entity.WeaveType()  # type: ignore
EntityType = typing.cast(GeneratePartialMixin, EntityType)


@gql_weave_type("user")
class User(PartialObject):
    REQUIRED_FRAGMENT = """
        id
        name
    """


UserType = User.WeaveType()  # type: ignore
UserType = typing.cast(GeneratePartialMixin, UserType)


@gql_weave_type("project")
class Project(PartialObject):
    REQUIRED_FRAGMENT = """
        id
        name
    """


ProjectType = Project.WeaveType()  # type: ignore
ProjectType = typing.cast(GeneratePartialMixin, ProjectType)


@gql_weave_type("run")
class Run(PartialObject):
    REQUIRED_FRAGMENT = """
        id
        name
    """


RunType = Run.WeaveType()  # type: ignore
RunType = typing.cast(GeneratePartialMixin, RunType)


@gql_weave_type("artifactType")
class ArtifactType(PartialObject):
    REQUIRED_FRAGMENT = """
        id
        name
    """


ArtifactTypeType = ArtifactType.WeaveType()  # type: ignore
ArtifactTypeType = typing.cast(GeneratePartialMixin, ArtifactTypeType)


@gql_weave_type("artifact")  # Name and Class mismatch intention due to weave0
class ArtifactCollection(PartialObject):
    REQUIRED_FRAGMENT = """
        id
        name
    """


ArtifactCollectionType = ArtifactCollection.WeaveType()  # type: ignore
ArtifactCollectionType = typing.cast(GeneratePartialMixin, ArtifactCollectionType)


@gql_weave_type("artifactVersion")
class ArtifactVersion(PartialObject):
    REQUIRED_FRAGMENT = """
        id
    """


ArtifactVersionType = ArtifactVersion.WeaveType()  # type: ignore
ArtifactVersionType = typing.cast(GeneratePartialMixin, ArtifactVersionType)


@gql_weave_type("artifactMembership")  # Name and Class mismatch intention due to weave0
class ArtifactCollectionMembership(PartialObject):
    REQUIRED_FRAGMENT = """
        id
    """


ArtifactCollectionMembershipType = ArtifactCollectionMembership.WeaveType()  # type: ignore
ArtifactCollectionMembershipType = typing.cast(
    GeneratePartialMixin, ArtifactCollectionMembershipType
)


@gql_weave_type("artifactAlias")
class ArtifactAlias(PartialObject):
    REQUIRED_FRAGMENT = """
        id
    """


ArtifactAliasType = ArtifactAlias.WeaveType()  # type: ignore
ArtifactAliasType = typing.cast(GeneratePartialMixin, ArtifactAliasType)


@gql_weave_type("report")
class Report(PartialObject):
    REQUIRED_FRAGMENT = """
        id
    """


ReportType = Report.WeaveType()  # type: ignore
ReportType = typing.cast(GeneratePartialMixin, ReportType)


@gql_weave_type("runQueue")
class RunQueue(PartialObject):
    REQUIRED_FRAGMENT = """
        id
    """


RunQueueType = RunQueue.WeaveType()  # type: ignore
RunQueueType = typing.cast(GeneratePartialMixin, RunQueueType)


# Simple types (maybe should be put into primitives?)


@weave_type("link")
class Link:
    name: str
    url: str


LinkType = Link.WeaveType()  # type: ignore
LinkType = typing.cast(types.Type, LinkType)
