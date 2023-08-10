from ..compile_domain import wb_gql_op_plugin
from ..api import op
from .. import weave_types as types
from . import wb_domain_types as wdt
from ..language_features.tagging.make_tag_getter_op import make_tag_getter_op
from .wandb_domain_gql import (
    _make_alias,
    gql_prop_op,
    gql_direct_edge_op,
    gql_connection_op,
    gql_root_op,
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
    return artifactType.gql["name"]


# Section 4/6: Direct Relationship Ops
# None

# Section 5/6: Connection Ops
gql_connection_op(
    "artifactType-artifacts",
    wdt.ArtifactTypeType,
    "artifactCollections",
    wdt.ArtifactCollectionType,
    {},
    lambda inputs: "first: 100",
)

# Section 6/6: Non Standard Business Logic Ops
# This is a horrible op due to the double limits - we should remove this.
first_100_collections_alias = _make_alias("first: 100", prefix="artifactCollections")
first_100_artifacts_alias = _make_alias("first: 100", prefix="artifacts")


@op(
    name="artifactType-artifactVersions",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
    {first_100_collections_alias}: artifactCollections(first: 100) {{
        edges {{
            node {{
                {first_100_artifacts_alias}: artifacts(first: 100) {{
                    edges {{
                        node {{
                            {wdt.ArtifactVersion.REQUIRED_FRAGMENT}
                            {inner}
                        }}
                    }}
                }}
            }}
        }}
    }}"""
    ),
)
def artifact_versions(
    artifactType: wdt.ArtifactType,
) -> list[wdt.ArtifactVersion]:
    res = []
    for artifactCollectionEdge in artifactType.gql[first_100_collections_alias][
        "edges"
    ]:
        for artifactEdge in artifactCollectionEdge["node"][first_100_artifacts_alias][
            "edges"
        ]:
            res.append(wdt.ArtifactVersion.from_gql(artifactEdge["node"]))
    return res
