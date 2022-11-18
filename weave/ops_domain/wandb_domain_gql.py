import typing
from wandb.apis import public as wandb_api

from ..wandb_api import wandb_public_api
from . import wb_domain_types


def _query(query_str, variables={}):
    return wandb_public_api().client.execute(
        wandb_api.gql(query_str),
        variable_values=variables,
    )


def artifact_collection_is_portfolio(
    artifact_collection: wb_domain_types.ArtifactCollection,
) -> bool:
    res = _query(
        """	
        query artifact_collection_is_portfolio(	
            $projectName: String!,	
            $entityName: String!,
            $artifactCollectionName: String!,	
        ) {	
            project(name: $projectName, entityName: $entityName) {	
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    __typename
                }
            }	
        }	
        """,
        {
            "projectName": artifact_collection._project.project_name,
            "entityName": artifact_collection._project._entity.entity_name,
            "artifactCollectionName": artifact_collection.artifact_collection_name,
        },
    )
    return res["project"]["artifactCollection"]["__typename"] == "ArtifactPortfolio"


def artifact_collection_artifact_type(
    artifact_collection: wb_domain_types.ArtifactCollection,
) -> wb_domain_types.ArtifactType:
    res = _query(
        """	
        query artifact_collection_artifact_type(	
            $projectName: String!,	
            $entityName: String!,
            $artifactCollectionName: String!,	
        ) {	
            project(name: $projectName, entityName: $entityName) {	
                id
                artifactCollection(name: $artifactCollectionName) {	
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
            "projectName": artifact_collection._project.project_name,
            "entityName": artifact_collection._project._entity.entity_name,
            "artifactCollectionName": artifact_collection.artifact_collection_name,
        },
    )
    return wb_domain_types.ArtifactType(
        artifact_collection._project,
        res["project"]["artifactCollection"]["defaultArtifactType"]["name"],
    )


def entity_projects(
    entity: wb_domain_types.Entity,
) -> list[wb_domain_types.Project]:
    res = _query(
        """
        query entity_projects(
            $entityName: String!,
        ) {
            entity(name: $entityName) {
                id
                projects(first: 50) {
                    edges {
                        node {
                            id
                            name
                        }
                    }
                }
            }
        }
        """,
        {"entityName": entity.entity_name},
    )

    projectNodes = res["entity"]["projects"]["edges"]

    return [
        wb_domain_types.Project(entity, projNode["node"]["name"])
        for projNode in projectNodes
    ]


def entity_portfolios(
    entity: wb_domain_types.Entity,
) -> list[wb_domain_types.ArtifactCollection]:
    res = _query(
        """
        query entity_portfolios(
            $entityName: String!,
        ) {
            entity(name: $entityName) {
                id
                artifactCollections(collectionTypes: [PORTFOLIO], first:50) {
                    edges {
                        node {
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
        """,
        {"entityName": entity.entity_name},
    )

    portNodes = res["entity"]["artifactCollections"]["edges"]

    return [
        wb_domain_types.ArtifactCollection(
            wb_domain_types.Project(
                wb_domain_types.Entity(portNode["node"]["project"]["entity"]["name"]),
                portNode["node"]["project"]["name"],
            ),
            portNode["node"]["name"],
        )
        for portNode in portNodes
    ]


def artifact_collection_membership_for_alias(
    artifact_collection: wb_domain_types.ArtifactCollection, identifier: str
) -> wb_domain_types.ArtifactCollectionMembership:
    res = _query(
        """	
        query artifact_collection_membership_for_alias(	
            $projectName: String!,	
            $entityName: String!,
            $artifactCollectionName: String!,	
            $identifier: String!,	
        ) {	
            project(name: $projectName, entityName: $entityName) {	
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    artifactMembership(aliasName: $identifier) {
                        id
                        versionIndex
                    }   
                }
            }	
        }
        """,
        {
            "projectName": artifact_collection._project.project_name,
            "entityName": artifact_collection._project._entity.entity_name,
            "artifactCollectionName": artifact_collection.artifact_collection_name,
            "identifier": identifier,
        },
    )
    return wb_domain_types.ArtifactCollectionMembership(
        artifact_collection,
        res["project"]["artifactCollection"]["artifactMembership"]["versionIndex"],
    )


def artifact_membership_aliases(
    artifact_collection_membership: wb_domain_types.ArtifactCollectionMembership,
) -> list[wb_domain_types.ArtifactAlias]:
    res = _query(
        """	
        query artifact_membership_aliases(	
            $projectName: String!,	
            $entityName: String!,
            $artifactCollectionName: String!,	
            $identifier: String!,	
        ) {	
            project(name: $projectName, entityName: $entityName) {	
                id
                artifactCollection(name: $artifactCollectionName) {	
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
        }
        """,
        {
            "projectName": artifact_collection_membership._artifact_collection._project.project_name,
            "entityName": artifact_collection_membership._artifact_collection._project._entity.entity_name,
            "artifactCollectionName": artifact_collection_membership._artifact_collection.artifact_collection_name,
            "identifier": f"v{artifact_collection_membership.version_index}",
        },
    )
    return [
        wb_domain_types.ArtifactAlias(
            artifact_collection_membership._artifact_collection,
            alias["alias"],
        )
        for alias in res["project"]["artifactCollection"]["artifactMembership"][
            "aliases"
        ]
    ]


def artifact_collection_aliases(
    artifact_collection: wb_domain_types.ArtifactCollection,
) -> list[wb_domain_types.ArtifactAlias]:
    res = _query(
        """	
        query artifact_collection_aliases(	
            $projectName: String!,	
            $entityName: String!,
            $artifactCollectionName: String!,	
        ) {	
            project(name: $projectName, entityName: $entityName) {	
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    aliases(first: 50) {
                        edges {
                            node {
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
            "projectName": artifact_collection._project.project_name,
            "entityName": artifact_collection._project._entity.entity_name,
            "artifactCollectionName": artifact_collection.artifact_collection_name,
        },
    )
    return [
        wb_domain_types.ArtifactAlias(artifact_collection, edge["node"]["alias"])
        for edge in res["project"]["artifactCollection"]["aliases"]["edges"]
    ]


def artifact_version_aliases(
    artifact_version: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.ArtifactAlias]:
    res = _query(
        """	
        query artifact_version_aliases(	
            $entityName: String!,	
            $projectName: String!,	
            $artifactCollectionName: String!,	
            $aliasName: String!,	
        ) {	
            project(name: $projectName, entityName: $entityName) {
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id
                    defaultArtifactType {
                        id
                        name
                    }
                    artifactMembership(aliasName: $aliasName) {
                        id
                        artifact {
                            aliases {
                                id
                                alias
                                artifactCollection {
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
            "entityName": artifact_version._artifact_sequence._project._entity.entity_name,
            "projectName": artifact_version._artifact_sequence._project.project_name,
            "artifactCollectionName": artifact_version._artifact_sequence.artifact_collection_name,
            "aliasName": f"v{artifact_version.version_index}",
        },
    )
    return [
        wb_domain_types.ArtifactAlias(
            wb_domain_types.ArtifactCollection(
                wb_domain_types.Project(
                    wb_domain_types.Entity(
                        alias["artifactCollection"]["project"]["entity"]["name"]
                    ),
                    alias["artifactCollection"]["project"]["name"],
                ),
                alias["artifactCollection"]["name"],
            ),
            alias["alias"],
        )
        for alias in res["project"]["artifactCollection"]["artifactMembership"][
            "artifact"
        ]["aliases"]
    ]


def artifact_version_created_by(
    artifact_version: wb_domain_types.ArtifactVersion,
) -> typing.Optional[wb_domain_types.Run]:
    res = _query(
        """	
        query artifact_version_created_by(	
            $entityName: String!,	
            $projectName: String!,	
            $artifactCollectionName: String!,	
            $aliasName: String!,
        ) {	
            project(name: $projectName, entityName: $entityName) {
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    artifactMembership(aliasName: $aliasName) {
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
            "entityName": artifact_version._artifact_sequence._project._entity.entity_name,
            "projectName": artifact_version._artifact_sequence._project.project_name,
            "artifactCollectionName": artifact_version._artifact_sequence.artifact_collection_name,
            "aliasName": f"v{artifact_version.version_index}",
        },
    )
    entity_name = res["project"]["artifactCollection"]["artifactMembership"][
        "artifact"
    ]["createdBy"]["project"]["entity"]["name"]
    project_name = res["project"]["artifactCollection"]["artifactMembership"][
        "artifact"
    ]["createdBy"]["project"]["name"]
    run_id = res["project"]["artifactCollection"]["artifactMembership"]["artifact"][
        "createdBy"
    ]["name"]
    if (
        res["project"]["artifactCollection"]["artifactMembership"]["artifact"][
            "createdBy"
        ]
        == "Run"
    ):
        return wb_domain_types.Run(
            wb_domain_types.Project(wb_domain_types.Entity(entity_name), project_name),
            run_id,
        )
    return None


def artifact_version_created_by_user(
    artifact_version: wb_domain_types.ArtifactVersion,
) -> typing.Optional[wb_domain_types.User]:
    res = _query(
        """	
        query artifact_version_created_by_user(	
            $entityName: String!,	
            $projectName: String!,	
            $artifactCollectionName: String!,	
            $aliasName: String!,
        ) {	
            project(name: $projectName, entityName: $entityName) {
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    artifactMembership(aliasName: $aliasName) {
                        id
                        artifact {
                            id
                            createdBy {
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
            "entityName": artifact_version._artifact_sequence._project._entity.entity_name,
            "projectName": artifact_version._artifact_sequence._project.project_name,
            "artifactCollectionName": artifact_version._artifact_sequence.artifact_collection_name,
            "aliasName": f"v{artifact_version.version_index}",
        },
    )
    if (
        res["project"]["artifactCollection"]["artifactMembership"]["artifact"][
            "createdBy"
        ]
        == "User"
    ):
        return wb_domain_types.User(
            res["project"]["artifactCollection"]["artifactMembership"]["artifact"][
                "createdBy"
            ]["name"]
        )
    return None


def artifact_version_artifact_collections(
    artifact_version: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.ArtifactCollection]:
    res = _query(
        """	
        query artifact_version_artifact_collections(	
            $entityName: String!,	
            $projectName: String!,	
            $artifactCollectionName: String!,	
            $aliasName: String!,
        ) {	
            project(name: $projectName, entityName: $entityName) {
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    artifactMembership(aliasName: $aliasName) {
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
            "entityName": artifact_version._artifact_sequence._project._entity.entity_name,
            "projectName": artifact_version._artifact_sequence._project.project_name,
            "artifactCollectionName": artifact_version._artifact_sequence.artifact_collection_name,
            "aliasName": f"v{artifact_version.version_index}",
        },
    )

    membershipEdges = res["project"]["artifactCollection"]["artifactMembership"][
        "artifact"
    ]["artifactMemberships"]["edges"]

    return [
        wb_domain_types.ArtifactCollection(
            wb_domain_types.Project(
                wb_domain_types.Entity(
                    memEdge["node"]["artifactCollection"]["project"]["entity"]["name"]
                ),
                memEdge["node"]["artifactCollection"]["project"]["name"],
            ),
            memEdge["node"]["artifactCollection"]["name"],
        )
        for memEdge in membershipEdges
    ]


def artifact_version_memberships(
    artifact_version: wb_domain_types.ArtifactVersion,
) -> list[wb_domain_types.ArtifactCollectionMembership]:
    res = _query(
        """	
        query artifact_version_memberships(	
            $entityName: String!,	
            $projectName: String!,	
            $artifactCollectionName: String!,	
            $aliasName: String!,
        ) {	
            project(name: $projectName, entityName: $entityName) {
                id
                artifactCollection(name: $artifactCollectionName) {	
                    id	
                    artifactMembership(aliasName: $aliasName) {
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
            "entityName": artifact_version._artifact_sequence._project._entity.entity_name,
            "projectName": artifact_version._artifact_sequence._project.project_name,
            "artifactCollectionName": artifact_version._artifact_sequence.artifact_collection_name,
            "aliasName": f"v{artifact_version.version_index}",
        },
    )

    membershipEdges = res["project"]["artifactCollection"]["artifactMembership"][
        "artifact"
    ]["artifactMemberships"]["edges"]
    return [
        wb_domain_types.ArtifactCollectionMembership(
            wb_domain_types.ArtifactCollection(
                wb_domain_types.Project(
                    wb_domain_types.Entity(
                        memEdge["node"]["artifactCollection"]["project"]["entity"][
                            "name"
                        ]
                    ),
                    memEdge["node"]["artifactCollection"]["project"]["name"],
                ),
                memEdge["node"]["artifactCollection"]["name"],
            ),
            memEdge["node"]["versionIndex"],
        )
        for memEdge in membershipEdges
    ]
