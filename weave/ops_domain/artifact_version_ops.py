import json
from ..compile_domain import wb_gql_op_plugin
from ..api import op
from .. import weave_types as types
from . import wb_domain_types as wdt
from ..language_features.tagging.make_tag_getter_op import make_tag_getter_op
from .wandb_domain_gql import (
    gql_prop_op,
    gql_direct_edge_op,
    gql_connection_op,
    gql_root_op,
)

import typing
from . import wb_util
from urllib.parse import quote
from . import file_wbartifact
from .. import refs
from .. import artifacts_local
import logging
from . import wbartifact
from .. import uris

# Section 1/6: Tag Getters
# None

# Section 2/6: Root Ops
# None

# Section 3/6: Attribute Getters
gql_prop_op("artifactVersion-id", wdt.ArtifactVersionType, "id", types.String())
gql_prop_op("artifactVersion-digest", wdt.ArtifactVersionType, "digest", types.String())
gql_prop_op("artifactVersion-size", wdt.ArtifactVersionType, "size", types.Int())
gql_prop_op(
    "artifactVersion-description", wdt.ArtifactVersionType, "description", types.Int()
)
gql_prop_op(
    "artifactVersion-createdAt", wdt.ArtifactVersionType, "createdAt", wdt.DateType
)


@op(
    plugins=wb_gql_op_plugin(lambda inputs, inner: "metadata"),
)
def refine_metadata(
    artifactVersion: wdt.ArtifactVersion,
) -> types.Type:
    return wb_util.process_run_dict_type(
        json.loads(artifactVersion.gql["metadata"] or "{}")
    )


@op(
    name="artifactVersion-metadata",
    refine_output_type=refine_metadata,
    plugins=wb_gql_op_plugin(lambda inputs, inner: "metadata"),
)
def metadata(
    artifactVersion: wdt.ArtifactVersion,
) -> dict[str, typing.Any]:
    return wb_util.process_run_dict_obj(
        json.loads(artifactVersion.gql["metadata"] or "{}")
    )


# Section 4/6: Direct Relationship Ops
gql_direct_edge_op(
    "artifactVersion-aliases",
    wdt.ArtifactVersionType,
    "aliases",
    wdt.ArtifactAliasType,
    is_many=True,
)

gql_direct_edge_op(
    "artifactVersion-artifactType",
    wdt.ArtifactVersionType,
    "artifactType",
    wdt.ArtifactTypeType,
)

gql_direct_edge_op(
    "artifactVersion-artifactSequence",
    wdt.ArtifactVersionType,
    "artifactSequence",
    wdt.ArtifactCollectionType,
)


@op(
    name="artifactVersion-createdBy",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
        createdBy {{
            __typename
            ... on Run {{
                {wdt.Run.REQUIRED_FRAGMENT}
                {inner}
            }}
        }}
        """
    ),
)
def artifact_version_created_by(
    artifactVersion: wdt.ArtifactVersion,
) -> typing.Optional[wdt.Run]:
    if artifactVersion.gql["createdBy"]["__typename"] == "Run":
        return wdt.Run.from_gql(artifactVersion.gql["createdBy"])
    return None


@op(
    name="artifactVersion-createdByUser",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
        createdBy {{
            __typename
            ... on User {{
                {wdt.User.REQUIRED_FRAGMENT}
                {inner}
            }}
        }}
        """
    ),
)
def artifact_version_created_by_user(
    artifactVersion: wdt.ArtifactVersion,
) -> typing.Optional[wdt.User]:
    if artifactVersion.gql["createdBy"]["__typename"] == "User":
        return wdt.User.from_gql(artifactVersion.gql["createdBy"])
    return None


# Section 5/6: Connection Ops
gql_connection_op(
    "artifactVersion-artifactCollections",
    wdt.ArtifactVersionType,
    "artifactCollections",
    wdt.ArtifactCollectionType,
)

gql_connection_op(
    "artifactVersion-memberships",
    wdt.ArtifactVersionType,
    "artifactMemberships",
    wdt.ArtifactCollectionMembershipType,
)

gql_connection_op(
    "artifactVersion-usedBy",
    wdt.ArtifactVersionType,
    "usedBy",
    wdt.RunType,
    {},
    lambda inputs: f"first: 50",
)


# Section 6/6: Non Standard Business Logic Ops
@op(
    name="artifactVersion-name",
    plugins=wb_gql_op_plugin(
        lambda inputs, inner: f"""
            versionIndex
            artifactSequence {{
                id
                name
            }}
        """,
    ),
)
def op_artifact_version_name(
    artifact: wdt.ArtifactVersion,
) -> str:
    return f'{artifact.gql["artifactSequence"]["name"]}:v{artifact.gql["versionIndex"]}'


