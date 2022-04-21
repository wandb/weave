# TODO: split this into multiple files like we do in the JS version

from ..api import op, weave_class
from .. import weave_types as types
from ..ops_primitives import file
from ..artifacts_local import LOCAL_ARTIFACT_DIR


class Project(types.Type):
    name = "project"


class ArtifactVersion(types.Type):
    name = "artifactversion"


class RunType(types.BasicType):
    name = "run"


@weave_class(weave_type=Project)
class ProjectOps(object):
    @op(
        name="project-artifactVersion",
        input_type={
            "project": Project(),
            "artifactName": types.String(),
            "artifactVersionAlias": types.String(),
        },
        output_type=ArtifactVersion(),
    )
    def artifactVersion(project, artifactName, artifactVersionAlias):
        import wandb

        api = wandb.Api()
        return api.artifact(
            "%s/%s/%s:%s"
            % (project.entity, project.name, artifactName, artifactVersionAlias)
        )

    @op(
        name="project-runs",
        input_type={
            "project": Project(),
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
            "project": Project(),
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
    output_type=Project(),
)
def project(entityName, projectName):
    import wandb

    api = wandb.Api()
    return api.project(name=projectName, entity=entityName)


@weave_class(weave_type=ArtifactVersion)
class ArtifactVersionOps(object):
    @op(
        name="artifactVersion-file",
        input_type={"artifactVersion": ArtifactVersion(), "path": types.String()},
        output_type=types.FileType(),
    )
    def file(artifactVersion, path):
        local_path = os.path.abspath(
            os.path.join(LOCAL_ARTIFACT_DIR, artifactVersion.path, path)
        )
        return file.LocalFile(local_path)


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
