import typing

from . import file_wbartifact
from ..api import op
from . import wb_domain_types
from . import wbartifact
from . import wandb_domain_gql
from .. import weave_types as types
from .. import refs
from .. import artifacts_local


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
    return wandb_domain_gql.artifact_collection_artifact_type(
        artifactVersion._artifact_sequence
    )


@op(name="artifactVersion-artifactSequence")
def artifact_version_artifact_sequence(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> wb_domain_types.ArtifactCollection:
    return artifactVersion._artifact_sequence


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


@op(name="artifactVersion-id")
def id(artifactVersion: wb_domain_types.ArtifactVersion) -> str:
    return artifactVersion.sdk_obj.id


@op(name="artifactVersion-name")
def name(artifactVersion: wb_domain_types.ArtifactVersion) -> str:
    return artifactVersion.sdk_obj.name


@op(name="artifactVersion-digest")
def digest(artifactVersion: wb_domain_types.ArtifactVersion) -> str:
    return artifactVersion.sdk_obj.digest


@op(name="artifactVersion-size")
def size(artifactVersion: wb_domain_types.ArtifactVersion) -> int:
    return artifactVersion.sdk_obj.size


@op(name="artifactVersion-description")
def description(artifactVersion: wb_domain_types.ArtifactVersion) -> str:
    return artifactVersion.sdk_obj.description


@op(name="artifactVersion-createdAt")
def created_at(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> wb_domain_types.Date:
    return artifactVersion.sdk_obj.created_at


@op(name="artifactVersion-files")
def files(
    artifactVersion: wb_domain_types.ArtifactVersion,
) -> list[file_wbartifact.ArtifactVersionFile]:
    # TODO: What is the correct data model here? - def don't want to go download everything
    return []


# Special bridge functions to lower level local artifacts


@op(
    name="artifactVersion-file",
    output_type=refs.ArtifactVersionFileType(),
)
def file_(artifactVersion: wb_domain_types.ArtifactVersion, path: str):
    art_local = artifacts_local.WandbArtifact.from_wb_artifact(artifactVersion.sdk_obj)
    return wbartifact.ArtifactVersion.path.raw_resolve_fn(art_local, path)


# WHY DO I NEED THIS AS WELL?
@op(
    name="artifactVersion-path",
    output_type=refs.ArtifactVersionFileType(),
)
def path(artifactVersion: wb_domain_types.ArtifactVersion, path: str):
    art_local = artifacts_local.WandbArtifact.from_wb_artifact(artifactVersion.sdk_obj)
    return wbartifact.ArtifactVersion.path.raw_resolve_fn(art_local, path)


@op(
    name="artifactVersion-fileReturnType",
    output_type=types.Type(),
)
def path_type(artifactVersion: wb_domain_types.ArtifactVersion, path: str):
    art_local = artifacts_local.WandbArtifact.from_wb_artifact(artifactVersion.sdk_obj)
    return wbartifact.ArtifactVersion.path_type.raw_resolve_fn(art_local, path)
