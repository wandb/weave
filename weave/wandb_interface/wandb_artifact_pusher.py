import dataclasses
import typing
import wandb
from wandb import Artifact

from weave import wandb_client_api
from weave.wandb_interface.wandb_lite_run import InMemoryLazyLiteRun
from .. import engine_trace


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
    tracer = engine_trace.tracer()  # type: ignore
    # Here we get the default entity if none is provided.
    # When we support saving dashboards to target entities,
    # we may want to rework this code path so that the caller
    # must provide an entity name.
    entity_name = entity_name or wandb_client_api.wandb_public_api().default_entity

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
