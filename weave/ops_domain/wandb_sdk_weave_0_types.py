import dataclasses
from ..api import type as weave_type
from wandb.apis import public as wandb_api
from .. import weave_types as types
from ..wandb_api import wandb_public_api
from .. import safe_cache


# "Api" types - they map to a public API class (needs serialization)
class ProjectType(types._PlainStringNamedType):
    name = "project"
    instance_classes = wandb_api.Project
    instance_class = wandb_api.Project

    def instance_to_dict(self, obj):
        return {"entity_name": obj.entity, "project_name": obj.name}

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.project(name=d["project_name"], entity=d["entity_name"])


# This is very helpful when deserializing runs which have been
# serialized. Without caching here, the mappers end up loading
# the run for every tagged cell in the table!
@safe_cache.safe_lru_cache(1000)
def _memoed_get_run(run_uri):
    import time

    print("%s: RUN INSTANCE FROM DICT" % time.time())
    api = wandb_public_api()
    run = api.run(run_uri)
    print("%s: DONE RUN INSTANCE FROM DICT" % time.time())
    return run

class RunType(types._PlainStringNamedType):
    name = "run"

    instance_classes = wandb_api.Run
    instance_class = wandb_api.Run

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj._entity,
            "project_name": obj.project,
            "run_id": obj.id,
        }

    def instance_from_dict(self, d):
        return _memoed_get_run("{entity_name}/{project_name}/{run_id}".format(**d))

@dataclasses.dataclass(frozen=True)
class RunsType(types.Type):
    name = "runs"

    instance_classes = wandb_api.Runs
    instance_class = wandb_api.Runs

    object_type: types.Type = RunType()

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.runs("{entity_name}/{project_name}".format(**d), per_page=500)

    @classmethod
    def from_dict(cls, d):
        return cls()

class ArtifactTypeType(types._PlainStringNamedType):
    name = "artifactType"
    instance_classes = wandb_api.ArtifactType
    instance_class = wandb_api.ArtifactType

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_type_name": obj.type,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.artifact_type(
            d["artifact_type_name"], project=f"{d['entity_name']}/{d['project_name']}"
        )

class ProjectArtifactTypesType(types.Type):
    name = "projectArtifactTypes"

    instance_classes = wandb_api.ProjectArtifactTypes
    instance_class = wandb_api.ProjectArtifactTypes

    @property
    def object_type(self):
        return RunType()

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.project("{entity_name}/{project_name}".format(**d)).artifacts_types()

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


class ArtifactsType(types.Type):
    name = "artifacts"
    instance_classes = wandb_api.ProjectArtifactCollections
    instance_class = wandb_api.ProjectArtifactCollections

    @property
    def object_type(self):
        return ArtifactCollectionType()

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_type_name": obj.type_name,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.artifact_type(
            d["artifact_type_name"], project=f"{d['entity_name']}/{d['project_name']}"
        ).collections()

class ArtifactVersionsType(types.Type):
    name = "projectArtifactVersions"
    instance_classes = wandb_api.ArtifactVersions
    instance_class = wandb_api.ArtifactVersions

    def instance_to_dict(self, obj):
        return {
            "entity_name": obj.entity,
            "project_name": obj.project,
            "artifact_type_name": obj.type,
            "artifact_name": obj.collection_name,
        }

    def instance_from_dict(self, d):
        api = wandb_public_api()
        return api.artifact_versions(
            d["artifact_type_name"],
            f"{d['entity_name']}/{d['project_name']}/{d['artifact_name']}",
        )

# "Virtual" types - they do not map directly to a public API class
@weave_type("entity")
class Entity:
    _name: str


@weave_type("user")
class User:
    username: str


@weave_type("artifactMembership")
class ArtifactCollectionMembership:
    artifact_collection: wandb_api.ArtifactCollection
    commit_hash: str
    version_index: int


@weave_type("artifactAlias")
class ArtifactAlias:
    _alias: str
    artifact_collection: wandb_api.ArtifactCollection
