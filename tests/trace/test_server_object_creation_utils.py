"""Tests for object_creation_utils.py utilities.

These tests verify that the helper functions serialize objects in the same way
as the SDK.  Ideally they would be placed next to the trace_server tests, but
the client serialization requires a client object to serialize.
"""

import weave
from weave.flow.scorer import Scorer
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


def test_helper_serializes_scorer_same_way_as_sdk(client: WeaveClient) -> None:
    """Test that helpers serialize a Scorer with the correct structure.

    Note: The helper creates base Scorer objects (not custom subclasses),
    so we compare the data fields rather than type metadata.
    """

    class TestScorer(Scorer):
        @weave.op
        def score(self, *, output, **kwargs):  # type: ignore
            return {"score": len(output)}

    scorer = TestScorer(name="test_scorer", description="Test scorer for serialization")

    # Like Dataset, Scorer is a pydantic model that gets converted to an ObjectRecord.
    # We need to simulate the actual save process:

    # 1. Save the score op to get a reference
    client._save_op(scorer.score)

    # 2. Save the summarize op to get a reference
    client._save_op(scorer.summarize)

    # 3. Convert to ObjectRecord (what gets serialized)
    obj_rec = pydantic_object_record(scorer)

    # 4. Map nested objects to their refs (score op -> score op ref, summarize op -> summarize op ref)
    mapped_obj_rec = map_to_refs(obj_rec)

    # 5. Finally serialize
    sdk_val = to_json(mapped_obj_rec, client._project_id(), client)

    # Extract the score op reference URI and summarize op ref from the serialized data
    score_op_ref_uri = sdk_val["score"]
    summarize_op_ref_uri = sdk_val["summarize"]
    column_map = sdk_val.get("column_map")

    # Build the scorer value using the helper function
    helper_val = object_creation_utils.build_scorer_val(
        name=scorer.name,
        description=scorer.description,
        score_op_ref=score_op_ref_uri,
        summarize_op_ref=summarize_op_ref_uri,
        column_map=column_map,
        class_name=scorer.__class__.__name__,
    )

    assert helper_val == sdk_val
