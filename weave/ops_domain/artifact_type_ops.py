from ..api import op
from . import wb_domain_types


@op(name="artifactType-name")
def name(artifactType: wb_domain_types.ArtifactType) -> str:
    return artifactType.artifact_type_name


@op(name="artifactType-artifacts")
def artifacts(
    artifactType: wb_domain_types.ArtifactType,
) -> list[wb_domain_types.ArtifactCollection]:
    return [
        wb_domain_types.ArtifactCollection.from_sdk_obj(c)
        for c in artifactType.sdk_obj.collections()
    ]
