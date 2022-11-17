import typing
from wandb.apis import public as wandb_api

from . import wandb_sdk_weave_0_types

from ..wandb_api import wandb_public_api


def _query(query_str, variables={}):
    return wandb_public_api().client.execute(
        wandb_api.gql(query_str),
        variable_values=variables,
    )


def artifact_collection_is_portfolio(
    artifact_collection: wandb_api.ArtifactCollection,
) -> bool:
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


def entity_portfolios(
    entity: wandb_sdk_weave_0_types.Entity,
) -> list[wandb_api.ArtifactCollection]:
    # TODO: WANDB SDK needs to support portfolios, not just sequences (well, actually we just need to write our own class layer)
    return []
    # The below query is what we will want in the long run:
    # res = _query(
    #     """
    #     query EntityPortfolios(
    #         $entityName: String!,
    #     ) {
    #         entity(name: $entityName) {
    #             id
    #             artifactCollections(collectionTypes: [PORTFOLIO]) {
    #                 edges {
    #                     node {
    #                         id
    #                         name
    #                         defaultArtifactType {
    #                             id
    #                             name
    #                         }
    #                         project {
    #                             id
    #                             name
    #                             entity {
    #                                 id
    #                                 name
    #                             }
    #                         }
    #                     }
    #                 }
    #             }
    #         }
    #     }
    #     """,
    #     {"entityName": entity._name},
    # )

    # portNodes = res["entity"]["artifactCollections"]["edges"]

    # return [
    #     wandb_api.ArtifactCollection(
    #         wandb_public_api().client,
    #         portNode["node"]["project"]["entity"]["name"],
    #         portNode["node"]["project"]["name"],
    #         portNode["node"]["name"],
    #         portNode["node"]["defaultArtifactType"]["name"],
    #     )
    #     for portNode in portNodes
    # ]


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
        ) {	
            artifactCollection(id: $id) {	
                id	
                aliases {
                    edges {
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
                    defaultArtifactType {
                        id
                        name
                    }
                    artifactMembership(aliasName: $digest) {
                        id
                        artifact {
                            aliases {
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
            "artifactCollectionName": artifact_version._artifact_name.split(":")[0],
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
                artifact_version._artifact_name.split(":")[0],
                res["project"]["artifactCollection"]["defaultArtifactType"]["name"],
            ),
        )
        for alias in res["project"]["artifactCollection"]["artifactMembership"][
            "artifact"
        ]["aliases"]
    ]


def artifact_version_created_by(
    artifact_version: wandb_api.Artifact,
) -> typing.Optional[wandb_api.Run]:
    res = _query(
        """	
        query ArtifactVersionCreatedBy(	
            $entityName: String!,	
            $projectName: String!,	
            $artifactCollectionName: String!,	
            $digest: String!,
        ) {	
            project(name: $projectName, entityName: $entityName) {
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    artifactMembership(aliasName: $digest) {
                        id
                        artifact {
                            id
                            createdBy {
                                ... on Run {
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
                                }
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
            "artifactCollectionName": artifact_version._artifact_name.split(":")[0],
            "digest": artifact_version.digest,
        },
    )
    entity_name = res["project"]["artifactCollection"]["artifactMembership"][
        "artifact"
    ]["createdBy"]["project"]["entity"]["name"]
    project_name = res["project"]["artifactCollection"]["artifactMembership"][
        "artifact"
    ]["createdBy"]["project"]["name"]
    run_name = res["project"]["artifactCollection"]["artifactMembership"]["artifact"][
        "createdBy"
    ]["name"]
    if (
        res["project"]["artifactCollection"]["artifactMembership"]["artifact"][
            "createdBy"
        ]
        == "Run"
    ):
        return wandb_public_api().run(f"{entity_name}/{project_name}/{run_name}")
    return None


def artifact_version_created_by_user(
    artifact_version: wandb_api.Artifact,
) -> typing.Optional[wandb_sdk_weave_0_types.User]:
    res = _query(
        """	
        query ArtifactVersionCreatedBy(	
            $entityName: String!,	
            $projectName: String!,	
            $artifactCollectionName: String!,	
            $digest: String!,
        ) {	
            project(name: $projectName, entityName: $entityName) {
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    artifactMembership(aliasName: $digest) {
                        id
                        artifact {
                            id
                            createdBy {
                                __typename
                                ... on User {
                                    id
                                    name
                                }
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
            "artifactCollectionName": artifact_version._artifact_name.split(":")[0],
            "digest": artifact_version.digest,
        },
    )
    if (
        res["project"]["artifactCollection"]["artifactMembership"]["artifact"][
            "createdBy"
        ]
        == "User"
    ):
        return wandb_sdk_weave_0_types.User(
            username=res["project"]["artifactCollection"]["artifactMembership"][
                "artifact"
            ]["createdBy"]["name"]
        )
    return None


def artifact_version_artifact_collections(
    artifact_version: wandb_api.Artifact,
) -> list[wandb_api.ArtifactCollection]:
    res = _query(
        """	
        query ArtifactVersionCreatedBy(	
            $entityName: String!,	
            $projectName: String!,	
            $artifactCollectionName: String!,	
            $digest: String!,
        ) {	
            project(name: $projectName, entityName: $entityName) {
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    artifactMembership(aliasName: $digest) {
                        id
                        artifact {
                            artifactMemberships {
                                edges {
                                    node {
                                        id
                                        artifactCollection {
                                            id
                                            name
                                            defaultArtifactType {
                                                id
                                                name
                                            }
                                            project {
                                                id
                                                name 
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
            }
        }
        """,
        {
            "entityName": artifact_version.entity,
            "projectName": artifact_version.project,
            "artifactCollectionName": artifact_version._artifact_name.split(":")[0],
            "digest": artifact_version.digest,
        },
    )

    membershipEdges = res["project"]["artifactCollection"]["artifactMembership"][
        "artifact"
    ]["artifactMemberships"]["edges"]

    return [
        wandb_api.ArtifactCollection(
            wandb_public_api().client,
            memEdge["node"]["artifactCollection"]["project"]["entity"]["name"],
            memEdge["node"]["artifactCollection"]["project"]["name"],
            memEdge["node"]["artifactCollection"]["name"],
            memEdge["node"]["artifactCollection"]["defaultArtifactType"]["name"],
        )
        for memEdge in membershipEdges
    ]


def artifact_version_memberships(
    artifact_version: wandb_api.Artifact,
) -> list[wandb_api.ArtifactCollection]:
    res = _query(
        """	
        query ArtifactVersionCreatedBy(	
            $entityName: String!,	
            $projectName: String!,	
            $artifactCollectionName: String!,	
            $digest: String!,
        ) {	
            project(name: $projectName, entityName: $entityName) {
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    artifactMembership(aliasName: $digest) {
                        id
                        artifact {
                            artifactMemberships {
                                edges {
                                    node {
                                        id
                                        versionIndex
                                        commitHash
                                        artifactCollection {
                                            id
                                            name
                                            defaultArtifactType {
                                                id
                                                name
                                            }
                                            project {
                                                id
                                                name 
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
            }
        }
        """,
        {
            "entityName": artifact_version.entity,
            "projectName": artifact_version.project,
            "artifactCollectionName": artifact_version._artifact_name.split(":")[0],
            "digest": artifact_version.digest,
        },
    )

    membershipEdges = res["project"]["artifactCollection"]["artifactMembership"][
        "artifact"
    ]["artifactMemberships"]["edges"]
    return [
        wandb_sdk_weave_0_types.ArtifactCollectionMembership(
            wandb_api.ArtifactCollection(
                wandb_public_api().client,
                memEdge["node"]["artifactCollection"]["project"]["entity"]["name"],
                memEdge["node"]["artifactCollection"]["project"]["name"],
                memEdge["node"]["artifactCollection"]["name"],
                memEdge["node"]["artifactCollection"]["defaultArtifactType"]["name"],
            ),
            memEdge["node"]["commitHash"],
            memEdge["node"]["versionIndex"],
        )
        for memEdge in membershipEdges
    ]


def artifact_version_artifact_type(
    artifact_version: wandb_api.Artifact,
) -> wandb_api.ArtifactType:
    return wandb_public_api().artifact_type(
        artifact_version.project, artifact_version.type
    )


def artifact_version_artifact_sequence(
    artifact_version: wandb_api.Artifact,
) -> wandb_api.ArtifactCollection:
    return wandb_api.ArtifactCollection(
        wandb_public_api().client,
        artifact_version.entity,
        artifact_version.project,
        artifact_version._sequence_name,
        artifact_version.type,
    )
