import typing

from . import artifacts_local
from .ops_domain import file_wbartifact

from . import uris

# This function takes a dictionary entry in a run summary and conditionally transforms it
# into the appropriate ArtifactVersionFile object. Most of the W&B specific logic should be incorporated
# into the W&B client directly, but this is a good place to start.
def wb_client_dict_to_artifact_version_file(
    val: dict,
) -> typing.Optional[file_wbartifact.ArtifactVersionFile]:
    avf: typing.Optional[file_wbartifact.ArtifactVersionFile] = None
    if "artifact_path" in val:
        artifact_path = val["artifact_path"]
        if "://" in artifact_path:
            scheme, uri = artifact_path.split("://", 1)
            art_identifier, file_path = uri.split("/", 1)
            ref = uris.WeaveURI.parse(val["artifact_path"])
            art = artifacts_local.WandbClientArtifact(ref)  # type: ignore
            avf = file_wbartifact.ArtifactVersionFile(art, file_path)  # type: ignore

    return avf
