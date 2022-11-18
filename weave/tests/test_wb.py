import os
import shutil
from unittest import mock

import pytest
from .. import api as weave
from .. import ops as ops
from .. import ops_domain
from .. import wandb_api

TEST_TABLE_ARTIFACT_PATH = "testdata/wb_artifacts/test_res_1fwmcd3q:v0"


@pytest.mark.parametrize(
    "table_file_node",
    [
        # Path used in weave demos
        ops.project("stacey", "mendeleev")
        .artifactType("test_results")
        .artifacts()[0]
        .versions()[0]
        .file("test_results.table.json"),
        # Path used in artifact browser
        ops.project("stacey", "mendeleev")
        .artifact("test_results")
        .membershipForAlias("v0")
        .artifactVersion()
        .file("test_results.table.json"),
    ],
)
def test_table_call(table_file_node, fake_wandb):
    table_image0_node = table_file_node.table().rows()[0]["image"]
    table_image0 = weave.use(table_image0_node)
    assert table_image0.height == 299
    assert table_image0.width == 299
    assert table_image0.path.path == "media/images/6274b7484d7ed4b6ad1b.png"

    # artifactVersion is not currently callable on image node as a method.
    # TODO: fix
    image0_url_node = (
        ops.wbartifact.artifactVersion(table_image0_node)
        .file(
            "wandb-artifact://stacey/mendeleev/test_res_1fwmcd3q:v0?file=media%2Fimages%2F8f65e54dc684f7675aec.png"
        )
        .direct_url_as_of(1654358491562)
    )
    image0_url = weave.use(image0_url_node)
    assert image0_url.endswith(
        "testdata/wb_artifacts/test_res_1fwmcd3q_v0/media/images/8f65e54dc684f7675aec.png"
    )
