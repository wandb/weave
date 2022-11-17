from .wandb_domain_gql import project_artifact_collection_type
from ..api import op
from . import wb_domain_types
from . import wandb_domain_gql


@op(name="artifact-type")
def type_(artifact: wb_domain_types.ArtifactCollection) -> wb_domain_types.ArtifactType:
    return wb_domain_types.ArtifactType(
        _project=artifact._project,
        artifact_type_name=artifact.sdk_obj.type,
    )


@op(name="artifact-name")
def name_(artifact: wb_domain_types.ArtifactCollection) -> str:
    return artifact.artifact_collection_name


@op(name="artifact-description")
def description(artifact: wb_domain_types.ArtifactCollection) -> str:
    return artifact.sdk_obj._attrs.get("description", "")


@op(name="artifact-versions")
def versions(
    artifact: wb_domain_types.ArtifactCollection,
) -> list[wb_domain_types.ArtifactVersion]:
    return [
        wb_domain_types.ArtifactVersion.from_sdk_obj(v)
        for v in artifact.sdk_obj.versions()
    ]


@op(name="artifact-createdAt")
def createdAt(artifact: wb_domain_types.ArtifactCollection) -> wb_domain_types.Date:
    return artifact.sdk_obj._attrs.get("createdAt", None)


@op(name="artifact-id")
def id(artifact: wb_domain_types.ArtifactCollection) -> str:
    return artifact.sdk_obj.id


@op(name="artifact-isPortfolio")
def is_portfolio(artifact: wb_domain_types.ArtifactCollection) -> bool:
    return wandb_domain_gql.artifact_collection_is_portfolio(artifact.sdk_obj)


@op(name="artifact-memberships")
def artifact_memberships(
    artifact: wb_domain_types.ArtifactCollection,
) -> list[wb_domain_types.ArtifactCollectionMembership]:
    return [
        wandb_domain_gql.artifact_collection_membership_for_alias(artifact, v.digest)
        for v in artifact.sdk_obj.versions()
    ]


@op(name="artifact-membershipForAlias")
def artifact_membership_for_alias(
    artifact: wb_domain_types.ArtifactCollection, aliasName: str
) -> wb_domain_types.ArtifactCollectionMembership:
    return wandb_domain_gql.artifact_collection_membership_for_alias(
        artifact, aliasName
    )


@op(name="artifact-lastMembership")
def artifact_last_membership(
    artifact: wb_domain_types.ArtifactCollection,
) -> wb_domain_types.ArtifactCollectionMembership:
    return wandb_domain_gql.artifact_collection_membership_for_alias(artifact, "latest")


@op(name="artifact-aliases")
def artifact_aliases(
    artifact: wb_domain_types.ArtifactCollection,
) -> list[wb_domain_types.ArtifactAlias]:
    return wandb_domain_gql.artifact_collection_aliases(artifact)


@op(name="artifact-project")
def artifact_project(
    artifact: wb_domain_types.ArtifactCollection,
) -> wb_domain_types.Project:
    return artifact._project
