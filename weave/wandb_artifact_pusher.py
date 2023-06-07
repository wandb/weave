import dataclasses
import datetime
import typing
import wandb
from wandb.sdk.artifacts.artifact_saver import ArtifactSaver
from wandb.sdk.artifacts.public_artifact import Artifact
from wandb.sdk.internal.sender import _manifest_json_from_proto

# from wandb.sdk.internal.artifact_saver import ArtifactSaver # This symbol moved after our pinned version
# from wandb.sdk.internal.sender import _manifest_json_from_proto # This symbol moved after our pinned version
from wandb.sdk.internal.file_pusher import FilePusher
from wandb.sdk.internal.file_stream import FileStreamApi
from wandb.sdk.interface.interface import InterfaceBase
from wandb.sdk.internal.internal_api import Api as InternalApi

from weave.wandb_client_api import wandb_public_api


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
) -> WeaveWBArtifactURIComponents:
    # Get handles to the public and internal APIs
    p_api = wandb_public_api()
    entity_name = entity_name or p_api.default_entity
    i_api = InternalApi({"project": project_name, "entity": entity_name})

    # Extract Artifact Attributes
    artifact_name = artifact.name
    artifact_type_name = artifact.type

    assert entity_name is not None
    assert project_name is not None
    assert artifact_name is not None
    assert artifact_type_name is not None

    # Ensure project exists
    p_api.create_project(name=project_name, entity=entity_name)

    # Ensure the artifact type exists
    i_api.create_artifact_type(
        artifact_type_name=artifact_type_name,
        entity_name=entity_name,
        project_name=project_name,
    )

    # Produce a run to log the artifact to
    new_run = p_api.create_run(project=project_name, entity=entity_name)  # type: ignore[no-untyped-call]
    i_api.set_current_run_id(new_run.id)

    # Setup the FileStream and FilePusher
    stream = FileStreamApi(i_api, new_run.id, datetime.datetime.utcnow().timestamp())
    stream.start()
    pusher = FilePusher(i_api, stream)

    # Finalize the artifact and construct the manifest.
    artifact.finalize()
    manifest_dict = _manifest_json_from_proto(
        InterfaceBase()._make_artifact(artifact).manifest  # type: ignore[abstract, attr-defined]
    )

    # Save the Artifact and the associated files
    saver = ArtifactSaver(
        api=i_api,
        digest=artifact.digest,
        manifest_json=manifest_dict,
        file_pusher=pusher,
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

    # Mark the run as complete
    stream.finish(0)

    # Wait for the FilePusher and FileStream to finish
    pusher.finish()
    pusher.join()

    if res is not None:
        commit_hash = Artifact.from_id(res["id"], p_api.client).commit_hash

    # Return the URI of the artifact
    return WeaveWBArtifactURIComponents(
        entity_name=entity_name,
        project_name=project_name,
        artifact_name=artifact_name,
        version_str=commit_hash,
    )
