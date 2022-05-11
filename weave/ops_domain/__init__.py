# TODO: split this into multiple files like we do in the JS version
import typing

from wandb.apis import public as wandb_api

from ..api import op, weave_class
from .. import weave_types as types
from . import wbartifact


class ProjectType(types.Type):
    name = "project"
    instance_classes = wandb_api.Project
    instance_class = wandb_api.Project

    def instance_to_dict(self, obj):
        return {"entity_name": obj.entity, "project_name": obj.name}

    def instance_from_dict(self, d):
        api = wandb_api.Api()
        return api.project(name=d["project_name"], entity=d["entity_name"])


class RunType(types.Type):
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
        api = wandb_api.Api()
        return api.run("{entity_name}/{project_name}/{run_id}".format(**d))


@weave_class(weave_type=RunType)
class Run:
    @op()
    # @staticmethod  # TODO: doesn't work
    def jobtype(run: wandb_api.Run) -> str:
        return run.jobType


class RunsType(types.Type):
    name = "runs"

    instance_classes = wandb_api.Runs
    instance_class = wandb_api.Runs

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
        }

    def instance_from_dict(self, d):
        api = wandb_api.Api()
        return api.runs("{entity_name}/{project_name}".format(**d))


@weave_class(weave_type=RunsType)
class RunsOps:
    @op()
    def count(self: wandb_api.Runs) -> int:
        return len(self)


class ArtifactTypeType(types.Type):
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
        api = wandb_api.Api()
        return api.artifact_type(
            d["artifact_type_name"], project=f"{d['entity_name']}/{d['project_name']}"
        )


@weave_class(weave_type=ArtifactTypeType)
class ArtifactTypeOps:
    @op(name="artifactType-name")
    def name(artifactType: wandb_api.ArtifactType) -> str:
        return artifactType.type


class ArtifactType(types.Type):
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
        api = wandb_api.Api()
        return api.artifact_type(
            d["artifact_type_name"], project=f"{d['entity_name']}/{d['project_name']}"
        ).collection(d["artifact_name"])


@weave_class(weave_type=ArtifactType)
class ArtifactOps:
    @op()
    def type(artifact: wandb_api.ArtifactCollection) -> wandb_api.ArtifactType:
        api = wandb_api.Api()
        return api.artifact_type(
            artifact.type, project=f"{artifact.entity}/{artifact.project}"
        )


class ArtifactsType(types.Type):
    name = "artifacts"
    instance_classes = wandb_api.ProjectArtifactCollections
    instance_class = wandb_api.ProjectArtifactCollections

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_type_name": obj.type_name,
        }

    def instance_from_dict(self, d):
        api = wandb_api.Api()
        return api.artifact_type(
            d["artifact_type_name"], project=f"{d['entity_name']}/{d['project_name']}"
        ).collections()


@weave_class(weave_type=ArtifactsType)
class ArtifactsOps:
    @op()
    def count(self: wandb_api.ProjectArtifactCollections) -> int:
        return len(self)


@weave_class(weave_type=ProjectType)
class Project:
    @op()
    # @staticmethod  # TODO: doesn't work
    def name(project: wandb_api.Project) -> str:
        print("Project", project)
        return project.name

    @op()
    def artifacts(
        project: wandb_api.Project,
    ) -> typing.List[wandb_api.ArtifactCollection]:
        print("Project", project)
        api = wandb_api.Api()
        return api.artifact_type(
            "test_results", project=f"{project.entity}/{project.name}"
        ).collections()

    @op(name="project-artifactVersion")
    def artifact_version(
        project: wandb_api.Project, artifactName: str, artifactVersionAlias: str
    ) -> wandb_api.Artifact:
        return wandb_api.Api().artifact(
            "%s/%s/%s:%s"
            % (project.entity, project.name, artifactName, artifactVersionAlias)
        )

    @op()
    def runs(project: wandb_api.Project) -> wandb_api.Runs:
        import wandb

        api = wandb.Api()
        return api.runs(
            path="%s/%s" % (project.entity, project.name),
        )

    @op(name="project-filtered-runs")
    def filtered_runs(
        project: wandb_api.Project, filter: typing.Any, order: str
    ) -> wandb_api.Runs:
        import wandb

        api = wandb.Api()
        return api.runs(
            path="%s/%s" % (project.entity, project.name),
            filters=json.loads(filter),
            order=order,
        )


@op(name="root-project")
def project(entityName: str, projectName: str) -> wandb_api.Project:
    return wandb_api.Api().project(name=projectName, entity=entityName)


@weave_class(weave_type=types.WBTable)
class WBTableOps(object):
    @op(
        name="table-rows",
        input_type={"table": types.WBTable()},
        output_type=types.List(types.TypedDict({})),
    )
    def rows(table):
        rows = []
        for row in table["data"]:
            row_result = {}
            for col_name, val in zip(table["columns"], row):
                row_result[col_name] = val
            rows.append(row_result)
        return rows


from .image import *
