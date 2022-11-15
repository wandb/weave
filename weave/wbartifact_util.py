import typing

from .wandb_api import wandb_public_api

from . import artifacts_local
from .ops_domain import file_wbartifact
from wandb.apis import public as wandb_api

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
            if ":" in art_identifier:
                art_id, art_alias = art_identifier.split(":", 1)
                query = wandb_api.gql(
                    """
                query ArtifactVersion(
                    $id: ID!,
                    $aliasName: String!
                ) {
                    artifactCollection(id: $id) {
                        id
                        name
                        project {
                            id
                            name
                            entity {
                                id
                                name
                            }
                        }
                        artifactMembership(aliasName: $aliasName) {
                            id
                            versionIndex
                        }
                        defaultArtifactType {
                            id
                            name
                        }
                    }
                }
                """
                )
                res = wandb_public_api().client.execute(
                    query,
                    variable_values={
                        "id": art_id,
                        "aliasName": art_alias,
                    },
                )
                entity_name = res["artifactCollection"]["project"]["entity"]["name"]
                project_name = res["artifactCollection"]["project"]["name"]
                artifact_type_name = res["artifactCollection"]["defaultArtifactType"][
                    "name"
                ]
                artifact_name = res["artifactCollection"]["name"]
                version_index = res["artifactCollection"]["artifactMembership"][
                    "versionIndex"
                ]
                version = f"v{version_index}"

                weave_art_uri = uris.WeaveWBArtifactURI.from_parts(
                    entity_name,
                    project_name,
                    artifact_name,
                    version,
                )
                weave_art = artifacts_local.WandbArtifact(
                    artifact_name, artifact_type_name, weave_art_uri
                )
                avf = file_wbartifact.ArtifactVersionFile(weave_art, file_path)  # type: ignore
    return avf
