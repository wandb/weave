# TODO: split this into multiple files like we do in the JS version
import functools
import json
import typing

from wandb.apis import public as wandb_api

from . import wandb_sdk_weave_0_types
from . import wandb_domain_gql


# Can't import this here, since it relies on panels. It needs
# to go in ecosystem.
# TODO: move this to ecosystem
# from .run_segment import RunSegment, run_segment_render
from ..api import op, weave_class, type as weave_type
from .. import safe_cache
from .. import weave_types as types
from . import wbartifact
from . import file_wbartifact
from .wbmedia import *
from .. import errors
from .. import artifacts_local
from ..wandb_api import wandb_public_api
from ..language_features.tagging import make_tag_getter_op


class OrgType(types._PlainStringNamedType):
    name = "org"


@weave_type("link")
class Link:
    name: str
    url: str


@weave_type("date")
class Date:
    pass


@op(name="user-link")
def user_link(user: wandb_sdk_weave_0_types.User) -> Link:
    return Link(user.username, f"/{user.username}")


@op(name="entity-name")
def entity_name(entity: wandb_sdk_weave_0_types.Entity) -> str:
    return entity._name


@op(name="entity-link")
def entity_link(entity: wandb_sdk_weave_0_types.Entity) -> Link:
    return Link(entity._name, f"/{entity._name}")


class ProjectType(types._PlainStringNamedType):
    name = "project"
    instance_classes = wandb_api.Project
    instance_class = wandb_api.Project

    def instance_to_dict(self, obj):
        return {"entity_name": obj.entity, "project_name": obj.name}

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.project(name=d["project_name"], entity=d["entity_name"])


# This is very helpful when deserializing runs which have been
# serialized. Without caching here, the mappers end up loading
# the run for every tagged cell in the table!
@safe_cache.safe_lru_cache(1000)
def _memoed_get_run(run_uri):
    import time

    print("%s: RUN INSTANCE FROM DICT" % time.time())
    api = wandb_public_api()
    run = api.run(run_uri)
    print("%s: DONE RUN INSTANCE FROM DICT" % time.time())
    return run


class RunType(types._PlainStringNamedType):
    name = "run"

    instance_classes = wandb_api.Run
    instance_class = wandb_api.Run

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj._entity,
            "project_name": obj.project,
            "run_id": obj.id,
        }

    def instance_from_dict(self, d):
        return _memoed_get_run("{entity_name}/{project_name}/{run_id}".format(**d))


class ArtifactVersionsType(types.Type):
    name = "projectArtifactVersions"
    instance_classes = wandb_api.ArtifactVersions
    instance_class = wandb_api.ArtifactVersions

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_type_name": obj.type,
            "artifact_name": obj.collection_name,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.artifact_versions(
            d["artifact_type_name"],
            f"{d['entity_name']}/{d['project_name']}/{d['artifact_name']}",
        )


def process_summary_obj(val):
    if isinstance(val, dict) and "_type" in val and val["_type"] == "table-file":
        return TableClientArtifactFileRef(val["artifact_path"])
    return val


def process_summary_type(val):
    if isinstance(val, dict) and "_type" in val and val["_type"] == "table-file":
        return TableClientArtifactFileRef.WeaveType()
    return types.TypeRegistry.type_of(val)


@op(render_info={"type": "function"})
def refine_summary_type(run: wandb_api.Run) -> types.Type:
    return types.TypedDict(
        {k: process_summary_type(v) for k, v in run.summary._json_dict.items()}
    )


@weave_class(weave_type=RunType)
class WBRun:
    @op()
    def jobtype(run: wandb_api.Run) -> str:
        return run.jobType

    @op()
    def name(run: wandb_api.Run) -> str:
        return run.name

    @op(name="run-link")
    def link(run: wandb_api.Run) -> Link:
        return Link(run.display_name, f"/{run.entity}/{run.project}/runs/{run.name}")

    @op()
    def id(run: wandb_api.Run) -> str:
        return run.id

    @op(refine_output_type=refine_summary_type)
    def summary(run: wandb_api.Run) -> dict[str, typing.Any]:
        return {k: process_summary_obj(v) for k, v in run.summary._json_dict.items()}

    @op(name="run-usedArtifactVersions")
    def used_artifact_versions(run: wandb_api.Run) -> wandb_api.ArtifactVersions:
        return run.used_artifacts()


