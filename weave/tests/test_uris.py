import pytest
from .. import uris

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
