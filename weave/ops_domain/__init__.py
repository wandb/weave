# TODO: split this into multiple files like we do in the JS version
import functools
import json
import typing

from wandb.apis import public as wandb_api


# Can't import this here, since it relies on panels. It needs
# to go in ecosystem.
# TODO: move this to ecosystem
# from .run_segment import RunSegment, run_segment_render
from ..api import op, weave_class
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


class EntityType(types._PlainStringNamedType):
    name = "entity"


class ArtifactMembershipType(types._PlainStringNamedType):
    name = "artifactMembership"


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
@functools.lru_cache(1000)
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


class ArtifactType(types._PlainStringNamedType):
    name = "artifact"
    instance_classes = wandb_api.ArtifactCollection
    instance_class = wandb_api.ArtifactCollection

    def instance_to_dict(self, obj):
        # TODO: I'm here, trying to serialize/deserialize Artifact
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_type_name": obj.type,
            "artifact_name": obj.name,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.artifact_type(
            d["artifact_type_name"], project=f"{d['entity_name']}/{d['project_name']}"
        ).collection(d["artifact_name"])


class ArtifactVersionsType(types.Type):
    name = "projectArtifactVersions"
    instance_classes = wandb_api.ArtifactVersions
    instance_class = wandb_api.ArtifactVersions

    def instance_to_dict(self, obj):
        # TODO: I'm here, trying to serialize/deserialize Artifact
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
    # @staticmethod  # TODO: doesn't work
    def jobtype(run: wandb_api.Run) -> str:
        return run.jobType

    @op()
    def name(run: wandb_api.Run) -> str:
        return run.name

    @op()
    def id(run: wandb_api.Run) -> str:
        return run.id

    @op(refine_output_type=refine_summary_type)
    def summary(run: wandb_api.Run) -> dict[str, typing.Any]:
        return {k: process_summary_obj(v) for k, v in run.summary._json_dict.items()}


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


class ArtifactsType(types.Type):
    name = "artifacts"
    instance_classes = wandb_api.ProjectArtifactCollections
    instance_class = wandb_api.ProjectArtifactCollections

    @property
    def object_type(self):
        return ArtifactType()

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_type_name": obj.type_name,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.artifact_type(
            d["artifact_type_name"], project=f"{d['entity_name']}/{d['project_name']}"
        ).collections()


@weave_class(weave_type=ArtifactsType)
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
        # TODO: I'm here, trying to serialize/deserialize Artifact
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
        # Hacking to support mapped call here. WeaveJS autosuggest uses it
        # TODO: True mapped call support
        if isinstance(artifactType, wandb_api.ProjectArtifactTypes):
            return [at.name for at in artifactType]  # type: ignore
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


@weave_class(weave_type=ArtifactType)
class ArtifactOps:
    @op(name="artifact-type")
    def type_(artifact: wandb_api.ArtifactCollection) -> wandb_api.ArtifactType:
        api = wandb_public_api()
        return api.artifact_type(
            artifact.type, project=f"{artifact.entity}/{artifact.project}"
        )

    # :( Since we mixin with nodes (include VarNode), name collides.
    # TODO: Fix this is no good.
    @op(name="artifact-name")
    def name_(artifact: wandb_api.ArtifactCollection) -> str:
        return artifact.name

    @op(name="artifact-versions")
    def versions(artifact: wandb_api.ArtifactCollection) -> wandb_api.ArtifactVersions:
        return artifact.versions()


@weave_class(weave_type=ProjectType)
class Project:
    @op()
    # @staticmethod  # TODO: doesn't work
    def name(project: wandb_api.Project) -> str:
        return project.name

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
        import wandb

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


project_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "project", ProjectType(), op_name="tag-project"
)

run_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "run", RunType(), op_name="tag-run"
)


# We don't have proper `wandb` SDK classes for these types so we use object types for now
@weave.type()
class ArtifactCollection:
    project: wandb_api.Project
    artifactName: str


@op(name="project-artifact")
def project_artifact(
    project: wandb_api.Project, artifactName: str
) -> ArtifactCollection:
    return ArtifactCollection(project=project, artifactName=artifactName)


@weave.type()
class ArtifactCollectionMembership:
    artifactCollection: ArtifactCollection
    aliasName: str


@op(name="artifact-membershipForAlias")
def artifact_membership_for_alias(
    artifact: ArtifactCollection, aliasName: str
) -> ArtifactCollectionMembership:
    return ArtifactCollectionMembership(
        artifactCollection=artifact, aliasName=aliasName
    )


@op(name="artifactMembership-artifactVersion")
def artifact_membership_version(
    artifactMembership: ArtifactCollectionMembership,
) -> artifacts_local.WandbArtifact:
    wb_artifact = wandb_public_api().artifact(
        "%s/%s/%s:%s"
        % (
            artifactMembership.artifactCollection.project.entity,
            artifactMembership.artifactCollection.project.name,
            artifactMembership.artifactCollection.artifactName,
            artifactMembership.aliasName,
        )
    )
    return artifacts_local.WandbArtifact.from_wb_artifact(wb_artifact)
