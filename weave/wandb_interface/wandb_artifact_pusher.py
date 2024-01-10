import dataclasses
import typing
import wandb
from wandb import Artifact

from weave import wandb_client_api
from weave.wandb_interface.wandb_lite_run import InMemoryLazyLiteRun
from .. import engine_trace
from wandb.apis.public import api as wb_public


def artifact_commithash_by_digest(
    entity_name: str, project_name: str, artifact_name: str, digest: str
) -> typing.Optional[str]:
    query = wb_public.gql(
        """
    query ArtifactVersionFromDigest(
        $entityName: String!,
        $projectName: String!,
        $artName: String!,
        $digest: String!,
    ) {
        project(name: $projectName, entityName: $entityName) {
            artifactCollection(name: $artName) {
                artifactMembership(aliasName: $digest) {
                    commitHash
                    artifact {
                        id
                    }
                }
            }
        }
    }
    """
    )
    res = wandb_client_api.wandb_public_api().client.execute(
        query,
        # variable_values={"id": hex_to_b64_id(server_id)},
        variable_values={
            "entityName": entity_name,
            "projectName": project_name,
            "artName": artifact_name,
            "digest": digest,
        },
    )
    project = res.get("project")
    if project is None:
        return None
    artifact_collection = project.get("artifactCollection")
    if artifact_collection is None:
        return None
    artifact_membership = artifact_collection.get("artifactMembership")
    if artifact_membership is None:
        return None
    return artifact_membership.get("commitHash")


@dataclasses.dataclass
class WeaveWBArtifactURIComponents:
    entity_name: str
    project_name: str
    artifact_name: str
    version_str: str


def write_artifact_to_wandb(
    artifact: wandb.Artifact,
    project_name: str,
    entity_name: typing.Optional[str] = None,
    additional_aliases: list = [],
    *,
    _lite_run: typing.Optional[InMemoryLazyLiteRun] = None,
    artifact_collection_exists: bool = False,
) -> WeaveWBArtifactURIComponents:
    artifact_name = artifact.name

    tracer = engine_trace.tracer()  # type: ignore
    # Here we get the default entity if none is provided.
    # When we support saving dashboards to target entities,
    # we may want to rework this code path so that the caller
    # must provide an entity name.
    entity_name = entity_name or wandb_client_api.wandb_public_api().default_entity

    if entity_name is None:
        raise ValueError("entity_name must be provided")

    # Finalize the artifact, and return early if the digest already exists on the
    # server.
    artifact.finalize()
    existing_commit_hash = artifact_commithash_by_digest(
        entity_name=entity_name,
        project_name=project_name,
        artifact_name=artifact_name,
        digest=artifact.digest,
    )
    if existing_commit_hash is not None:
        return WeaveWBArtifactURIComponents(
            entity_name=entity_name,
            project_name=project_name,
            artifact_name=artifact_name,
            version_str=existing_commit_hash,
        )

    if _lite_run is None:
        lite_run = InMemoryLazyLiteRun(
            entity_name,
            project_name,
            group="weave_artifact_pushers",
            _hide_in_wb=True,
        )
    else:
        lite_run = _lite_run

    with tracer.trace("Logging artifact"):
        res = lite_run.log_artifact(
            artifact,
            additional_aliases,
            artifact_collection_exists,
        )

    with tracer.trace("Finish lite_run"):
        lite_run.finish()

    if res is not None:
        art = Artifact._from_id(res["id"], wandb_client_api.wandb_public_api().client)
        if art is not None:
            commit_hash = art.commit_hash

    # Return the URI of the artifact
    return WeaveWBArtifactURIComponents(
        entity_name=entity_name,
        project_name=project_name,
        artifact_name=artifact.name,
        version_str=commit_hash,
    )
