from ..api import type as weave_type
from wandb.apis import public as wandb_api


@weave_type("artifactMembership")
class ArtifactCollectionMembership:
    artifactCollection: wandb_api.ArtifactCollection
    aliasName: str  # consider: versionIndex
