# Note: in the long run we want to eiminate all uses of sdk objects!

import datetime
from wandb.apis import public

from .. import wandb_api
from .. import safe_cache
from ..decorator_type import type as weave_type

# These should contain the minimum identifiers needed to load the object
# When in doubt, think of what the PK is for the object in the database
# or what the min data needed to get the object via GQL.


@weave_type("org", True)
class Org:
    pass


@weave_type("entity", True)
class Entity:
    entity_name: str


@weave_type("user", True)  # TODO: How to decailt this is an instance of entity?
class User:
    user_name: str


@safe_cache.safe_lru_cache(1000)
def _memoed_get_project(entity_name: str, project_name: str):
    return wandb_api.wandb_public_api().project(project_name, entity_name)


@weave_type("project", True)
class Project:
    _entity: Entity
    project_name: str

    @property
    def sdk_obj(self) -> public.Project:
        if not hasattr(self, "_sdk_obj"):  # or self._sdk_obj is None:  # tyoe: ignore
            self._sdk_obj = _memoed_get_project(
                self._entity.entity_name, self.project_name
            )
        return self._sdk_obj


# This is very helpful when deserializing runs which have been
# serialized. Without caching here, the mappers end up loading
# the run for every tagged cell in the table!
@safe_cache.safe_lru_cache(1000)
def _memoed_get_run(entity_name: str, project_name: str, run_id: str):
    return wandb_api.wandb_public_api().run(f"{entity_name}/{project_name}/{run_id}")


@weave_type("run", True)
class Run:
    _project: Project
    run_id: str

    @property
    def sdk_obj(self) -> public.Run:
        if not hasattr(self, "_sdk_obj"):  # or self._sdk_obj is None:  # tyoe: ignore
            self._sdk_obj = _memoed_get_run(
                self._project._entity.entity_name,
                self._project.project_name,
                self.run_id,
            )
        return self._sdk_obj

    @classmethod
    def from_sdk_obj(cls, obj: public.Run):
        inst = cls(
            _project=Project(
                _entity=Entity(entity_name=obj.entity),
                project_name=obj.project,
            ),
            run_id=obj.id,
        )
        setattr(inst, "_sdk_obj", obj)
        return inst


@safe_cache.safe_lru_cache(1000)
def _memoed_get_artifact_type(
    entity_name: str, project_name: str, artifact_type_name: str
):
    return wandb_api.wandb_public_api().artifact_type(
        artifact_type_name, f"{entity_name}/{project_name}"
    )


@weave_type("artifactType", True)
class ArtifactType:
    _project: Project
    artifact_type_name: str

    @property
    def sdk_obj(self) -> public.Run:
        if not hasattr(self, "_sdk_obj"):  # or self._sdk_obj is None:  # tyoe: ignore
            self._sdk_obj = _memoed_get_artifact_type(
                self._project._entity.entity_name,
                self._project.project_name,
                self.artifact_type_name,
            )
        return self._sdk_obj

    @classmethod
    def from_sdk_obj(cls, obj: public.ArtifactType):
        inst = cls(
            _project=Project(
                _entity=Entity(entity_name=obj.entity),
                project_name=obj.project,
            ),
            artifact_type_name=obj.type,
        )
        setattr(inst, "_sdk_obj", obj)
        return inst


@safe_cache.safe_lru_cache(1000)
def _memoed_get_artifact_collection(
    entity_name: str, project_name: str, artifact_name: str, type_name: str
):
    return public.ArtifactCollection(
        wandb_api.wandb_public_api().client,
        entity_name,
        project_name,
        artifact_name,
        type_name,
    )


# Note: the SDK does not support portfolios yet, so we should make a PR to ensure fix that
@weave_type("artifact", True)  # Name mismatch intention due to weave0
class ArtifactCollection:
    _project: Project
    artifact_collection_name: str

    @property
    def sdk_obj(self) -> public.ArtifactCollection:
        if not hasattr(self, "_sdk_obj"):  # or self._sdk_obj is None:  # tyoe: ignore
            # This is a special case of needing to hit the API to get the type first!
            from ..ops_domain.wandb_domain_gql import artifact_collection_artifact_type

            type_name = artifact_collection_artifact_type(self).artifact_type_name
            self._sdk_obj = _memoed_get_artifact_collection(
                self._project._entity.entity_name,
                self._project.project_name,
                self.artifact_collection_name,
                type_name,
            )
        return self._sdk_obj

    @classmethod
    def from_sdk_obj(cls, obj: public.ArtifactCollection):
        inst = cls(
            _project=Project(
                _entity=Entity(entity_name=obj.entity),
                project_name=obj.project,
            ),
            artifact_collection_name=obj.name,
        )
        setattr(inst, "_sdk_obj", obj)
        return inst


@weave_type("artifactMembership", True)  # Name mismatch intention due to weave0
class ArtifactCollectionMembership:
    _artifact_collection: ArtifactCollection
    # commit_hash: str
    version_index: int


@safe_cache.safe_lru_cache(1000)
def _memoed_get_artifact_version(
    entity_name: str, project_name: str, artifact_name: str, version_index: int
):
    return wandb_api.wandb_public_api().artifact(
        f"{entity_name}/{project_name}/{artifact_name}:v{version_index}"
    )


@weave_type("artifactVersion", True)
class ArtifactVersion:
    _artifact_sequence: ArtifactCollection  # home collection
    # digest: str
    version_index: int

    @classmethod
    def from_sdk_obj(cls, obj: public.Artifact):
        inst = cls(
            _artifact_sequence=ArtifactCollection(
                _project=Project(
                    _entity=Entity(entity_name=obj.entity),
                    project_name=obj.project,
                ),
                artifact_collection_name=obj.name.split(":")[0],
            ),
            version_index=obj.version.split("v")[1],
        )
        setattr(inst, "_sdk_obj", obj)
        return inst

    @property
    def sdk_obj(self) -> public.Artifact:
        if not hasattr(self, "_sdk_obj"):  # or self._sdk_obj is None:  # tyoe: ignore
            self._sdk_obj = _memoed_get_artifact_version(
                self._artifact_sequence._project._entity.entity_name,
                self._artifact_sequence._project.project_name,
                self._artifact_sequence.artifact_collection_name,
                self.version_index,
            )
        return self._sdk_obj


@weave_type("artifactAlias", True)
class ArtifactAlias:
    _artifact_collection: ArtifactCollection
    alias_name: str


# Simple types (maybe should be put into primtives?)


@weave_type("date", True)
class Date:
    datetime_value: datetime.datetime


@weave_type("link", True)
class Link:
    name: str
    url: str