@dataclasses.dataclass(frozen=True)
class RunsType(types.Type):
    name = "runs"

    instance_classes = wandb_api.Runs
    instance_class = wandb_api.Runs

    object_type: types.Type = RunType()

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.runs("{entity_name}/{project_name}".format(**d), per_page=500)

    @classmethod
    def from_dict(cls, d):
        return cls()


@weave_class(weave_type=RunsType)
class RunsOps:
    @op()
    def count(self: wandb_api.Runs) -> int:
        return len(self)

    @op(
        output_type=types.List(RunType()),
    )
    def limit(self: wandb_api.Runs, limit: int):
        runs: list[wandb_api.Run] = []
        for run in self:
            if len(runs) >= limit:
                break
            runs.append(run)

        return runs


@weave_class(weave_type=wandb_sdk_weave_0_types.ArtifactsType)
class ArtifactsOps:
    @op()
    def count(self: wandb_api.ProjectArtifactCollections) -> int:
        return len(self)

    @op()
    def __getitem__(
        self: wandb_api.ProjectArtifactCollections, index: int
    ) -> wandb_api.ArtifactCollection:
        return self[index]


@weave_class(weave_type=ArtifactVersionsType)
class ArtifactVersionsOps:
    @op()
    def count(self: wandb_api.ArtifactVersions) -> int:
        return len(self)

    @op()
    def __getitem__(
        self: wandb_api.ArtifactVersions, index: int
    ) -> artifacts_local.WandbArtifact:
        wb_artifact = self[index]
        return artifacts_local.WandbArtifact.from_wb_artifact(wb_artifact)


class ArtifactTypeType(types._PlainStringNamedType):
    name = "artifactType"
    instance_classes = wandb_api.ArtifactType
    instance_class = wandb_api.ArtifactType

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_type_name": obj.type,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.artifact_type(
            d["artifact_type_name"], project=f"{d['entity_name']}/{d['project_name']}"
        )


@weave_class(weave_type=ArtifactTypeType)
class ArtifactTypeOps:
    @op(name="artifactType-name")
    def name(artifactType: wandb_api.ArtifactType) -> str:
        return artifactType.type

    @op(name="artifactType-artifacts")
    def artifacts(
        artifactType: wandb_api.ArtifactType,
    ) -> wandb_api.ProjectArtifactCollections:
        return artifactType.collections()


class ProjectArtifactTypesType(types.Type):
    name = "projectArtifactTypes"

    instance_classes = wandb_api.ProjectArtifactTypes
    instance_class = wandb_api.ProjectArtifactTypes

    @property
    def object_type(self):
        return RunType()

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.project("{entity_name}/{project_name}".format(**d)).artifacts_types()


@weave_class(weave_type=wandb_sdk_weave_0_types.ArtifactCollectionType)
class ArtifactOps:
    @op(name="artifact-type")
    def type_(artifact: wandb_api.ArtifactCollection) -> wandb_api.ArtifactType:
        api = wandb_public_api()
        return api.artifact_type(
            artifact.type, project=f"{artifact.entity}/{artifact.project}"
        )

    @op(name="artifact-name")
    def name_(artifact: wandb_api.ArtifactCollection) -> str:
        return artifact.name

    @op(name="artifact-description")
    def description(artifact: wandb_api.ArtifactCollection) -> str:
        return artifact._attrs.get("description", "")

    @op(name="artifact-versions")
    def versions(artifact: wandb_api.ArtifactCollection) -> wandb_api.ArtifactVersions:
        return artifact.versions()

    @op(name="artifact-createdAt")
    def createdAt(artifact: wandb_api.ArtifactCollection) -> Date:
        return artifact._attrs.get("createdAt", None)

    @op(name="artifact-id")
    def id(artifact: wandb_api.ArtifactCollection) -> str:
        return artifact.id

    @op(name="artifact-isPortfolio")
    def is_portfolio(artifact: wandb_api.ArtifactCollection) -> bool:
        return wandb_domain_gql.artifact_collection_is_portfolio(artifact)


