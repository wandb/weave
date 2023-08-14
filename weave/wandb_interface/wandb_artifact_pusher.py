import dataclasses
import typing
import wandb
from wandb import Artifact
from wandb.sdk.artifacts.artifact_saver import ArtifactSaver
from wandb.sdk.internal.sender import _manifest_json_from_proto

# from wandb.sdk.internal.artifact_saver import ArtifactSaver # This symbol moved after our pinned version
# from wandb.sdk.internal.sender import _manifest_json_from_proto # This symbol moved after our pinned version
from wandb.sdk.interface.interface import InterfaceBase

from weave import wandb_client_api
from weave.wandb_interface.wandb_lite_run import InMemoryLazyLiteRun


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
) -> WeaveWBArtifactURIComponents:
    # Extract Artifact Attributes
    artifact_name = artifact.name
    artifact_type_name = artifact.type

    assert artifact_name is not None
    assert artifact_type_name is not None

    wandb_client_api.assert_wandb_authenticated()

    # Here we get the default entity if none is provided.
    # When we support saving dashboards to target entities,
    # we may want to rework this code path so that the caller
    # must provide an entity name.
    entity_name = entity_name or wandb_client_api.wandb_public_api().default_entity

    if _lite_run is None:
        lite_run = InMemoryLazyLiteRun(
            entity_name, project_name, group="weave_artifact_pushers", _hide_in_wb=True
        )
    else:
        lite_run = _lite_run

    # Ensure the artifact type exists
    lite_run.i_api.create_artifact_type(
        artifact_type_name=artifact_type_name,
        entity_name=lite_run.run.entity,
        project_name=lite_run.run.project,
    )

    # Finalize the artifact and construct the manifest.
    artifact.finalize()
    manifest_dict = _manifest_json_from_proto(
        InterfaceBase()._make_artifact(artifact).manifest  # type: ignore[abstract, attr-defined]
    )

    # Save the Artifact and the associated files
    saver = ArtifactSaver(
        api=lite_run.i_api,
        digest=artifact.digest,
        manifest_json=manifest_dict,
        file_pusher=lite_run.pusher,
        is_user_created=False,
    )
    res = saver.save(
        type=artifact_type_name,
        name=artifact_name,
        client_id=artifact._client_id,
        sequence_client_id=artifact._sequence_client_id,
        metadata=artifact.metadata,
        description=artifact.description,
        aliases=["latest"] + additional_aliases,
        use_after_commit=False,
    )

    lite_run.finish()

    if res is not None:
        art = Artifact._from_id(res["id"], wandb_client_api.wandb_public_api().client)
        if art is not None:
            commit_hash = art.commit_hash

    # Return the URI of the artifact
    return WeaveWBArtifactURIComponents(
        entity_name=lite_run.run.entity,
        project_name=lite_run.run.project,
        artifact_name=artifact_name,
        version_str=commit_hash,
    )
