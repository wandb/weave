# TODO: split this into multiple files like we do in the JS version

from ..api import op, weave_class
from .. import weave_types as types
from ..ops_primitives import file


class Project(types.Type):
    name = "project"


class ArtifactVersion(types.Type):
    name = "artifactversion"


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
            os.path.join("local-artifacts", artifactVersion.path, path)
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