@weave_class(weave_type=ProjectType)
class Project:
    @op()
    def name(project: wandb_api.Project) -> str:
        return project.name

    @op(name="project-link")
    def link(self) -> Link:
        return Link(self.name, f"{self.entity}/{self.name}")

    @op(name="project-entity")
    def entity(project: wandb_api.Project) -> wandb_sdk_weave_0_types.Entity:
        return wandb_sdk_weave_0_types.Entity(project.entity)

    @op()
    def artifacts(
        project: wandb_api.Project,
    ) -> typing.List[wandb_api.ArtifactCollection]:
        api = wandb_public_api()
        return [
            col
            for at in api.artifact_types(project=f"{project.entity}/{project.name}")
            for col in at.collections()
        ]

    @op(name="project-artifactTypes")
    def artifact_types(project: wandb_api.Project) -> wandb_api.ProjectArtifactTypes:
        return project.artifacts_types()

    @op(name="project-artifactType")
    def artifact_type(
        project: wandb_api.Project, artifactType: str
    ) -> wandb_api.ArtifactType:
        api = wandb_public_api()
        return api.artifact_type(
            artifactType, project=f"{project.entity}/{project.name}"
        )

    @op(name="project-artifactVersion")
    def artifact_version(
        project: wandb_api.Project, artifactName: str, artifactVersionAlias: str
    ) -> artifacts_local.WandbArtifact:
        wb_artifact = wandb_public_api().artifact(
            "%s/%s/%s:%s"
            % (project.entity, project.name, artifactName, artifactVersionAlias)
        )
        return artifacts_local.WandbArtifact.from_wb_artifact(wb_artifact)

    @op()
    def runs(project: wandb_api.Project) -> wandb_api.Runs:
        api = wandb_public_api()
        return api.runs(path="%s/%s" % (project.entity, project.name), per_page=500)

    @op(name="project-filteredRuns")
    def filtered_runs(
        project: wandb_api.Project, filter: str, order: str
    ) -> wandb_api.Runs:
        import wandb

        api = wandb_public_api()
        return api.runs(
            path="%s/%s" % (project.entity, project.name),  # type: ignore
            filters=json.loads(filter),
            order=order,
            per_page=500,
        )


@op(name="root-project")
def project(entityName: str, projectName: str) -> wandb_api.Project:
    return wandb_public_api().project(name=projectName, entity=entityName)


@op(name="root-entity")
def entity(entityName: str) -> wandb_sdk_weave_0_types.Entity:
    return wandb_sdk_weave_0_types.Entity(entityName)


project_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "project", ProjectType(), op_name="tag-project"
)

run_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "run", RunType(), op_name="tag-run"
)


@op(name="artifactAlias-alias")
def alias(artifactAlias: wandb_sdk_weave_0_types.ArtifactAlias) -> str:
    return artifactAlias._alias


@op(name="artifactAlias-artifact")
def artifact(
    artifactAlias: wandb_sdk_weave_0_types.ArtifactAlias,
) -> wandb_api.ArtifactCollection:
    return artifactAlias.artifact_collection


@op(name="project-artifact")
def project_artifact(
    project: wandb_api.Project, artifactName: str
) -> wandb_api.ArtifactCollection:
    return wandb_domain_gql.project_artifact(project, artifactName)


@op(name="artifactMembership-versionIndex")
def artifact_membership_version_index(
    artifactMembership: wandb_sdk_weave_0_types.ArtifactCollectionMembership,
) -> int:
    return artifactMembership.version_index


@op(name="artifactMembership-aliases")
def artifact_membership_aliases(
    artifactMembership: wandb_sdk_weave_0_types.ArtifactCollectionMembership,
) -> list[wandb_sdk_weave_0_types.ArtifactAlias]:
    return wandb_domain_gql.artifact_membership_aliases(artifactMembership)


@op(name="artifactMembership-collection")
def artifact_membership_collection(
    artifactMembership: wandb_sdk_weave_0_types.ArtifactCollectionMembership,
) -> wandb_api.ArtifactCollection:
    return artifactMembership.artifact_collection


@op(name="artifact-memberships")
def artifact_memberships(
    artifact: wandb_api.ArtifactCollection,
) -> list[wandb_sdk_weave_0_types.ArtifactCollectionMembership]:
    return [
        wandb_domain_gql.artifact_collection_membership_for_alias(artifact, v.digest)
        for v in artifact.versions()
    ]


@op(name="artifact-membershipForAlias")
def artifact_membership_for_alias(
    artifact: wandb_api.ArtifactCollection, aliasName: str
) -> wandb_sdk_weave_0_types.ArtifactCollectionMembership:
    return wandb_domain_gql.artifact_collection_membership_for_alias(
        artifact, aliasName
    )


