import typing
from ..api import op
from . import wb_domain_types
from . import wandb_domain_gql


@op(name="artifactVersion-createdBy")
def artifact_version_created_by(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> typing.Optional[wb_domain_types.Run]:
    return wandb_domain_gql.artifact_version_created_by(artifactVersion)


@op(name="artifactVersion-isWeaveObject")
def artifact_version_is_weave_object(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> bool:
    # TODO: this needs a query.
    return False


@op(name="artifactVersion-aliases")
def artifact_version_aliases(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.ArtifactAlias]:
    return wandb_domain_gql.artifact_version_aliases(artifactVersion)


@op(name="artifactVersion-artifactCollections")
def artifact_version_artifact_collections(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.ArtifactCollection]:
    return wandb_domain_gql.artifact_version_artifact_collections(artifactVersion)


@op(name="artifactVersion-memberships")
def artifact_version_memberships(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.ArtifactCollectionMembership]:
    return wandb_domain_gql.artifact_version_memberships(artifactVersion)


@op(name="artifactVersion-createdByUser")
def artifact_version_created_by_user(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> typing.Optional[wb_domain_types.User]:
    return wandb_domain_gql.artifact_version_created_by_user(artifactVersion)


@op(name="artifactVersion-artifactType")
def artifact_version_artifact_type(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> wb_domain_types.ArtifactType:
    return wandb_domain_gql.artifact_version_artifact_type(artifactVersion)


@op(name="artifactVersion-artifactSequence")
def artifact_version_artifact_sequence(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> wb_domain_types.ArtifactCollection:
    return wandb_domain_gql.artifact_version_artifact_sequence(artifactVersion)


@op(name="artifactVersion-usedBy")
def artifact_version_used_by(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.Run]:
    artifactVersion.sdk_obj
    return [
        wb_domain_types.Run(
            _project=wb_domain_types.Project(
                _entity=wb_domain_types.Entity(r.entity),
                project_name=r.project,
            ),
            run_name=r.name,
        )
        for r in artifactVersion.sdk_obj.used_by()
    ]
