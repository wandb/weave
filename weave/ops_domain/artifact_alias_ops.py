from ..api import op
from . import wb_domain_types


@op(name="artifactAlias-alias")
def alias(artifactAlias: wb_domain_types.ArtifactAlias) -> str:
    return artifactAlias.alias_name


@op(name="artifactAlias-artifact")
def artifact(
    artifactAlias: wb_domain_types.ArtifactAlias,
) -> wb_domain_types.ArtifactCollection:
    return artifactAlias._artifact_collection
