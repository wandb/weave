import pytest
from . import uris

URIS = [
    "op-get",
    "op-get/version1",
    "local-artifact:///tmp/artifact-dir/op-test/version",
    "local-artifact:///tmp/artifact-dir/op-test/version?extra=1",
    "local-artifact:///tmp/artifact-dir/op-test/version?extra=1&extra=2&extra=3",
    "local-artifact:///tmp/artifact-dir/op-test/version?extra=1&file=a.txt",
    "local-artifact:///tmp/artifact-dir/op-test/version?file=a.txt",
    "local-artifact://relative/artifact-dir/op-test/version",
    "local-artifact:///relative/artifact-dir/multiple_levels/nested/op-test/version",
    "wandb-artifact://entity-name/project/op-test:v0",
    "wandb-artifact://entity-name/project/op-test:v0?extra=1",
    "wandb-artifact://entity-name/project/op-test:v0?extra=1&extra=2&extra=3",
    "wandb-artifact://entity-name/project/op-test:v0?extra=1&file=_obj.types.json",
]
# URIS = [
#      "local-artifact://relative/artifact-dir/op-test/version",
# ]


@pytest.mark.parametrize("uri_str", URIS)
def test_parse_uri_str(uri_str: str):
    local_uri = uris.WeaveURI.parse(uri_str)
    assert uri_str == local_uri.uri


def test_parse_uri_hide_obj():
    uri_str = "local-artifact:///tmp/artifact-dir/op-test/version?file=_obj"
    expected_str = "local-artifact:///tmp/artifact-dir/op-test/version"
    local_uri = uris.WeaveURI.parse(uri_str)
    assert expected_str == local_uri.uri
