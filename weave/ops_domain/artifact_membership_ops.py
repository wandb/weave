from ..api import op
from . import wb_domain_types
from . import wandb_domain_gql


@op(name="artifactMembership-versionIndex")
def artifact_membership_version_index(
    artifactMembership: wb_domain_types.ArtifactCollectionMembership,
) -> int:
    return artifactMembership.version_index


@op(name="artifactMembership-aliases")
def artifact_membership_aliases(
    artifactMembership: wb_domain_types.ArtifactCollectionMembership,
) -> list[wb_domain_types.ArtifactAlias]:
    return wandb_domain_gql.artifact_membership_aliases(artifactMembership)


@op(name="artifactMembership-collection")
def artifact_membership_collection(
    artifactMembership: wb_domain_types.ArtifactCollectionMembership,
) -> wb_domain_types.ArtifactCollection:
    return artifactMembership._artifact_collection


@op(name="artifactMembership-artifactVersion")
def artifact_membership_version(
    artifactMembership: wb_domain_types.ArtifactCollectionMembership,
) -> wb_domain_types.ArtifactVersion:
    return wb_domain_types.ArtifactVersion(
        _artifact_sequence=artifactMembership._artifact_collection,
        version_index=artifactMembership.version_index,
    )


@op(name="artifactMembership-createdAt")
def artifact_membership_created_at(
    artifactMembership: wb_domain_types.ArtifactCollectionMembership,
) -> wb_domain_types.Date:
    return wandb_domain_gql.artifact_membership_created_at(artifactMembership)
