# TODO: split this into multiple files like we do in the JS version

from ..api import op, weave_class
from .. import weave_types as types
from ..ops_primitives import file

from wandb.apis import public as wandb_api
from wandb.sdk.interface import artifacts as wandb_artifacts


class ProjectType(types.Type):
    name = "project"
    instance_classes = wandb_api.Project
    instance_class = wandb_api.Project

    def instance_to_dict(self, obj):
        return {"entity_name": obj.entity, "project_name": obj.name}

    def instance_from_dict(self, d):
        api = wandb_api.Api()
        return api.project(name=d["project_name"], entity=d["entity_name"])


class ArtifactVersionType(types.Type):
    name = "artifactVersion"
    instance_classes = wandb_api.Artifact
    instance_class = wandb_api.Artifact

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_name": obj._sequence_name,
            "artifact_version": obj.version,
        }

    def instance_from_dict(self, d):
        api = wandb_api.Api()
        return api.artifact(
            "%s/%s/%s:%s"
            % (
                d["entity_name"],
                d["project_name"],
                d["artifact_name"],
                d["artifact_version"],
            )
        )


class ArtifactVersionFileType(types.Type):
    name = "artifactversion-path"
    instance_classes = wandb_artifacts.ArtifactEntry

    def instance_to_dict(self, obj):
        art = obj.parent_artifact()
        return {
            "entity_name": art.entity,
            "project_name": art.project,
            "artifact_name": art._sequence_name,
            "artifact_version": art.version,
            "path": obj.name,
        }

    def instance_from_dict(self, d):
        api = wandb_api.Api()
        return api.artifact(
            "%s/%s/%s:%s"
            % (
                d["entity_name"],
                d["project_name"],
                d["artifact_name"],
                d["artifact_version"],
            )
        ).get_path(d["path"])


class RunType(types.BasicType):
    name = "run"


@weave_class(weave_type=ProjectType)
class Project:
    @op(
        name="project-artifactVersion",
        input_type={
            "project": ProjectType(),
            "artifactName": types.String(),
            "artifactVersionAlias": types.String(),
        },
        output_type=ArtifactVersionType(),
    )
    def artifactVersion(project, artifactName, artifactVersionAlias):
        return wandb_api.Api().artifact(
            "%s/%s/%s:%s"
            % (project.entity, project.name, artifactName, artifactVersionAlias)
        )

    @op(
        name="project-runs",
        input_type={
            "project": ProjectType(),
        },
        output_type=types.List(RunType()),
    )
    def runs(project):
        import wandb

        api = wandb.Api()
        runs = api.runs(
            path="%s/%s" % (project.entity, project.name),
        )

        # limit to 10
        # TODO: fix
        res = []
        for i, run in enumerate(runs):
            res.append({"id": run.id, "name": run.name, "summary": run.summary_metrics})
            if i == 10:
                break
        return res

    @op(
        name="project-filtered-runs",
        input_type={
            "project": ProjectType(),
            "filter": types.Any(),
            "order": types.String(),
        },
        output_type=types.List(RunType()),
    )
    def filtered_runs(project, filter, order):
        import wandb

        api = wandb.Api()
        runs = api.runs(
            path="%s/%s" % (project.entity, project.name),
            filters=json.loads(filter),
            order=order,
        )

        # limit to 10
        # TODO: fix
        res = []
        for i, run in enumerate(runs):
            res.append({"id": run.id, "name": run.name, "summary": run.summary_metrics})
            if i == 10:
                break
        return res


@op(
    name="root-project",
    input_type={"entityName": types.String(), "projectName": types.String()},
    output_type=ProjectType(),
)
def project(entityName, projectName):
    return wandb_api.Api().project(name=projectName, entity=entityName)


@weave_class(weave_type=ArtifactVersionType)
class ArtifactVersion:
    @op(
        name="artifactVersion-file",
        input_type={"artifactVersion": ArtifactVersionType(), "path": types.String()},
        output_type=ArtifactVersionFileType(),
    )
    # TODO: This function should probably be called path, but it return Dir or File.
    # ok...
    def file(artifactVersion, path):
        if path == "":
            # print(
            #     "MANIFEST",
            #     artifactVersion.manifest.entries,
            #     flush=True,
            # )
            files = {}
            dirs = {}
            # TODO: fix this code up.
            for path, ent in artifactVersion.manifest.entries.items():
                parts = path.split("/")
                if len(parts) == 1:
                    file_parts = path.split(".")
                    ext = ""
                    if len(file_parts) > 1:
                        ext = file_parts[-1]
                    files[path] = file.LocalFile(path, mtime=1, extension=ext)
            return file.Dir("", 5, dirs, files)
        return artifactVersion.get_path(path)


@weave_class(weave_type=ArtifactVersionFileType)
class ArtifactVersionFile(file.FileOps):
    @op(
        name="artifactVersionPath-contents",
        input_type={"artifactVersionPath": ArtifactVersionFileType()},
        output_type=types.String(),
    )
    def contents(artifactVersionPath):
        local_path = artifactVersionPath.download()
        return open(local_path, encoding="ISO-8859-1").read()


@weave_class(weave_type=types.WBTable)
class WBTableOps(object):
    @op(
        name="table-rows",
        input_type={"table": types.WBTable()},
        output_type=types.Table(),
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
