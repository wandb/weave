import os
import pytest
import shutil
from unittest import mock

from .. import artifacts_local
from .. import ops_domain
from .. import wandb_api
from ..ops_domain import wandb_domain_gql

TEST_TABLE_ARTIFACT_PATH = "testdata/wb_artifacts/test_res_1fwmcd3q:v0"


class FakeProject:
    entity = "stacey"
    name = "mendeleev"


class FakeEntry:
    pass


class FakeManifest:
    entries = {"fakePath": FakeEntry()}

    get_entry_by_path = mock.Mock(return_value=FakeEntry())


class FakePath:
    def __init__(self, path):
        self.path = path

    def download(self):
        return self.path


class FakeVersion:
    entity = "stacey"
    project = "mendeleev"
    _sequence_name = "test_res_1fwmcd3q"
    version = "v0"

    manifest = FakeManifest()

    def get_path(self, path):
        full_artifact_dir = os.path.join(
            artifacts_local.wandb_artifact_dir(), TEST_TABLE_ARTIFACT_PATH
        )
        full_artifact_path = os.path.join(full_artifact_dir, path)
        os.makedirs(os.path.dirname(full_artifact_path), exist_ok=True)
        artifact_path = os.path.join(TEST_TABLE_ARTIFACT_PATH, path)
        shutil.copy2(artifact_path, full_artifact_path)
        return FakePath(artifact_path)

    def download(self):
        pass


class FakeVersions:
    __getitem__ = mock.Mock(return_value=FakeVersion())


class FakeArtifact:
    versions = mock.Mock(return_value=FakeVersions())


class FakeArtifacts:
    __getitem__ = mock.Mock(return_value=FakeArtifact())


class FakeArtifactType:
    # "collections" should be called "artifacts" in the wandb API
    collections = mock.Mock(return_value=FakeArtifacts())


class FakeClient:
    def execute(self, gql, variable_values):
        if gql.definitions[0].operation == "query":
            if (
                gql.definitions[0].name.value == "ProjectArtifact"
            ):  # this is for wandb_domain.gql.py::project_artifact
                return {
                    "project": {
                        "artifactCollection": {
                            "defaultArtifactType": {"name": "test_type"}
                        }
                    }
                }
            elif (
                gql.definitions[0].name.value == "ArtifactCollectionMembershipForAlias"
            ):  # this is for wandb_domain.gql.py::artifact_collection_membership_for_alias
                return {
                    "artifactCollection": {
                        "artifactMembership": {
                            "commitHash": "xyz",
                            "versionIndex": "0",
                        }
                    }
                }
            elif (
                gql.definitions[0].name.value == "ArtifactCollection"
            ):  # this is for public.py::ArtifactCollection.load
                return {"project": {"artifactType": {"artifactSequence": {"id": 1001}}}}

        raise Exception(
            "Query was not mocked - please fill out in fixture_fakewandb.py"
        )


class FakeApi:
    client = FakeClient()
    project = mock.Mock(return_value=FakeProject())
    artifact_type = mock.Mock(return_value=FakeArtifactType())
    artifact = mock.Mock(return_value=FakeVersion())


fake_api = FakeApi()


def wandb_public_api():
    return fake_api


def setup():
    old_wandb_api_wandb_public_api = wandb_api.wandb_public_api
    wandb_api.wandb_public_api = wandb_public_api
    old_wandb_domain_gql_wandb_public_api = wandb_domain_gql.wandb_public_api
    wandb_domain_gql.wandb_public_api = wandb_public_api
    return (
        old_wandb_api_wandb_public_api,
        old_wandb_domain_gql_wandb_public_api,
    )


def teardown(setup_response):
    wandb_api.wandb_public_api = setup_response[0]
    wandb_domain_gql.wandb_public_api = setup_response[1]
