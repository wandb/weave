import os
from unittest import mock
from . import api as weave
from . import ops as ops
from . import ops_domain
from . import wandb_api

TEST_TABLE_ARTIFACT_PATH = "testdata/wb_artifacts/test_res_1fwmcd3q:v0"


def test_table_call():
    class FakeProject:
        entity = "stacey"
        name = "mendeleev"

    class FakeManifest:
        pass

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

        manifest = mock.Mock(return_value=FakeManifest())

        def get_path(self, path):
            return FakePath(os.path.join(TEST_TABLE_ARTIFACT_PATH, path))

    class FakeVersions:
        __getitem__ = mock.Mock(return_value=FakeVersion())

    class FakeArtifact:
        versions = mock.Mock(return_value=FakeVersions())

    class FakeArtifacts:
        __getitem__ = mock.Mock(return_value=FakeArtifact())

    class FakeArtifactType:
        # "collections" should be called "artifacts" in the wandb API
        collections = mock.Mock(return_value=FakeArtifacts())

    class FakeApi:
        project = mock.Mock(return_value=FakeProject())
        artifact_type = mock.Mock(return_value=FakeArtifactType())
        artifact = mock.Mock(return_value=FakeVersion())

    fake_api = FakeApi()

    def wandb_public_api():
        return fake_api

    ops_domain.wandb_public_api = wandb_public_api
    wandb_api.wandb_public_api = wandb_public_api

    table_image0_node = (
        ops.project("stacey", "mendeleev")
        .artifact_type("test_results")
        .artifacts()[0]
        .versions()[0]
        .path("test_results.table.json")
        .table()
        .rows()[0]["image"]
    )
    table_image0 = weave.use(table_image0_node)
    assert table_image0.height == 299
    assert table_image0.width == 299
    assert table_image0.path.path == "media/images/6274b7484d7ed4b6ad1b.png"

    # artifactVersion is not currently callable on image node as a method.
    # TODO: fix
    image0_url_node = (
        ops.wbartifact.artifactVersion(table_image0_node)
        .path(
            "wandb-artifact://stacey/mendeleev/test_res_1fwmcd3q:v0?file=media%2Fimages%2F8f65e54dc684f7675aec.png"
        )
        .direct_url_as_of(1654358491562)
    )
    image0_url = weave.use(image0_url_node)
    assert image0_url.endswith(
        "testdata/wb_artifacts/test_res_1fwmcd3q:v0/media/images/8f65e54dc684f7675aec.png"
    )
