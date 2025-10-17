"""Tests for object_creation_utils.py utilities.

These tests verify that the helper functions serialize objects in the same way
as the SDK.  Ideally they would be placed next to the trace_server tests, but
the client serialization requires a client object to serialize.
"""

import weave
from weave.trace.object_record import pydantic_object_record
from weave.trace.serialization.serialize import to_json
from weave.trace.weave_client import WeaveClient, map_to_refs
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


def test_helper_serializes_dataset_same_way_as_sdk(client: WeaveClient) -> None:
    """Test that helpers serialize a Dataset the same way as SDK."""
    # Create a test dataset
    dataset = weave.Dataset(
        name="test_dataset",
        description="Test dataset for serialization",
        rows=[
            {"id": 1, "value": "first"},
            {"id": 2, "value": "second"},
            {"id": 3, "value": "third"},
        ],
    )

    # Note: Unlike Op which has custom serialization, Dataset is a pydantic
    # model that gets converted to an ObjectRecord. We need to simulate the
    # actual save process:

    # 1. Save the table to get a table reference
    client._save_table(dataset.rows)

    # 2. Convert to ObjectRecord (what gets serialized)
    obj_rec = pydantic_object_record(dataset)

    # 3. Map nested objects to their refs (table -> table ref)
    mapped_obj_rec = map_to_refs(obj_rec)

    # 4. Finally serialize
    sdk_val = to_json(mapped_obj_rec, client._project_id(), client)

    # Extract the table reference URI from the serialized data
    table_ref_uri = sdk_val["rows"]

    # Build the dataset value using the helper function
    helper_val = object_creation_utils.build_dataset_val(
        name=dataset.name,
        description=dataset.description,
        table_ref=table_ref_uri,
    )

    assert helper_val == sdk_val
