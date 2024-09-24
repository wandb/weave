import pytest

from weave.legacy.weave import uris
from weave.legacy.weave.artifact_wandb import WeaveWBArtifactURI

URIS = [
    "op-get",
    "op-get/version1",
    "local-artifact:///op-test:version",
    "local-artifact:///op-test:version#1",
    "local-artifact:///op-test:version#1/2/3",
    "local-artifact:///op-test:version/a.txt#1",
    "local-artifact:///op-test:version/a.txt",
    "local-artifact:///op-test:version/subdir/a.txt",
    "wandb-artifact:///entity-name/project/op-test:v0",
    "wandb-artifact:///entity-name/project/op-test:v0#1",
    "wandb-artifact:///entity-name/project/op-test:v0#1/2/3",
    "wandb-artifact:///entity-name/project/op-test:v0/obj.types.json#1",
]


@pytest.mark.parametrize("uri_str", URIS)
def test_parse_uri_str(uri_str: str):
    local_uri = uris.WeaveURI.parse(uri_str)
    assert uri_str == str(local_uri)


def test_uri_with_slashes():
    uri = WeaveWBArtifactURI(
        "test-art-deleted-07/02/23-17898374309789951906",
        "latest",
        "test",
        "test",
        "",
        "test.table.json",
    )
    uri_str = str(uri)
    uri2 = uris.WeaveURI.parse(uri_str)
    assert uri == uri2
