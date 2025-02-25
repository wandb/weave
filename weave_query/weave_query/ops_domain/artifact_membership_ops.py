import logging
import urllib
import typing

from weave_query import weave_types as types
from weave_query import artifact_fs, artifact_wandb
from weave_query.api import op
from weave_query.gql_op_plugin import wb_gql_op_plugin
from weave_query.ops_domain import wb_domain_types as wdt
from weave_query.ops_domain.wandb_domain_gql import (
    gql_direct_edge_op,
    gql_prop_op,
)

static_art_membership_file_gql = """
            versionIndex
            artifactCollection {
                id 
                name 
                defaultArtifactType {
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
            """


# Section 1/6: Tag Getters
# None

# Section 2/6: Root Ops
# None

# Section 3/6: Attribute Getters
gql_prop_op(
    "artifactMembership-versionIndex",
    wdt.ArtifactCollectionMembershipType,
    "versionIndex",
    types.Int(),
)


gql_prop_op(
    "artifactMembership-createdAt",
    wdt.ArtifactCollectionMembershipType,
    "createdAt",
    types.Timestamp(),
)

gql_prop_op(
    "artifactMembership-commitHash",
    wdt.ArtifactCollectionMembershipType,
    "commitHash",
    types.String(),
)

# Section 4/6: Direct Relationship Ops
gql_direct_edge_op(
    "artifactMembership-collection",
    wdt.ArtifactCollectionMembershipType,
    "artifactCollection",
    wdt.ArtifactCollectionType,
)

gql_direct_edge_op(
    "artifactMembership-artifactVersion",
    wdt.ArtifactCollectionMembershipType,
    "artifact",
    wdt.ArtifactVersionType,
)

gql_direct_edge_op(
    "artifactMembership-aliases",
    wdt.ArtifactCollectionMembershipType,
    "aliases",
    wdt.ArtifactAliasType,
    is_many=True,
)

# Section 5/6: Connection Ops
# None

# Section 6/6: Non Standard Business Logic Ops
# None


@op(
    name="artifactMembership-link",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: static_art_membership_file_gql,
    ),
)
def artifact_membership_link(
    artifactMembership: wdt.ArtifactCollectionMembership,
) -> wdt.Link:
    return wdt.Link(
        name=f"{artifactMembership['artifactCollection']['name']}:v{artifactMembership['versionIndex']}",
        url=f"/{artifactMembership['artifactCollection']['defaultArtifactType']['project']['entity']['name']}/"
        f"{artifactMembership['artifactCollection']['defaultArtifactType']['project']['name']}/"
        f"artifacts/{urllib.parse.quote(artifactMembership['artifactCollection']['defaultArtifactType']['name'])}/"
        f"{urllib.parse.quote(artifactMembership['artifactCollection']['name'])}"
        f"/v{artifactMembership['versionIndex']}",
    )


def _artifact_membership_to_wb_artifact(artifactMembership: wdt.ArtifactCollectionMembership):
    type_name = artifactMembership["artifactCollection"]["defaultArtifactType"]["name"]
    collection_name = artifactMembership["artifactCollection"]["name"]

    # This is valid because the commitHash for portfolios is always null. So we will leverage
    # the artifact's membership in its source collection to fetch it via the commitHash in
    # downstream paths
    version = f"v{artifactMembership['versionIndex']}"
    entity_name = artifactMembership["artifactCollection"]['defaultArtifactType']['project']['entity']['name']
    project_name = artifactMembership["artifactCollection"]['defaultArtifactType']['project']['name']
    uri = artifact_wandb.WeaveWBArtifactURI(
        collection_name, version, entity_name, project_name
    )
    return artifact_wandb.WandbArtifact(
        name=collection_name,
        type=type_name,
        uri=uri,
    )

# Same as the artifactVersion-_file_refine_output_type op
@op(
    name="artifactMembership-_file_refine_output_type",
    hidden=True,
    output_type=types.TypeType(),
    plugins=wb_gql_op_plugin(lambda inputs, inner: static_art_membership_file_gql),
)
def _file_refine_output_type(artifactMembership: wdt.ArtifactCollectionMembership, path: str):
    art_local = _artifact_membership_to_wb_artifact(artifactMembership)
    return types.TypeRegistry.type_of(art_local.path_info(path))


# Same as the artifactVersion-file op
@op(
    name="artifactMembership-file",
    refine_output_type=_file_refine_output_type,
    plugins=wb_gql_op_plugin(lambda inputs, inner: static_art_membership_file_gql),
)
def file_(
        artifactMembership: wdt.ArtifactCollectionMembership, path: str
) -> typing.Union[
    None, artifact_fs.FilesystemArtifactFile  # , artifact_fs.FilesystemArtifactDir
]:
    art_local = _artifact_membership_to_wb_artifact(artifactMembership)
    return art_local.path_info(path)  # type: ignore