@op(name="artifact-lastMembership")
def artifact_last_membership(
    artifact: wandb_api.ArtifactCollection,
) -> wandb_sdk_weave_0_types.ArtifactCollectionMembership:
    return wandb_domain_gql.artifact_collection_membership_for_alias(artifact, "latest")


@op(name="artifactMembership-artifactVersion")
def artifact_membership_version(
    artifactMembership: wandb_sdk_weave_0_types.ArtifactCollectionMembership,
) -> artifacts_local.WandbArtifact:
    wb_artifact = wandb_public_api().artifact(
        "%s/%s/%s:%s"
        % (
            artifactMembership.artifact_collection.entity,
            artifactMembership.artifact_collection.project,
            artifactMembership.artifact_collection.name,
            artifactMembership.commit_hash,
        )
    )
    return artifacts_local.WandbArtifact.from_wb_artifact(wb_artifact)


@op(name="artifactVersion-createdBy")
def artifact_version_created_by(
    artifactVersion: artifacts_local.WandbArtifact,
) -> typing.Optional[wandb_api.Run]:
    return wandb_domain_gql.artifact_version_created_by(artifactVersion._saved_artifact)


@op(name="artifactVersion-isWeaveObject")
def artifact_version_is_weave_object(
    artifactVersion: artifacts_local.WandbArtifact,
) -> bool:
    # TODO: this needs a query.
    return False


@op(name="artifact-aliases")
def artifact_aliases(
    artifact: wandb_api.ArtifactCollection,
) -> list[wandb_sdk_weave_0_types.ArtifactAlias]:
    return wandb_domain_gql.artifact_collection_aliases(artifact)


@op(name="artifactVersion-aliases")
def artifact_version_aliases(
    artifactVersion: artifacts_local.WandbArtifact,
) -> list[wandb_sdk_weave_0_types.ArtifactAlias]:
    return wandb_domain_gql.artifact_version_aliases(artifactVersion._saved_artifact)


@op(name="artifactVersion-artifactCollections")
def artifact_version_artifact_collections(
    artifactVersion: artifacts_local.WandbArtifact,
) -> list[wandb_api.ArtifactCollection]:
    return wandb_domain_gql.artifact_version_artifact_collections(
        artifactVersion._saved_artifact
    )


@op(name="artifactVersion-memberships")
def artifact_version_memberships(
    artifactVersion: artifacts_local.WandbArtifact,
) -> list[wandb_sdk_weave_0_types.ArtifactCollectionMembership]:
    return wandb_domain_gql.artifact_version_memberships(
        artifactVersion._saved_artifact
    )


@op(name="artifactVersion-createdByUser")
def artifact_version_created_by_user(
    artifactVersion: artifacts_local.WandbArtifact,
) -> typing.Optional[wandb_sdk_weave_0_types.User]:
    return wandb_domain_gql.artifact_version_created_by_user(
        artifactVersion._saved_artifact
    )


@op(name="artifactVersion-artifactType")
def artifact_version_artifact_type(
    artifactVersion: artifacts_local.WandbArtifact,
) -> wandb_api.ArtifactType:
    return wandb_domain_gql.artifact_version_artifact_type(artifactVersion)


@op(name="artifactVersion-artifactSequence")
def artifact_version_artifact_sequence(
    artifactVersion: artifacts_local.WandbArtifact,
) -> wandb_api.ArtifactCollection:
    return wandb_domain_gql.artifact_version_artifact_sequence(artifactVersion)


@op(name="artifactVersion-usedBy")
def artifact_version_used_by(
    artifactVersion: artifacts_local.WandbArtifact,
) -> list[wandb_api.Run]:
    return artifactVersion._saved_artifact.used_by()


@op(name="entity-portfolios")
def entity_portfolios(
    entity: wandb_sdk_weave_0_types.Entity,
) -> list[wandb_api.ArtifactCollection]:
    return wandb_domain_gql.entity_portfolios(entity)


@op(name="artifact-project")
def artifact_project(artifact: wandb_api.ArtifactCollection) -> wandb_api.Project:
    return wandb_public_api().project(artifact.project, artifact.entity)


@op(name="none-coalesce")
def none_coalesce(a: typing.Any, b: typing.Any) -> typing.Any:
    # TODO: This logic is really complicated in Weavae0.
    return a or b
