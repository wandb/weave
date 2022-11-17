from ..api import type as weave_type
from wandb.apis import public as wandb_api
from .. import weave_types as types
from ..wandb_api import wandb_public_api


# "Api" types - they map to a public API class (needs serialization)
class ArtifactCollectionType(types._PlainStringNamedType):
    name = "artifact"
    instance_classes = wandb_api.ArtifactCollection
    instance_class = wandb_api.ArtifactCollection

    def instance_to_dict(self, obj):
        # TODO: I'm here, trying to serialize/deserialize Artifact
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_type_name": obj.type,
            "artifact_name": obj.name,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.artifact_type(
            d["artifact_type_name"], project=f"{d['entity_name']}/{d['project_name']}"
        ).collection(d["artifact_name"])


# "Virtual" types - they do not map directly to a public API class


@weave_type("artifactMembership")
class ArtifactCollectionMembership:
    artifact_collection: wandb_api.ArtifactCollection
    commit_hash: str
    version_index: int


@weave_type("artifactAlias")
class ArtifactAlias:
    _alias: str
    artifact_collection: wandb_api.ArtifactCollection
