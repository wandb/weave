from wandb.apis import public as wandb_api

from ..wandb_api import wandb_public_api


def _query(query_str, variables={}):
    return wandb_public_api().client.execute(
        wandb_api.gql(query_str),
        variable_values=variables,
    )


def client_art_id_to_version_parts(art_id: str, art_version: str):
    res = _query(
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
        """,
        {
            "id": art_id,
            "aliasName": art_version,
        },
    )
    entity_name = res["artifactCollection"]["project"]["entity"]["name"]
    project_name = res["artifactCollection"]["project"]["name"]
    artifact_type_name = res["artifactCollection"]["defaultArtifactType"]["name"]
    artifact_name = res["artifactCollection"]["name"]
    version_index = res["artifactCollection"]["artifactMembership"]["versionIndex"]
    return {
        "entity_name": entity_name,
        "project_name": project_name,
        "artifact_type_name": artifact_type_name,
        "artifact_name": artifact_name,
        "version_index": version_index,
    }


def artifact_collection_is_portfolio(artifact_collection: wandb_api.ArtifactCollection):
    res = _query(
        """	
        query ArtifactCollectionIsPortfolio(	
            $id: ID!,	
        ) {	
            artifactCollection(id: $id) {	
                id	
                __typename
            }	
        }	
        """,
        {
            "id": artifact_collection.id,
        },
    )
    return res["artifactCollection"]["__typename"] == "ArtifactPortfolio"


def project_artifact(
    project: wandb_api.Project, artifactName: str
) -> wandb_api.ArtifactCollection:
    res = _query(
        """	
        query ProjectArtifact(	
            $projectName: ID!,	
            $entityName: String!,
            $artifactName: String!,	
        ) {	
            project(name: $projectName, entityName: $entityName {	
                id	
                entity {
                    id
                    name
                }
                artifactCollection(name: $artifactName) {	
                    id
                    defaultArtifactType {	
                        id	
                        name	
                    }	
                }	
            }	
        }	
        """,
        {
            "id": project.id,
            "artifactName": artifactName,
        },
    )
    return wandb_api.ArtifactCollection(
        wandb_public_api().client,
        res["project"]["entity"]["name"],
        res["project"]["name"],
        artifactName,
        res["project"]["defaultArtifactType"]["name"],
    )


# def artifact_membership_version_index()
