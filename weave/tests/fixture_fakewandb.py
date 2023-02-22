from contextvars import Token
from dataclasses import dataclass, field
import json
import os
import random
import tempfile
import typing

from weave import context_state
from weave import wandb_api
from weave import util
from ..artifact_wandb import WandbArtifact, WeaveWBArtifactURI, is_valid_version_index
from .. import wandb_client_api
from unittest import mock
import shutil
import weave

# Note: We're mocking out the whole io_service right now. This is too
# high level and doesn't test the actual io implementation. We should
# mock wandb_api instead probably.
from .. import io_service

TEST_TABLE_ARTIFACT_PATH = "testdata/wb_artifacits/test_res_1fwmcd3q:v0"
ABS_TEST_TABLE_ARTIFACT_PATH = os.path.abspath(TEST_TABLE_ARTIFACT_PATH)

shared_artifact_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "testdata", "shared_artifact_dir")
)


class FakeEntry:
    ref = None

    def __init__(self, path):
        self.path = path

    def __getitem__(self, key):
        if key == "ref":
            return None
        elif key == "digest":
            return self.path
        raise KeyError

    def get(self, path):
        try:
            return self[path]
        except KeyError:
            return None


class FakeManifest:
    entries = {"fakeentry": FakeEntry("fakeentry")}

    def __init__(self, dir_to_use=None):
        self.dir_to_use = dir_to_use

    def get_entry_by_path(self, path):
        if self.dir_to_use != None:
            target = os.path.join(self.dir_to_use, path)
            if os.path.exists(target):
                if os.path.isdir(target):
                    return None
                return FakeEntry(path)
        if path == "test_results.table.json":
            return FakeEntry(path)
        if path.startswith("media/images") and path.endswith(".png"):
            return FakeEntry(path)
        if path == "weird_table.table.json":
            return FakeEntry(path)
        # Otherwise, file is missing, return None.
        return None

    def get_paths_in_directory(self, cur_dir):
        if self.dir_to_use != None:
            target = os.path.join(self.dir_to_use, cur_dir)
            if os.path.exists(target) and os.path.isdir(target):
                return [
                    os.path.join(cur_dir, sub_path)
                    for sub_path in os.listdir(target)
                    if os.path.isfile(os.path.join(target, sub_path))
                ]
        return []


class FakePath:
    def __init__(self, path):
        self.path = path

    def download(self, root=None):
        # copy file to root
        if root is not None:
            os.makedirs(root, exist_ok=True)
            shutil.copy2(self.path, root)
            return os.path.join(root, os.path.basename(self.path))
        return self.path


shared_artifact_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "testdata", "shared_artifact_dir")
)


@dataclass
class FakeVersion:
    entity: str = "stacey"
    project: str = "mendeleev"
    _sequence_name: str = "test_res_1fwmcd3q"
    version: str = "v0"
    name: str = "test_res_1fwmcd3q:v0"
    id: str = "1234567890"


class FakeVersions:
    __getitem__ = mock.Mock(return_value=FakeVersion())

    def __iter__(self):
        return iter([FakeVersion()])


class FakeArtifact:
    versions = mock.Mock(return_value=FakeVersions())
    entity = "stacey"
    project = "mendeleev"
    name = "test_res_1fwmcd3q"


class FakeRunFile:
    def __init__(self, name):
        self.name = name

    def download(self, root, replace=False):
        if self.name == "media/tables/legacy_table.table.json":
            path = os.path.join(root, "legacy_table.table.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(
                    json.dumps(
                        {
                            "columns": ["col1", "col2"],
                            "data": [["a", "b"], ["c", "d"]],
                        }
                    )
                )
            return open(path)
        else:
            raise Exception(f"Please mock file {self.name} in fixture_fakewandb.py")


class FakeRun:
    def file(self, name):
        return FakeRunFile(name)


@dataclass
class FakeClient:
    execute_log: typing.List[dict[str, typing.Any]] = field(default_factory=list)
    mock_handlers: typing.List[
        typing.Callable[[dict[str, typing.Any], int], typing.Optional[dict]]
    ] = field(default_factory=list)

    def execute(self, gql, variable_values):
        args = {"gql": gql, "variable_values": variable_values}
        self.execute_log.append(args)
        # This should only print when the test fails
        # print("Executing Mocked Query in fixture_fakewandb.py:")
        # print(graphql.language.print_ast(graphql.language.parse(gql.loc.source.body)))
        for handler in self.mock_handlers:
            res = handler(args, len(self.execute_log) - 1)
            if res is not None:
                # print("RESULT:")
                # print(res)
                return res
        raise Exception(
            "Query was not mocked - please fill out in fixture_fakewandb.py",
            gql.loc.source.body,
        )


class FakeApi:
    client = FakeClient()
    run = mock.Mock(return_value=FakeRun())

    def artifact(self, path: str) -> FakeVersion:
        entity, project, name = path.split("/")
        name, version = name.split(":")
        return FakeVersion(
            entity=entity,
            project=project,
            name=name,
            version="v4" if not is_valid_version_index(version) else version,
        )

    def add_mock(
        self,
        handler: typing.Callable[[dict[str, typing.Any], int], typing.Optional[dict]],
    ):
        self.client.mock_handlers.append(handler)

    def execute_log(self):
        return self.client.execute_log

    def clear_execute_log(self):
        self.client.execute_log = []

    def clear_mock_handlers(self):
        self.client.mock_handlers = []


@dataclass
class MockedArtifact:
    artifact: typing.Any
    local_path: tempfile.TemporaryDirectory


