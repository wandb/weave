import typing

from weave_query import weave_types as types
from weave_query.api import op
from weave_query.gql_op_plugin import wb_gql_op_plugin
from weave_query.ops_domain import wb_domain_types as wdt
from weave_query.ops_domain.wandb_domain_gql import (
    _make_alias,
    gql_connection_op,
    gql_direct_edge_op,
    gql_prop_op,
    gql_root_op,
)
from weave_query.constants import (
    LIMIT_ARTIFACT_COLLECTIONS,
    LIMIT_ARTIFACT_TYPES,
)

# Section 1/6: Tag Getters
# None

# Section 2/6: Root Ops
# None


# Section 3/6: Attribute Getters
# op_artifact_type_name is written in the plain style
# because the attribute is part of the required fragment
@op(name="artifactType-name")
def op_artifact_type_name(artifactType: wdt.ArtifactType) -> str:
    return artifactType["name"]


# Section 4/6: Direct Relationship Ops
# None

# Section 5/6: Connection Ops
gql_connection_op(
    "artifactType-artifacts",
    wdt.ArtifactTypeType,
    "artifactCollections",
    wdt.ArtifactCollectionType,
    {},
    lambda inputs: f"first: {LIMIT_ARTIFACT_TYPES}",
)

# Section 6/6: Non Standard Business Logic Ops
# This is a horrible op due to the double limits - we should remove this.
first_100_collections_alias = _make_alias(f"first: {LIMIT_ARTIFACT_COLLECTIONS}", prefix="artifactCollections")
first_100_artifacts_alias = _make_alias(f"first: {LIMIT_ARTIFACT_TYPES}", prefix="artifacts")


@op(
    name="artifactType-artifactVersions",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
    {first_100_collections_alias}: artifactCollections(first: {LIMIT_ARTIFACT_COLLECTIONS}) {{
        edges {{
            node {{
                {first_100_artifacts_alias}: artifacts(first: {LIMIT_ARTIFACT_TYPES}) {{
                    edges {{
                        node {{
                            {wdt.ArtifactVersion.REQUIRED_FRAGMENT}
                            {inner}
                        }}
                    }}
                }}
            }}
        }}
    }}""",
        gql_op_output_type=lambda inputs, input_type: types.List(
            wdt.ArtifactVersionType.with_keys(
                typing.cast(typing.Any, input_type)
                .keys[first_100_collections_alias]["edges"]
                .object_type["node"][first_100_artifacts_alias]["edges"]
                .object_type["node"]
                .property_types
            )
        ),
    ),
)
def artifact_versions(
    artifactType: wdt.ArtifactType,
) -> list[wdt.ArtifactVersion]:
    res = []
    for artifactCollectionEdge in artifactType[first_100_collections_alias]["edges"]:
        for artifactEdge in artifactCollectionEdge["node"][first_100_artifacts_alias][
            "edges"
        ]:
            res.append(wdt.ArtifactVersion.from_keys(artifactEdge["node"]))
    return res
