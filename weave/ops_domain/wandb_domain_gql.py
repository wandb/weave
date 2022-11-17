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


def artifact_membership_aliases(
    artifact_collection_membership: wandb_sdk_weave_0_types.ArtifactCollectionMembership,
) -> list[wandb_sdk_weave_0_types.ArtifactAlias]:
    res = _query(
        """	
        query ArtifactCollectionMembershipAliases(	
            $id: ID!,	
            $identifier: String!,	
        ) {	
            artifactCollection(id: $id) {	
                id	
                artifactMembership(aliasName: $identifier) {
                    id
                    aliases {
                        id
                        alias
                    }
                }   
            }	
        }
        """,
        {
            "id": artifact_collection_membership.artifact_collection.id,
            "identifier": artifact_collection_membership.commit_hash,
        },
    )
    return [
        wandb_sdk_weave_0_types.ArtifactAlias(
            alias["alias"], artifact_collection_membership.artifact_collection
        )
        for alias in res["artifactCollection"]["artifactMembership"]["aliases"]
    ]


def artifact_collection_aliases(
    artifact_collection: wandb_api.ArtifactCollection,
) -> list[wandb_sdk_weave_0_types.ArtifactAlias]:
    res = _query(
        """	
        query ArtifactCollectionAliases(	
            $id: ID!,	
            $identifier: String!,	
        ) {	
            artifactCollection(id: $id) {	
                id	
                aliases {
                    nodes {
                        node {
                            id
                            alias
                        }
                    }
                }   
            }	
        }
        """,
        {
            "id": artifact_collection.id,
        },
    )
    return [
        wandb_sdk_weave_0_types.ArtifactAlias(
            edge["node"]["alias"], artifact_collection
        )
        for edge in res["artifactCollection"]["aliases"]["edges"]
    ]


def artifact_version_aliases(
    artifact_version: wandb_api.Artifact,
) -> list[wandb_sdk_weave_0_types.ArtifactAlias]:
    res = _query(
        """	
        query ArtifactVersionAliases(	
            $entityName: String!,	
            $projectName: String!,	
            $artifactCollectionName: String!,	
            $digest: String!,	
        ) {	
            project(name: $projectName, entityName: $entityName) {
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id
                    membership(aliasName: $digest) {
                        id
                        artifact {
                            alaises {
                                id
                                alias
                            }
                        }
                    }
                }
            }
        }
        """,
        {
            "entityName": artifact_version.entity,
            "projectName": artifact_version.project,
            "artifactCollectionName": artifact_version.name,
            "digest": artifact_version.digest,
        },
    )
    return [
        wandb_sdk_weave_0_types.ArtifactAlias(
            alias["alias"],
            wandb_api.ArtifactCollection(
                wandb_public_api().client,
                artifact_version.entity,
                artifact_version.project,
                artifact_version.name,
            ),
        )
        for alias in res["project"]["artifactCollection"]["membership"]["artifact"][
            "aliases"
        ]
    ]


def artifact_version_created_by(
    artifact_version: wandb_api.Artifact,
) -> wandb_api.Run:
    res = _query(
        """	
        query ArtifactVersionCreatedBy(	
            $id: ID!,	
            $commit_hash: String!,	
        ) {	
            artifactCollection(id: $id) {	
                id	
                artifactMembership(aliasName: $commit_hash) {
                    id
                    artifact {
                        id
                        createdBy {
                            ... on Run {
                                id
                                name
                                project {
                                    id
                                    name {
                                        entity {
                                            id
                                            name
                                        }
                                    }
                                }
                            }
                        }
                    }
                }   
            }	
        }
        """,
        {
            "id": artifact_version.name,
            "commit_hash": artifact_version.commit_hash,
        },
    )
    entity_name = res["artifactCollection"]["artifactMembership"]["artifact"][
        "createdBy"
    ]["project"]["name"]["entity"]["name"]
    project_name = res["artifactCollection"]["artifactMembership"]["artifact"][
        "createdBy"
    ]["project"]["name"]
    run_name = res["artifactCollection"]["artifactMembership"]["artifact"]["createdBy"][
        "name"
    ]
    return wandb_api.Run(f"{entity_name}/{project_name}/{run_name}")
