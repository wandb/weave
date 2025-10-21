"""Tests for object_creation_utils.py utilities.

These tests verify that the helper functions serialize objects in the same way
as the SDK.  Ideally they would be placed next to the trace_server tests, but
the client serialization requires a client object to serialize.
"""

import weave
from weave.trace.serialization.serialize import to_json
from weave.trace.weave_client import WeaveClient
from weave.trace_server import object_creation_utils


def test_helper_serializes_op_same_way_as_sdk(client: WeaveClient) -> None:
    """Test that helpers serialize an Op the same way as SDK."""

    @weave.op
    def test_op(x: int) -> int:
        return x + 1

    # Serialize the Op using the SDK's to_json function
    sdk_val = to_json(test_op, client._project_id(), client)
    helper_val = object_creation_utils.build_op_val(
        sdk_val["files"][object_creation_utils.OP_SOURCE_FILE_NAME]
    )
    assert helper_val == sdk_val
