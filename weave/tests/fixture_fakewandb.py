import json
import os
import shutil
import typing
import uuid
from contextvars import Token
from dataclasses import dataclass, field
from unittest import mock
from urllib import parse

import wandb

import weave
from weave import util

# Note: We're mocking out the whole io_service right now. This is too
# high level and doesn't test the actual io implementation. We should
# mock wandb_api instead probably.
from weave.legacy import io_service, wandb_api, wandb_client_api
from weave.legacy.artifact_wandb import (
    WandbArtifact,
    WandbArtifactManifest,
    WeaveWBArtifactByIDURI,
    WeaveWBArtifactURI,
)

from .tag_test_util import op_add_tag

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
        elif key == "size":
            return 1234
        raise KeyError

    def get(self, path):
        try:
            return self[path]
        except KeyError:
            return None


class FakeArtifactManifestEntry:
    def __init__(self, entry):
        self.entry = entry

    def __getitem__(self, key):
        if key == "birth_artifact_id":
            return self.entry.birth_artifact_id
        if key == "digest":
            return self.entry.digest
        if key == "path":
            return self.entry.path
        if key == "ref":
            return self.entry.ref
        if key == "size":
            return self.entry.size
        raise KeyError

    def get(self, path):
        try:
            return self[path]
        except KeyError:
            return None


class FakeFilesystemManifest:
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
                    for sub_path in sorted(os.listdir(target), reverse=True)
                    if os.path.isfile(os.path.join(target, sub_path))
                ]
        return []


