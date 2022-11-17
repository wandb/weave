from wandb.apis import public as wandb_api

from . import wandb_sdk_weave_0_types

from ..wandb_api import wandb_public_api


def _query(query_str, variables={}):
    return wandb_public_api().client.execute(
        wandb_api.gql(query_str),
        variable_values=variables,
    )


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
            $projectName: String!,	
            $entityName: String!,
            $artifactName: String!,	
        ) {	
            project(name: $projectName, entityName: $entityName) {	
                id
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
            "projectName": project.name,
            "entityName": project.entity,
            "artifactName": artifactName,
        },
    )
    return wandb_api.ArtifactCollection(
        wandb_public_api().client,
        project.entity,
        project.name,
        artifactName,
        res["project"]["artifactCollection"]["defaultArtifactType"]["name"],
    )


def artifact_collection_membership_for_alias(
    artifact_collection: wandb_api.ArtifactCollection, identifier: str
) -> wandb_sdk_weave_0_types.ArtifactCollectionMembership:
    res = _query(
        """	
        query ArtifactCollectionMembershipForAlias(	
            $id: ID!,	
            $identifier: String!,	
        ) {	
            artifactCollection(id: $id) {	
                id	
                artifactMembership(aliasName: $identifier) {
                    id
                    versionIndex
                    commitHash
                }   
            }	
        }
        """,
        {
            "id": artifact_collection.id,
            "identifier": identifier,
        },
    )
    return wandb_sdk_weave_0_types.ArtifactCollectionMembership(
        artifact_collection=artifact_collection,
        commit_hash=res["artifactCollection"]["artifactMembership"]["commitHash"],
        version_index=res["artifactCollection"]["artifactMembership"]["versionIndex"],
    )
