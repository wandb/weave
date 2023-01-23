from contextvars import Token
from dataclasses import dataclass, field
import json
import os
import random
import typing

from weave import context_state
from .. import wandb_api
from unittest import mock
import shutil

from .. import artifact_wandb
import graphql

TEST_TABLE_ARTIFACT_PATH = "testdata/wb_artifacts/test_res_1fwmcd3q:v0"
ABS_TEST_TABLE_ARTIFACT_PATH = os.path.abspath(TEST_TABLE_ARTIFACT_PATH)

shared_artifact_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "testdata", "shared_artifact_dir")
)


class FakeEntry:
    ref = None

    def __init__(self, path):
        self.path = path


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
        if path == "media/images/8f65e54dc684f7675aec.png":
            return FakeEntry(path)
        if path == "weird_table.table.json":
            return FakeEntry(path)
        # Otherwise, file is missing, return None.
        return None

    def get_entries_in_directory(self, cur_dir):
        if self.dir_to_use != None:
            target = os.path.join(self.dir_to_use, cur_dir)
            if os.path.exists(target) and os.path.isdir(target):
                return [
                    FakeEntry(os.path.join(cur_dir, sub_path))
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


class FakeVersion:
    entity = "stacey"
    project = "mendeleev"
    _sequence_name = "test_res_1fwmcd3q"
    version = "v0"
    name = "test_res_1fwmcd3q:v0"
    id = "1234567890"

    def __init__(self, requested_path=None):
        self._local_path = None
        if requested_path != None:
            target = os.path.abspath(os.path.join(shared_artifact_dir, requested_path))
            if os.path.exists(target):
                self._local_path = target
        self.manifest = FakeManifest(self._local_path)

    def get_path(self, path):
        if self._local_path != None:
            return FakePath(os.path.join(self._local_path, path))
        full_artifact_dir = os.path.join(
            artifact_wandb.wandb_artifact_dir(), TEST_TABLE_ARTIFACT_PATH
        )
        full_artifact_path = os.path.join(full_artifact_dir, path)
        os.makedirs(os.path.dirname(full_artifact_path), exist_ok=True)
        artifact_path = os.path.join(ABS_TEST_TABLE_ARTIFACT_PATH, path)
        shutil.copy2(artifact_path, full_artifact_path)
        return FakePath(artifact_path)

    def download(self):
        pass


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
        print("Executing Mocked Query in fixture_fakewandb.py:")
        print(graphql.language.print_ast(graphql.language.parse(gql.loc.source.body)))
        for handler in self.mock_handlers:
            res = handler(args, len(self.execute_log) - 1)
            if res is not None:
                print("RESULT:")
                print(res)
                return res
        raise Exception(
            "Query was not mocked - please fill out in fixture_fakewandb.py"
        )


class FakeApi:
    client = FakeClient()
    run = mock.Mock(return_value=FakeRun())

    def artifact(self, path):
        return FakeVersion(path.replace(":", "_"))

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
class SetupResponse:
    fake_api: FakeApi
    old_wandb_api_wandb_public_api: typing.Callable
    token: Token


def setup():
    # set _cache_namespace_token to a random value so that
    # tests don't share the same namespace (since it defaults to None)
    token = context_state._cache_namespace_token.set(str(random.randint(0, 1000000)))
    fake_api = FakeApi()

    def wandb_public_api():
        return fake_api

    old_wandb_api_wandb_public_api = wandb_api.wandb_public_api
    wandb_api.wandb_public_api = wandb_public_api
    return SetupResponse(
        fake_api,
        old_wandb_api_wandb_public_api,
        token,
    )


def teardown(setup_response: SetupResponse):
    context_state._cache_namespace_token.reset(setup_response.token)
    setup_response.fake_api.clear_execute_log()
    setup_response.fake_api.clear_mock_handlers()
    wandb_api.wandb_public_api = setup_response.old_wandb_api_wandb_public_api


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