class FakeArtifactManifest:
    def __init__(self, artifact):
        self.artifact = artifact
        self.storage_layout = WandbArtifactManifest.StorageLayout.V1

    def get_entry_by_path(self, path):
        entry = self.artifact.manifest.get_entry_by_path(path)
        if entry is None:
            return None
        return FakeArtifactManifestEntry(entry)

    def get_paths_in_directory(self, cur_dir):
        for entry in self.artifact.manifest.entries.values():
            if entry.path.startswith(cur_dir):
                yield entry.path


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
    commit_hash: str = "303db33c9f9264768626"


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
        if ":" in name:
            name, version = name.split(":")
        else:
            version = "latest"

        return FakeVersion(
            entity=entity,
            project=project,
            name=name,
            version=version,  # currently a commit_hash or "latest"
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
    # local_path: tempfile.TemporaryDirectory


class FakeIoServiceClient:
    def __init__(self):
        self.mocked_artifacts = {}

    def add_artifact(self, artifact, artifact_uri):
        ma = MockedArtifact(artifact)
        self.mocked_artifacts[str(artifact_uri)] = ma

    def manifest(self, artifact_uri):
        uri_str = str(artifact_uri.with_path(""))
        if uri_str in self.mocked_artifacts:
            return FakeArtifactManifest(self.mocked_artifacts[uri_str].artifact)
            # return FakeFilesystemManifest(self.mocked_artifacts[uri_str].local_path.name)
        if isinstance(artifact_uri, WeaveWBArtifactURI):
            requested_path = f"{artifact_uri.entity_name}/{artifact_uri.project_name}/{artifact_uri.name}_{artifact_uri.version}"
        elif isinstance(artifact_uri, WeaveWBArtifactByIDURI):
            requested_path = f"{artifact_uri.path_root}/{artifact_uri.artifact_id}/{artifact_uri.name}_{artifact_uri.version}"
        target = os.path.abspath(os.path.join(shared_artifact_dir, requested_path))
        return FakeFilesystemManifest(target)

    def cleanup(self):
        pass

    @property
    def fs(self):
        class FakeFs:
            root = shared_artifact_dir

            def path(self, path):
                return os.path.join(self.root, path)

        return FakeFs()

    def direct_url(self, artifact_uri):
        if isinstance(artifact_uri, WeaveWBArtifactURI):
            return f"https://api.wandb.ai/{artifact_uri.entity_name}/{artifact_uri.project_name}/{artifact_uri.name}_{artifact_uri.version}/{artifact_uri.path}"
        elif isinstance(artifact_uri, WeaveWBArtifactByIDURI):
            return f"https://api.wandb.ai/{artifact_uri.path_root}/{artifact_uri.artifact_id}/{artifact_uri.name}_{artifact_uri.version}/{artifact_uri.path}"

    def ensure_file(self, artifact_uri):
        uri_str = str(artifact_uri.with_path(""))
        if uri_str in self.mocked_artifacts:
            entry = self.mocked_artifacts[uri_str].artifact.manifest.entries.get(
                artifact_uri.path
            )
            if entry is None:
                return None
            return entry.local_path
        if isinstance(artifact_uri, WeaveWBArtifactURI):
            return f"{artifact_uri.entity_name}/{artifact_uri.project_name}/{artifact_uri.name}_{artifact_uri.version}/{artifact_uri.path}"
        elif isinstance(artifact_uri, WeaveWBArtifactByIDURI):
            return f"{artifact_uri.path_root}/{artifact_uri.artifact_id}/{artifact_uri.name}_{artifact_uri.version}/{artifact_uri.path}"

    def ensure_file_downloaded(self, download_url):
        # assumes the file is already in the testdata directory
        _, netloc, path, _, _, _ = parse.urlparse(download_url)
        return os.path.join("wandb_file_manager", netloc, path.lstrip("/"))


@dataclass
class SetupResponse:
    fake_api: FakeApi
    fake_io: FakeIoServiceClient
    old_wandb_api_wandb_public_api: typing.Callable
    orig_io_service_client: FakeIoServiceClient
    token: Token

    def mock_artifact_as_node(
        self,
        artifact,
        entity_name="test_entity",
        project_name="test_project",
        tag_payload={
            # In the future, we should make these actual run and project objects so we can chain ops
            "fake_run": "test_run",
            "fake_project": "test_project",
        },
    ):
        artifact_uri = WeaveWBArtifactURI.parse(
            f"wandb-artifact:///{entity_name}/{project_name}/{artifact.name}:{artifact.commit_hash}"
        )

        self.fake_io.add_artifact(artifact, artifact_uri)
        res = weave.save(
            WandbArtifact(
                "test_name",
                None,
                artifact_uri,
            )
        )
        if tag_payload:
            res = op_add_tag(res, tag_payload)
        return res

    def mock_artifact_by_id_as_node(
        self,
        artifact,
        tag_payload={
            # In the future, we should make these actual run and project objects so we can chain ops
            "fake_run": "test_run",
            "fake_project": "test_project",
        },
    ):
        artifact_uri = WeaveWBArtifactByIDURI.parse(
            f"wandb-artifact-by-id:///__wb_artifacts_by_id__/{artifact.id}/{artifact.name}:{artifact.commit_hash}"
        )

        self.fake_io.add_artifact(artifact, artifact_uri)
        res = weave.save(
            WandbArtifact(
                "test_name",
                None,
                artifact_uri,
            )
        )
        if tag_payload:
            res = op_add_tag(res, tag_payload)
        return res


class PatchedSDKArtifact(wandb.Artifact):
    @property
    def commit_hash(self) -> str:
        if self._commit_hash is None:
            self._commit_hash = uuid.uuid4().hex[:20]
        return typing.cast(str, self._commit_hash)


OriginalArtifactSymbol = wandb.Artifact


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

    # patch wandb artifact to allow us to generate a commit hash before we log the artifact
    wandb.Artifact = PatchedSDKArtifact

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
    wandb.Artifact = OriginalArtifactSymbol


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
    "project": project_payload,
    "defaultArtifactType": defaultArtifactType_payload,
}
artifactVersion_payload = {
    "id": "QXJ0aWZhY3Q6MTQxODgyNDA=",
    "versionIndex": 0,
    "commitHash": "303db33c9f9264768626",
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
artifactSequence_no_entity_payload = {
    "id": "QXJ0aWZhY3RDb2xsZWN0aW9uOjE4MDQ0MjY=",
    "name": "test_res_1fwmcd3q",
    "project": None,
    "defaultArtifactType": defaultArtifactType_payload,
}
artifactVersion_no_entity_payload = {
    "id": "QXJ0aWZhY3Q6MTQxODgyNDA=",
    "versionIndex": 0,
    "commitHash": "303db33c9f9264768626",
    "artifactSequence": artifactSequence_no_entity_payload,
}