class FakeIoServiceClient:
    def __init__(self):
        self.mocked_artifacts = {}

    def add_artifact(self, artifact, artifact_uri):
        d = tempfile.TemporaryDirectory()
        for path, entry in artifact.manifest.entries.items():
            target_file_path = os.path.join(d.name, path)
            os.makedirs(os.path.dirname(target_file_path), exist_ok=True)
            shutil.copy2(entry.local_path, target_file_path)
        ma = MockedArtifact(artifact, d)

        self.mocked_artifacts[str(artifact_uri)] = ma

    def manifest(self, artifact_uri):
        uri_str = str(artifact_uri.with_path(""))
        if uri_str in self.mocked_artifacts:
            return FakeManifest(self.mocked_artifacts[uri_str].local_path.name)
        requested_path = f"{artifact_uri.entity_name}/{artifact_uri.project_name}/{artifact_uri.name}_{artifact_uri.version}"
        target = os.path.abspath(os.path.join(shared_artifact_dir, requested_path))
        return FakeManifest(target)

    def cleanup(self):
        for ma in self.mocked_artifacts.values():
            ma.local_path.cleanup()

    @property
    def fs(self):
        class FakeFs:
            root = shared_artifact_dir

            def path(self, path):
                return os.path.join(self.root, path)

        return FakeFs()

    def direct_url(self, artifact_uri):
        return f"https://api.wandb.ai/{artifact_uri.entity_name}/{artifact_uri.project_name}/{artifact_uri.name}_{artifact_uri.version}/{artifact_uri.path}"

    def ensure_file(self, artifact_uri):
        uri_str = str(artifact_uri.with_path(""))
        if uri_str in self.mocked_artifacts:
            return os.path.join(
                self.mocked_artifacts[uri_str].local_path.name, artifact_uri.path
            )
        return f"{artifact_uri.entity_name}/{artifact_uri.project_name}/{artifact_uri.name}_{artifact_uri.version}/{artifact_uri.path}"


@dataclass
class SetupResponse:
    fake_api: FakeApi
    fake_io: FakeIoServiceClient
    old_wandb_api_wandb_public_api: typing.Callable
    orig_io_service_client: FakeIoServiceClient
    token: Token

    def mock_artifact_as_node(
        self, artifact, entity_name="test_entity", project_name="test_project"
    ):
        artifact_uri = WeaveWBArtifactURI.parse(
            f"wandb-artifact:///{entity_name}/{project_name}/{artifact.name}:v{len(self.fake_io.mocked_artifacts)}"
        )
        self.fake_io.add_artifact(artifact, artifact_uri)
        return weave.make_node(
            WandbArtifact(
                "test_name",
                None,
                artifact_uri,
            )
        )


def setup():
    # Set user id to random string, its used as the cache namepsace and we want
    # each test to use a fresh one.
    token = wandb_api.set_wandb_api_context(util.rand_string_n(10), None, None, None)
    fake_api = FakeApi()
    fake_io_service_client = FakeIoServiceClient()

    def wandb_public_api():
        return fake_api

    old_wandb_api_wandb_public_api = wandb_client_api.wandb_public_api
    wandb_client_api.wandb_public_api = wandb_public_api

    def get_sync_client():
        return fake_io_service_client

    orig_io_service_client = io_service.get_sync_client
    io_service.get_sync_client = get_sync_client

    return SetupResponse(
        fake_api,
        fake_io_service_client,
        old_wandb_api_wandb_public_api,
        orig_io_service_client,
        token,
    )


def teardown(setup_response: SetupResponse):
    wandb_api.reset_wandb_api_context(setup_response.token)
    setup_response.fake_api.clear_execute_log()
    setup_response.fake_api.clear_mock_handlers()
    setup_response.fake_io.cleanup()
    wandb_client_api.wandb_public_api = setup_response.old_wandb_api_wandb_public_api
    io_service.get_sync_client = setup_response.orig_io_service_client  # type: ignore


entity_payload = {
    "id": "RW50aXR5OmFoSnpmbmRoYm1SaUxYQnliMlIxWTNScGIyNXlFZ3NTQmtWdWRHbDBlU0lHYzNSaFkyVjVEQQ==",
    "name": "stacey",
}
project_payload = {
    "id": "UHJvamVjdDp2MTptZW5kZWxlZXY6c3RhY2V5",
    "name": "mendeleev",
    "entity": entity_payload,
}
run_payload = {
    "id": "UnVuOnYxOjJlZDV4d3BuOm1lbmRlbGVldjpzdGFjZXk=",
    "name": "2ed5xwpn",
    "project": project_payload,
}
run2_payload = {
    "id": "run2_id",
    "name": "run2_name",
    "project": project_payload,
}
run3_payload = {
    "id": "run3_id",
    "name": "run3_name",
    "project": project_payload,
}
defaultArtifactType_payload = {
    "id": "QXJ0aWZhY3RUeXBlOjIzNzc=",
    "name": "test_results",
    "project": project_payload,
}
artifactSequence_payload = {
    "id": "QXJ0aWZhY3RDb2xsZWN0aW9uOjE4MDQ0MjY=",
    "name": "test_res_1fwmcd3q",
    "defaultArtifactType": defaultArtifactType_payload,
}
artifactVersion_payload = {
    "id": "QXJ0aWZhY3Q6MTQxODgyNDA=",
    "versionIndex": 0,
    "artifactSequence": artifactSequence_payload,
}
artifactMembership_payload = {
    "id": "QXJ0aWZhY3RDb2xsZWN0aW9uTWVtYmVyc2hpcDoxNDE4NDI1MQ==",
    "versionIndex": 0,
    "artifact": artifactVersion_payload,
    "artifactCollection": artifactSequence_payload,
}
artifactAlias_payload = {
    "id": "abcdefg",
    "alias": "custom_alias",
    "artifact": artifactVersion_payload,
    "artifactCollection": artifactSequence_payload,
}