@op(name="artifactVersion-link")
def artifact_version_link(
    artifactVersion: wdt.ArtifactVersion,
) -> wdt.Link:
    home_sequence_name = artifactVersion.gql["artifactSequence"]["name"]
    home_sequence_version_index = artifactVersion.gql["versionIndex"]
    type_name = artifactVersion.gql["artifactSequence"]["defaultArtifactType"]["name"]
    project_name = artifactVersion.gql["artifactSequence"]["defaultArtifactType"][
        "project"
    ]["name"]
    entity_name = artifactVersion.gql["artifactSequence"]["defaultArtifactType"][
        "project"
    ]["entity"]["name"]
    return wdt.Link(
        f"{home_sequence_name}:v{home_sequence_version_index}",
        f"/{entity_name}/{project_name}/artifacts/{quote(type_name)}/{quote(home_sequence_name)}/v{home_sequence_version_index}",
    )


# The following two ops: artifactVersion-isWeaveObject and artifactVersion-files
# need more work to get artifact version file metadata.


@op(name="artifactVersion-isWeaveObject")
def artifact_version_is_weave_object(
    artifactVersion: wdt.ArtifactVersion,
) -> bool:
    # TODO: Need to copy over some logic from the old codebase
    return False


@op(name="artifactVersion-files")
def files(
    artifactVersion: wdt.ArtifactVersion,
) -> list[file_wbartifact.ArtifactVersionFile]:
    # TODO: What is the correct data model here? - def don't want to go download everything
    return []


# This op contains a bunch of custom logic, punting for now
@op()
def refine_history_metrics(
    artifactVersion: wdt.ArtifactVersion,
) -> types.Type:
    return wb_util.process_run_dict_type({})


@op(name="artifactVersion-historyMetrics", refine_output_type=refine_history_metrics)
def history_metrics(
    artifactVersion: wdt.ArtifactVersion,
) -> dict[str, typing.Any]:
    # TODO: We should probably create a backend endpoint for this... in weave0 we make a bunch on custom calls.
    return {}


# Special bridge functions to lower level local artifacts

# TODO: Move all this to helper functions off the artifactVersion object
def _artifact_version_to_wb_artifact(artifactVersion: wdt.ArtifactVersion):
    entity_name = artifactVersion.gql["artifactSequence"]["defaultArtifactType"][
        "project"
    ]["entity"]["name"]
    project_name = artifactVersion.gql["artifactSequence"]["defaultArtifactType"][
        "project"
    ]["name"]
    type_name = artifactVersion.gql["artifactSequence"]["defaultArtifactType"]["name"]
    home_sequence_name = artifactVersion.gql["artifactSequence"]["name"]
    home_version_index = artifactVersion.gql["versionIndex"]
    return artifacts_local.WandbArtifact(
        name=home_sequence_name,
        type=type_name,
        uri=uris.WeaveWBArtifactURI(
            f"wandb-artifact://{entity_name}/{project_name}/{home_sequence_name}:v{home_version_index}"
        ),
    )


@op(
    name="artifactVersion-file",
    output_type=refs.ArtifactVersionFileType(),
)
def file_(artifactVersion: wdt.ArtifactVersion, path: str):
    # TODO (tim): This is a total hack - I am not sure why dispatch is sending use these
    if isinstance(artifactVersion, artifacts_local.Artifact):
        logging.warning(
            "Expected input to be of type ArtifactVersion, but got artifacts_local.Artifact in artifactVersion-file"
        )
        art_local = artifactVersion
    else:
        art_local = _artifact_version_to_wb_artifact(artifactVersion)
    return wbartifact.ArtifactVersion.file.raw_resolve_fn(art_local, path)


@op(
    name="artifactVersion-fileReturnType",
    output_type=types.Type(),
)
def path_type(artifactVersion: wdt.ArtifactVersion, path: str):
    # TODO (tim): This is a total hack - I am not sure why dispatch is sending use thsese
    if isinstance(artifactVersion, artifacts_local.Artifact):
        logging.warning(
            "Expected input to be of type ArtifactVersion, but got artifacts_local.Artifact in artifactVersion-fileReturnType"
        )
        art_local = artifactVersion
    else:
        art_local = _artifact_version_to_wb_artifact(artifactVersion)
    return wbartifact.ArtifactVersion.path_type.raw_resolve_fn(art_local, path)
