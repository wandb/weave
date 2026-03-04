"""Tests for object_creation_utils.py utilities.

These tests verify that the helper functions serialize objects in the same way
as the SDK.  Ideally they would be placed next to the trace_server tests, but
the client serialization requires a client object to serialize.
"""

import weave
from weave.evaluation.eval import Evaluation
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


def test_helper_serializes_evaluation_same_way_as_sdk(client: WeaveClient) -> None:
    """Test that helpers serialize an Evaluation with the correct structure.
    Note: The helper creates base Evaluation objects (not custom subclasses),
    so we compare the data fields rather than type metadata.
    """
    # Create test dataset
    dataset = weave.Dataset(
        name="eval_test_dataset",
        description="Test dataset for evaluation",
        rows=[
            {"question": "What is 2+2?", "expected": "4"},
            {"question": "What is the capital of France?", "expected": "Paris"},
        ],
    )

    class TestScorer(Scorer):
        @weave.op
        def score(self, *, output, **kwargs):  # type: ignore
            return {"score": 1.0}

    scorer = TestScorer(name="test_scorer", description="Test scorer")
    evaluation = Evaluation(
        name="test_evaluation",
        description="Test evaluation for serialization",
        dataset=dataset,
        scorers=[scorer],
        trials=3,
        evaluation_name="my_eval_run",
    )

    # Save the dataset to get a reference
    client._save_object(dataset, "eval_test_dataset")

    # Save the scorer ops to get references
    client._save_op(scorer.score)
    client._save_op(scorer.summarize)

    # Save the scorer to get a reference
    scorer_ref = client._save_object(scorer, "test_scorer")

    # Save evaluation ops to get references
    client._save_op(evaluation.evaluate)
    client._save_op(evaluation.predict_and_score)
    client._save_op(evaluation.summarize)

    # Convert to ObjectRecord (what gets serialized)
    obj_rec = pydantic_object_record(evaluation)

    # Map nested objects to their refs
    mapped_obj_rec = map_to_refs(obj_rec)

    # Finally serialize
    sdk_val = to_json(mapped_obj_rec, client._project_id(), client)

    # Extract references from the serialized data
    dataset_ref_uri = sdk_val["dataset"]
    scorers_refs = sdk_val.get("scorers", [])
    evaluate_ref = sdk_val["evaluate"]
    predict_and_score_ref = sdk_val["predict_and_score"]
    summarize_ref = sdk_val["summarize"]
    preprocess_model_input_ref = sdk_val.get("preprocess_model_input")

    # Build the evaluation value using the helper function
    helper_val = object_creation_utils.build_evaluation_val(
        name=evaluation.name,
        dataset_ref=dataset_ref_uri,
        trials=evaluation.trials,
        description=evaluation.description,
        scorer_refs=scorers_refs,
        evaluation_name=evaluation.evaluation_name,
        metadata=evaluation.metadata,
        preprocess_model_input=preprocess_model_input_ref,
        evaluate_ref=evaluate_ref,
        predict_and_score_ref=predict_and_score_ref,
        summarize_ref=summarize_ref,
    )

    assert helper_val == sdk_val


def test_make_safe_name_with_angle_brackets() -> None:
    """Test that make_safe_name correctly handles angle bracket characters.

    Tests various positions of < and > characters and verifies that ops can be
    successfully created with the sanitized names.
    """
    # Test cases with angle brackets in different positions
    # All should sanitize to "opname" after removing < and >
    test_cases = [
        "<opname",
        "opname>",
        "<opname>",
        "op<name",
        "op>name",
        "op<>name",
    ]

    for test_input in test_cases:
        # Apply make_safe_name to sanitize the input
        safe_name = object_creation_utils.make_safe_name(test_input)

        # Create an op with the safe name and verify it succeeds without error
        @weave.op(name=safe_name)
        def test_op(x: int) -> int:
            return x + 1

        # Verify the op was successfully created
        assert test_op.name == "opname", (
            f"Op creation failed for input '{test_input}': got name '{test_op.name}'"
        )


def test_make_safe_name_strips_all_invalid_characters() -> None:
    r"""Test that make_safe_name strips all characters invalid for object names.

    The object name validator only allows [\\w._-] (alphanumeric, underscore,
    dot, dash). make_safe_name must strip everything else so that downstream
    validation never rejects a sanitized name.
    """
    # Characters that previously slipped through and caused InvalidFieldError
    assert object_creation_utils.make_safe_name("prefix:suffix") == "prefixsuffix"
    assert object_creation_utils.make_safe_name("base64data==end") == "base64dataend"
    assert (
        object_creation_utils.make_safe_name(
            "weave-trace-internal:___abc123==_op_llen:xyz"
        )
        == "weave-trace-internal___abc123_op_llenxyz"
    )

    # Spaces and slashes become underscores; other invalid chars are removed
    assert object_creation_utils.make_safe_name("a b/c:d=e<f>g") == "a_b_cdefg"

    # Valid characters are preserved
    assert (
        object_creation_utils.make_safe_name("valid.name-123_ok") == "valid.name-123_ok"
    )

    # None becomes "unknown"
    assert object_creation_utils.make_safe_name(None) == "unknown"
