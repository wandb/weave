# TODO: split this into multiple files like we do in the JS version

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
        output_type=wbartifact.ArtifactVersionType(),
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
