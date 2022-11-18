import json
from ..wandb_api import wandb_public_api
from ..api import op
from . import wb_domain_types
from ..language_features.tagging import make_tag_getter_op
from . import wandb_domain_gql

project_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "project", wb_domain_types.Project.WeaveType(), op_name="tag-project"  # type: ignore
)


@op(name="root-project")
def project(entityName: str, projectName: str) -> wb_domain_types.Project:
    return wb_domain_types.Project(
        _entity=wb_domain_types.Entity(entityName),
        project_name=projectName,
    )


@op(name="project-name")
def name(project: wb_domain_types.Project) -> str:
    return project.project_name


@op(name="project-link")
def link(project: wb_domain_types.Project) -> wb_domain_types.Link:
    return wb_domain_types.Link(
        project.project_name, f"{project._entity.entity_name}/{project.project_name}"
    )


@op(name="project-entity")
def entity(project: wb_domain_types.Project) -> wb_domain_types.Entity:
    return wb_domain_types.Entity(project._entity.entity_name)


@op()
def artifacts(
    project: wb_domain_types.Project,
) -> list[wb_domain_types.ArtifactCollection]:
    # TODO: Create a custom query for this - very expensive to fetch all artifacts
    res: list[wb_domain_types.ArtifactCollection] = []
    for at in project.sdk_obj.artifact_types():
        for col in at.collections():
            if len(res) == 50:
                break
            res.append(wb_domain_types.ArtifactCollection.from_sdk_obj(col))
    return res


@op(name="project-artifactTypes")
def artifact_types(
    project: wb_domain_types.Project,
) -> list[wb_domain_types.ArtifactType]:
    # TODO: Create custom query
    res: list[wb_domain_types.ArtifactType] = []
    for at in project.sdk_obj.artifacts_types():
        if len(res) == 50:
            break
        res.append(wb_domain_types.ArtifactType.from_sdk_obj(at))
    return res


@op(name="project-artifactType")
def artifact_type(
    project: wb_domain_types.Project, artifactType: str
) -> wb_domain_types.ArtifactType:
    return wb_domain_types.ArtifactType(
        _project=project, artifact_type_name=artifactType
    )


@op(name="project-artifactVersion")
def artifact_version(
    project: wb_domain_types.Project, artifactName: str, artifactVersionAlias: str
) -> wb_domain_types.ArtifactVersion:
    artifact_collection = wb_domain_types.ArtifactCollection(
        _project=project,
        artifact_collection_name=artifactName,
    )
    version_index = None
    try:
        version_index = int(artifactVersionAlias.split("v")[0])
    except ValueError:
        version_index = wandb_domain_gql.artifact_collection_membership_for_alias(
            artifact_collection, artifactVersionAlias
        ).version_index

    return wb_domain_types.ArtifactVersion(
        _artifact_sequence=artifact_collection, version_index=version_index
    )


@op(name="project-runs")
def runs(project: wb_domain_types.Project) -> list[wb_domain_types.Run]:
    # TODO: Create custom query
    res: list[wb_domain_types.Run] = []
    for run in wandb_public_api().runs(
        f"{project._entity.entity_name}/{project.project_name}", per_page=50
    ):
        if len(res) == 50:
            break
        res.append(wb_domain_types.Run.from_sdk_obj(run))
    return res


@op(name="project-filteredRuns")
def filtered_runs(
    project: wb_domain_types.Project, filter: str, order: str
) -> list[wb_domain_types.Run]:
    # TODO: Create custom query
    res: list[wb_domain_types.Run] = []
    for run in wandb_public_api().runs(
        f"{project._entity.entity_name}/{project.project_name}",
        filters=json.loads(filter),
        order=order,
        per_page=50,
    ):
        if len(res) == 50:
            break
        res.append(wb_domain_types.Run.from_sdk_obj(run))
    return res


@op(name="project-artifact")
def project_artifact(
    project: wb_domain_types.Project, artifactName: str
) -> wb_domain_types.ArtifactCollection:
    return wb_domain_types.ArtifactCollection(project, artifactName)
