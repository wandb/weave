import datetime

import pytest

import weave
from tests.trace.util import NOT_CLICKHOUSE_BACKEND
from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    DummyIdConverter,
)
from weave import AnnotationSpec
from weave.trace.weave_client import WeaveClient, get_ref
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.common_interface import SortBy
from weave.trace_server.errors import (
    InvalidRequest,
    QueryIllegalTypeofArgumentError,
)
from weave.trace_server.feedback_agg_query_builder import (
    build_feedback_aggregate_query,
)
from weave.trace_server.interface.query import Query
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.trace_server_interface import (
    FeedbackAggregateBucket,
    FeedbackAggregateReq,
    FeedbackAggregateRes,
    FeedbackCreateReq,
    FeedbackQueryReq,
    FeedbackReplaceReq,
)


def test_client_feedback(client) -> None:
    feedbacks = client.get_feedback()
    assert len(feedbacks) == 0

    # Make three feedbacks on two calls
    call1 = client.create_call("x", {"a": 5, "b": 10})
    client.finish_call(call1, "hello1")
    trace_object1 = client.get_call(call1.id)
    feedback_id_emoji = trace_object1.feedback.add_reaction("👍")
    trace_object1.feedback.add_note("this is a note on call1")

    call2 = client.create_call("x", {"a": 6, "b": 11})
    client.finish_call(call2, "hello2")
    trace_object2 = client.get_call(call2.id)
    feedback_id_note2 = trace_object2.feedback.add_note("this is a note on call2")

    # Check expectations
    feedbacks = client.get_feedback()
    assert len(feedbacks) == 3

    f = client.get_feedback(feedback_id_note2)[0]
    assert f.payload == {"note": "this is a note on call2"}

    f = client.get_feedback(reaction="👍")[0]
    assert f.id == feedback_id_emoji

    assert len(client.get_feedback(limit=1)) == 1

    # Purge a feedback
    assert len(trace_object2.feedback) == 1
    trace_object2.feedback.purge(feedback_id_note2)
    assert len(trace_object2.feedback) == 0
    feedbacks = client.get_feedback()
    assert len(feedbacks) == 2


def test_custom_feedback(client) -> None:
    feedbacks = client.get_feedback()
    assert len(feedbacks) == 0

    # Add custom feedback to call
    call = client.create_call("x", {"a": 5, "b": 10})
    client.finish_call(call, "hello1")
    trace_object = client.get_call(call.id)
    feedback_id1 = trace_object.feedback.add("correctness", {"value": 4})
    feedback_id2 = trace_object.feedback.add("hallucination", value=0.5)

    # Check expectations
    feedbacks = client.get_feedback()
    assert len(feedbacks) == 2

    f = client.get_feedback(feedback_id1)[0]
    assert f.feedback_type == "correctness"
    assert f.payload["value"] == 4

    f = client.get_feedback(feedback_id2)[0]
    assert f.feedback_type == "hallucination"
    assert f.payload["value"] == 0.5

    with pytest.raises(ValueError, match="reserved for annotation feedback"):
        trace_object.feedback.add("wandb.trying_to_use_reserved_prefix", value=1)


def test_annotation_feedback(client: WeaveClient) -> None:
    project_id = client.project_id
    column_name = "column_name"
    feedback_type = f"wandb.annotation.{column_name}"
    weave_ref = f"weave:///{project_id}/call/cal_id_123"

    payload = {"value": 1}

    ref = weave.publish(AnnotationSpec(name=column_name, field_schema=int))
    annotation_ref = ref.uri

    # Case 1: Errors with no name in type (dangle or char len 0)
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="wandb.annotation",  # No name
                payload=payload,
                annotation_ref=annotation_ref,
            )
        )

    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="wandb.annotation.",  # Trailing period
                payload=payload,
                annotation_ref=annotation_ref,
            )
        )
    # Case 2: Errors with incorrect ref string format
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload=payload,
                annotation_ref=f"weave:///{project_id}/object/{column_name}",  # No digest
            )
        )
    # Case 3: Errors with name mismatch
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type + "_wrong_name",
                payload=payload,
                annotation_ref=annotation_ref,
            )
        )
    # Case 4: Errors if annotation ref is present but incorrect type
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="not.annotation",
                payload=payload,
                annotation_ref=f"weave:///{project_id}/op/{column_name}:obj_id_123",
            )
        )

    # Case 5: Invalid payload
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload={"not": "a valid payload"},
                annotation_ref=annotation_ref,
            )
        )

    # Success
    create_res = client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type=feedback_type,
            payload=payload,
            annotation_ref=annotation_ref,
        )
    )
    assert create_res.id is not None
    # Correct Query Result Payload
    query_res = client.server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
        )
    )
    assert len(query_res.result) == 1
    assert query_res.result[0] == {
        "id": create_res.id,
        "project_id": project_id,
        "weave_ref": weave_ref,
        "wb_user_id": "shawn",
        "creator": None,
        "created_at": MatchAnyDatetime(),
        "feedback_type": feedback_type,
        "payload": payload,
        "annotation_ref": annotation_ref,
        "runnable_ref": None,
        "call_ref": None,
        "trigger_ref": None,
        "queue_id": None,
        "scorer_tags": [],
        "scorer_tag_reasons": {},
        "scorer_tag_confidences": {},
        "scorer_ratings": {},
        "scorer_rating_reasons": {},
        "scorer_rating_confidences": {},
        "span_agent_name": "",
        "span_agent_version": "",
        "span_status_code": "UNSET",
        "span_conversation_id": "",
        "span_trace_id": "",
        "scorer_trace_id": "",
    }


@pytest.mark.parametrize(
    "bad_spec",
    [None, {"field_schema": None}, "not-a-spec"],
    ids=["null_spec", "null_field_schema", "scalar"],
)
def test_annotation_feedback_malformed_spec_is_invalid_request(
    client: WeaveClient, bad_spec: object
) -> None:
    """A malformed annotation spec yields InvalidRequest, not an unhandled 500 (WB-35940)."""
    project_id = client.project_id
    column_name = "malformed_spec"
    digest = client.server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=project_id, object_id=column_name, val=bad_spec
            )
        )
    ).digest
    annotation_ref = f"weave:///{project_id}/object/{column_name}:{digest}"

    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=f"weave:///{project_id}/call/call_id_123",
                feedback_type=f"wandb.annotation.{column_name}",
                payload={"value": 1},
                annotation_ref=annotation_ref,
            )
        )


def test_runnable_feedback(client: WeaveClient) -> None:
    """Test feedback creation with runnable references."""
    project_id = client.project_id
    runnable_name = "runnable_name"
    feedback_type = f"wandb.runnable.{runnable_name}"
    weave_ref = f"weave:///{project_id}/call/cal_id_123"
    runnable_ref = f"weave:///{project_id}/op/{runnable_name}:op_id_123"
    call_ref = f"weave:///{project_id}/call/call_id_123"
    trigger_ref = f"weave:///{project_id}/object/{runnable_name}:trigger_id_123"
    payload = {"output": 1}

    # Case 1: Errors with no name in type (dangle or char len 0)
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="wandb.runnable",  # No name
                payload=payload,
                runnable_ref=runnable_ref,
            )
        )

    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="wandb.runnable.",  # Trailing period
                payload=payload,
                runnable_ref=runnable_ref,
            )
        )

    # Case 2: Errors with incorrect ref string format
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload=payload,
                runnable_ref=f"weave:///{project_id}/op/{runnable_name}",  # No digest
            )
        )

    # Case 3: Errors with name mismatch
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type + "_wrong_name",
                payload=payload,
                runnable_ref=runnable_ref,
            )
        )

    # Case 4: Errors if runnable ref is present but incorrect type
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="not.runnable",  # Wrong type
                payload=payload,
                runnable_ref=runnable_ref,  # Wrong type
            )
        )

    # Case 5: Errors if call ref is present but incorrect type
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="not.runnable",  # Wrong type
                payload=payload,
                call_ref=call_ref,
            )
        )

    # Case 6: Errors if trigger ref is present but incorrect type
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="not.runnable",
                payload=payload,
                trigger_ref=trigger_ref,
            )
        )

    # Case 7: Invalid payload
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload={"not": "a valid payload"},
                runnable_ref=runnable_ref,
                call_ref=call_ref,
                trigger_ref=trigger_ref,
            )
        )

    # Success
    create_res = client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type=feedback_type,
            payload=payload,
            runnable_ref=runnable_ref,
            call_ref=call_ref,
            trigger_ref=trigger_ref,
        )
    )
    assert create_res.id is not None

    # Verify Query Result Payload
    query_res = client.server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
        )
    )
    assert len(query_res.result) == 1
    assert query_res.result[0] == {
        "id": create_res.id,
        "project_id": project_id,
        "weave_ref": weave_ref,
        "wb_user_id": "shawn",
        "creator": None,
        "created_at": MatchAnyDatetime(),
        "feedback_type": feedback_type,
        "payload": payload,
        "annotation_ref": None,
        "runnable_ref": runnable_ref,
        "call_ref": call_ref,
        "trigger_ref": trigger_ref,
        "queue_id": None,
        "scorer_tags": [],
        "scorer_tag_reasons": {},
        "scorer_tag_confidences": {},
        "scorer_ratings": {},
        "scorer_rating_reasons": {},
        "scorer_rating_confidences": {},
        "span_agent_name": "",
        "span_agent_version": "",
        "span_status_code": "UNSET",
        "span_conversation_id": "",
        "span_trace_id": "",
        "scorer_trace_id": "",
    }

    # Runnable scorer feedback may also populate typed scorer columns while
    # keeping the raw scorer output in payload for backwards compatibility.
    typed_weave_ref = f"weave:///{project_id}/call/call_id_456"
    typed_create_res = client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=typed_weave_ref,
            feedback_type=feedback_type,
            payload={"output": {"passed": False}},
            runnable_ref=runnable_ref,
            call_ref=call_ref,
            trigger_ref=trigger_ref,
            scorer_tags=["unsafe"],
            scorer_tag_reasons={"unsafe": "contains disallowed content"},
            scorer_tag_confidences={"unsafe": 0.91},
            scorer_ratings={"_rating_": 0.2},
            scorer_rating_reasons={"_rating_": "low quality response"},
            scorer_rating_confidences={"_rating_": 0.88},
        )
    )

    typed_query_res = client.server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
            query=Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "id"},
                            {"$literal": typed_create_res.id},
                        ]
                    }
                }
            ),
        )
    )
    assert len(typed_query_res.result) == 1
    typed_row = typed_query_res.result[0]
    assert typed_row["feedback_type"] == feedback_type
    assert typed_row["payload"] == {"output": {"passed": False}}
    assert typed_row["scorer_tags"] == ["unsafe"]
    assert typed_row["scorer_tag_reasons"] == {"unsafe": "contains disallowed content"}
    assert typed_row["scorer_tag_confidences"] == {"unsafe": 0.91}
    assert typed_row["scorer_ratings"] == {"_rating_": 0.2}
    assert typed_row["scorer_rating_reasons"] == {"_rating_": "low quality response"}
    assert typed_row["scorer_rating_confidences"] == {"_rating_": 0.88}


def test_agent_monitor_feedback(client: WeaveClient) -> None:
    """End-to-end create/query for wandb.agent_monitor feedback with typed scorer columns."""
    project_id = client.project_id
    feedback_type = "wandb.agent_monitor"
    weave_ref = f"weave:///{project_id}/call/call_id_123"
    runnable_name = "my_scorer"
    runnable_ref = f"weave:///{project_id}/object/{runnable_name}:obj_id_123"
    call_ref = f"weave:///{project_id}/call/call_id_123"
    trigger_ref = f"weave:///{project_id}/object/{runnable_name}:trigger_id_123"
    payload = {"value": ["nsfw"], "reason": ["explicit language"]}

    # Case 1: runnable_ref is required.
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload=payload,
                scorer_tags=["nsfw"],
            )
        )

    # Case 2: call_ref is required.
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload=payload,
                runnable_ref=runnable_ref,
            )
        )

    # Case 3: trigger_ref is required.
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload=payload,
                runnable_ref=runnable_ref,
                call_ref=call_ref,
            )
        )

    # Case 4: scorer_* fields rejected on feedback that is neither agent-monitor
    # nor runnable (non-empty value).
    with pytest.raises(InvalidRequest):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="custom",
                payload={},
                scorer_tags=["nsfw"],
            )
        )

    # Success: write tags, a rating, and reasons/confidences keyed by name.
    create_res = client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type=feedback_type,
            payload=payload,
            runnable_ref=runnable_ref,
            call_ref=call_ref,
            trigger_ref=trigger_ref,
            scorer_tags=["nsfw", "high-quality"],
            scorer_tag_reasons={"nsfw": "explicit language"},
            scorer_tag_confidences={"nsfw": 0.95},
            scorer_ratings={"_rating_": 0.87},
            scorer_rating_reasons={"_rating_": "very confident response"},
            scorer_rating_confidences={"_rating_": 0.92},
            span_agent_name="midi-generator",
            span_agent_version="1.2.0",
            span_status_code="OK",
        )
    )
    assert create_res.id is not None

    query_res = client.server.feedback_query(
        tsi.FeedbackQueryReq(project_id=project_id)
    )
    assert len(query_res.result) == 1
    row = query_res.result[0]
    assert row["feedback_type"] == feedback_type
    assert row["payload"] == payload
    assert row["scorer_tags"] == ["nsfw", "high-quality"]
    assert row["scorer_tag_reasons"] == {"nsfw": "explicit language"}
    assert row["scorer_tag_confidences"] == {"nsfw": 0.95}
    assert row["scorer_ratings"] == {"_rating_": 0.87}
    assert row["scorer_rating_reasons"] == {"_rating_": "very confident response"}
    assert row["scorer_rating_confidences"] == {"_rating_": 0.92}
    assert row["span_agent_name"] == "midi-generator"
    assert row["span_agent_version"] == "1.2.0"
    assert row["span_status_code"] == "OK"


def test_agent_monitor_feedback_empty_defaults(client: WeaveClient) -> None:
    """A minimal agent_monitor row (no typed scorer fields) round-trips with empty defaults."""
    project_id = client.project_id
    weave_ref = f"weave:///{project_id}/call/call_id_123"
    runnable_ref = f"weave:///{project_id}/object/my_scorer:obj_id_123"
    call_ref = f"weave:///{project_id}/call/call_id_123"
    trigger_ref = f"weave:///{project_id}/object/my_scorer:trigger_id_123"

    create_res = client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type="wandb.agent_monitor",
            payload={"value": None},
            runnable_ref=runnable_ref,
            call_ref=call_ref,
            trigger_ref=trigger_ref,
        )
    )
    assert create_res.id is not None

    query_res = client.server.feedback_query(
        tsi.FeedbackQueryReq(project_id=project_id)
    )
    assert query_res.result[0]["scorer_tags"] == []
    assert query_res.result[0]["scorer_tag_reasons"] == {}
    assert query_res.result[0]["scorer_tag_confidences"] == {}
    assert query_res.result[0]["scorer_ratings"] == {}
    assert query_res.result[0]["scorer_rating_reasons"] == {}
    assert query_res.result[0]["scorer_rating_confidences"] == {}
    assert query_res.result[0]["span_agent_name"] == ""
    assert query_res.result[0]["span_agent_version"] == ""
    assert query_res.result[0]["span_status_code"] == "UNSET"


def test_agent_user_feedback(client: WeaveClient) -> None:
    """A human agent score's value is a tag in scorer_tags (e.g. an emoji
    glyph), carrying no scorer refs. Non-emoji tags are allowed too.
    """
    project_id = client.project_id
    feedback_type = "wandb.agent_user_feedback"
    weave_ref = f"weave:///{project_id}/object/agent_turn:turn_id_123"

    create_res = client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type=feedback_type,
            payload={"emoji": "👍", "scorer_tags": ["👍"]},
            scorer_tags=["👍"],
            # Denormalized agent metadata the UI attaches for dashboard filtering.
            span_agent_name="support-bot",
            span_agent_version="1.2.0",
            span_status_code="OK",
        )
    )
    assert create_res.id is not None

    query_res = client.server.feedback_query(
        tsi.FeedbackQueryReq(project_id=project_id)
    )
    assert len(query_res.result) == 1
    row = query_res.result[0]
    assert row["feedback_type"] == feedback_type
    assert row["scorer_tags"] == ["👍"]
    assert row["runnable_ref"] is None
    assert row["trigger_ref"] is None
    assert row["scorer_ratings"] == {}
    assert row["span_agent_name"] == "support-bot"
    assert row["span_agent_version"] == "1.2.0"
    assert row["span_status_code"] == "OK"


def test_agent_monitor_feedback_filters(client: WeaveClient) -> None:
    """Filter agent_monitor rows by typed scorer columns.

    Covers each access pattern the proposal calls out:
      - `$contains` on `scorer_tags` → array membership (`has` / `json_each`)
      - dotted access on `scorer_ratings.<name>` → typed map value lookup
      - dotted access on `scorer_tag_reasons.<name>` for reason equality
    """
    project_id = client.project_id
    runnable_ref = f"weave:///{project_id}/object/my_scorer:obj_id_123"
    call_ref = f"weave:///{project_id}/call/call_id_123"
    trigger_ref = f"weave:///{project_id}/object/my_scorer:trigger_id_123"

    def _create(weave_ref_suffix: str, **scorer_kwargs):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=f"weave:///{project_id}/call/{weave_ref_suffix}",
                feedback_type="wandb.agent_monitor",
                payload={"value": scorer_kwargs.get("scorer_tags", [])},
                runnable_ref=runnable_ref,
                call_ref=call_ref,
                trigger_ref=trigger_ref,
                **scorer_kwargs,
            )
        )

    _create("a", scorer_tags=["nsfw"], scorer_ratings={"_rating_": 0.9})
    _create(
        "b",
        scorer_tags=["high-quality"],
        scorer_ratings={"_rating_": 0.4},
        scorer_tag_reasons={"high-quality": "well formatted"},
    )
    _create("c")  # empty defaults

    def _query(query_dict) -> list[dict]:
        res = client.server.feedback_query(
            tsi.FeedbackQueryReq(project_id=project_id, query=Query(**query_dict))
        )
        return res.result

    # $contains on scorer_tags — must use array membership, not substring.
    matches = _query(
        {
            "$expr": {
                "$contains": {
                    "input": {"$getField": "scorer_tags"},
                    "substr": {"$literal": "nsfw"},
                }
            }
        }
    )
    assert {m["weave_ref"].rsplit("/", 1)[-1] for m in matches} == {"a"}

    # Substring-style false positive should NOT match. "ns" appears inside
    # "nsfw" but `has()` requires exact tag equality.
    matches = _query(
        {
            "$expr": {
                "$contains": {
                    "input": {"$getField": "scorer_tags"},
                    "substr": {"$literal": "ns"},
                }
            }
        }
    )
    assert matches == []

    # case_insensitive $contains must still match. Without the case-insensitive
    # branch the array path falls back to exact equality and misses tags that
    # differ only in case.
    _create("upper", scorer_tags=["NSFW"])
    matches = _query(
        {
            "$expr": {
                "$contains": {
                    "input": {"$getField": "scorer_tags"},
                    "substr": {"$literal": "nsfw"},
                    "case_insensitive": True,
                }
            }
        }
    )
    assert {m["weave_ref"].rsplit("/", 1)[-1] for m in matches} == {"a", "upper"}

    # Map value lookup with numeric comparison.
    matches = _query(
        {
            "$expr": {
                "$gt": [
                    {"$getField": "scorer_ratings._rating_"},
                    {"$literal": 0.5},
                ]
            }
        }
    )
    assert {m["weave_ref"].rsplit("/", 1)[-1] for m in matches} == {"a"}

    # Map value lookup on scorer_tag_reasons keyed by tag name.
    matches = _query(
        {
            "$expr": {
                "$eq": [
                    {"$getField": "scorer_tag_reasons.high-quality"},
                    {"$literal": "well formatted"},
                ]
            }
        }
    )
    assert {m["weave_ref"].rsplit("/", 1)[-1] for m in matches} == {"b"}

    # Regression: ClickHouse Map(*, Float64) returns 0 for missing keys,
    # which would otherwise match `== 0` filters and surface every row
    # without a rating as a "zero rating" row. Row 'c' has no rating and
    # must not match an equality-against-zero filter.
    matches = _query(
        {
            "$expr": {
                "$eq": [
                    {"$getField": "scorer_ratings._rating_"},
                    {"$literal": 0},
                ]
            }
        }
    )
    assert matches == []

    # Same regression for Map(*, String) — missing keys would otherwise
    # read as "" and match an `== ""` filter.
    matches = _query(
        {
            "$expr": {
                "$eq": [
                    {"$getField": "scorer_tag_reasons.missing"},
                    {"$literal": ""},
                ]
            }
        }
    )
    assert matches == []


def test_feedback_aggregate(client: WeaveClient) -> None:
    """Aggregate scorer feedback, asserting the entire FeedbackAggregateRes shape.

    Uses sumMap / toStartOfInterval. Ratings are
    exact binary fractions (0.75, 0.5) so the summed Float64 (1.25) compares
    exactly without approx. Covers both a time-bucketed query and several
    unbucketed (whole-range rollup) queries.
    """
    project_id = client.project_id
    now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    after_ms = now_ms - 3_600_000
    before_ms = now_ms + 3_600_000

    scorer_a = f"weave:///{project_id}/object/scorer_a:obj_id_a"
    scorer_b = f"weave:///{project_id}/object/scorer_b:obj_id_b"
    call_ref = f"weave:///{project_id}/call/call_id_123"
    trigger_ref = f"weave:///{project_id}/object/my_scorer:trigger_id_123"

    def _create(suffix: str, runnable_ref: str, **scorer_kwargs):
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=f"weave:///{project_id}/call/{suffix}",
                feedback_type="wandb.agent_monitor",
                payload={"value": scorer_kwargs.get("scorer_tags", [])},
                runnable_ref=runnable_ref,
                call_ref=call_ref,
                trigger_ref=trigger_ref,
                **scorer_kwargs,
            )
        )

    # Scorer A: two rated rows (one also tagged) + one row that scored nothing
    # (so total_count > scored_count). Scorer B: one tagged row, no rating.
    _create(
        "a1",
        scorer_a,
        scorer_ratings={"_rating_": 0.75},
        scorer_tags=["good"],
        span_status_code="OK",
    )
    _create("a2", scorer_a, scorer_ratings={"_rating_": 0.5}, span_status_code="OK")
    _create("a3", scorer_a)  # no tags, no rating; span_status_code defaults to UNSET
    _create("b1", scorer_b, scorer_tags=["nsfw", "slow"], span_status_code="ERROR")
    # A non-agent-monitor row that must be excluded by the feedback_type filter.
    client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref=f"weave:///{project_id}/call/note",
            feedback_type="wandb.note.1",
            payload={"note": "ignore me"},
        )
    )

    # Per-scorer rollups, reused as the expected buckets across the cases below.
    # Grouping by scorer_id returns the scorer's object id (the name), not a ref.
    scorer_a_bucket = FeedbackAggregateBucket(
        time_bucket_start_ms=None,
        group={"scorer_id": "scorer_a"},
        total_count=3,  # a1, a2, a3
        scored_count=2,  # a3 emitted no tag/rating
        tag_counts={"good": 1},
        rating_counts={"_rating_": 2},
        rating_sums={"_rating_": 1.25},  # 0.75 + 0.5
    )
    scorer_b_bucket = FeedbackAggregateBucket(
        time_bucket_start_ms=None,
        group={"scorer_id": "scorer_b"},
        total_count=1,
        scored_count=1,
        tag_counts={"nsfw": 1, "slow": 1},
        rating_counts={},
        rating_sums={},
    )

    # --- Time-bucketed, grouped by scorer ---
    # All rows are written ~now, so they share one epoch-aligned 1h bucket.
    bucket_ms = 3600 * 1000
    expected_bucket_start = (now_ms // bucket_ms) * bucket_ms
    bucketed = client.server.feedback_aggregate(
        FeedbackAggregateReq(
            project_id=project_id,
            after_ms=after_ms,
            before_ms=before_ms,
            time_bucket_seconds=3600,
            feedback_types=["wandb.agent_monitor"],
            group_by=["scorer_id"],
        )
    )
    # ORDER BY bucket leaves rows in the same bucket unordered; sort by scorer for
    # a stable shape. (A rare run straddling the hour boundary fails loudly here.)
    bucketed.buckets.sort(key=lambda b: b.group["scorer_id"])
    assert bucketed == FeedbackAggregateRes(
        time_bucket_seconds=3600,
        after_ms=after_ms,
        before_ms=before_ms,
        buckets=[
            scorer_a_bucket.model_copy(
                update={"time_bucket_start_ms": expected_bucket_start}
            ),
            scorer_b_bucket.model_copy(
                update={"time_bucket_start_ms": expected_bucket_start}
            ),
        ],
    )

    # --- Unbucketed, grouped by scorer (ORDER BY scorer_id is deterministic) ---
    assert client.server.feedback_aggregate(
        FeedbackAggregateReq(
            project_id=project_id,
            after_ms=after_ms,
            before_ms=before_ms,
            feedback_types=["wandb.agent_monitor"],
            group_by=["scorer_id"],
        )
    ) == FeedbackAggregateRes(
        time_bucket_seconds=None,
        after_ms=after_ms,
        before_ms=before_ms,
        buckets=[scorer_a_bucket, scorer_b_bucket],
    )

    # --- Unbucketed, grouped by the span_status_code Enum8 column ---
    # Enum8 ORDER BY is by numeric value, not name, so sort by status for a
    # stable shape. UNSET (a3) scored nothing -> scored_count 0.
    by_status = client.server.feedback_aggregate(
        FeedbackAggregateReq(
            project_id=project_id,
            after_ms=after_ms,
            before_ms=before_ms,
            feedback_types=["wandb.agent_monitor"],
            group_by=["span_status_code"],
        )
    )
    by_status.buckets.sort(key=lambda b: b.group["span_status_code"])
    assert by_status == FeedbackAggregateRes(
        time_bucket_seconds=None,
        after_ms=after_ms,
        before_ms=before_ms,
        buckets=[
            FeedbackAggregateBucket(
                time_bucket_start_ms=None,
                group={"span_status_code": "ERROR"},
                total_count=1,
                scored_count=1,
                tag_counts={"nsfw": 1, "slow": 1},
                rating_counts={},
                rating_sums={},
            ),
            FeedbackAggregateBucket(
                time_bucket_start_ms=None,
                group={"span_status_code": "OK"},
                total_count=2,
                scored_count=2,
                tag_counts={"good": 1},
                rating_counts={"_rating_": 2},
                rating_sums={"_rating_": 1.25},
            ),
            FeedbackAggregateBucket(
                time_bucket_start_ms=None,
                group={"span_status_code": "UNSET"},
                total_count=1,
                scored_count=0,
                tag_counts={},
                rating_counts={},
                rating_sums={},
            ),
        ],
    )

    # --- Unbucketed, no group_by: one global rollup row over all matched rows ---
    assert client.server.feedback_aggregate(
        FeedbackAggregateReq(
            project_id=project_id,
            after_ms=after_ms,
            before_ms=before_ms,
            feedback_types=["wandb.agent_monitor"],
        )
    ) == FeedbackAggregateRes(
        time_bucket_seconds=None,
        after_ms=after_ms,
        before_ms=before_ms,
        buckets=[
            FeedbackAggregateBucket(
                time_bucket_start_ms=None,
                group={},
                total_count=4,  # a1, a2, a3, b1
                scored_count=3,  # a3 emitted nothing
                tag_counts={"good": 1, "nsfw": 1, "slow": 1},
                rating_counts={"_rating_": 2},
                rating_sums={"_rating_": 1.25},
            ),
        ],
    )

    # --- Time-bucketed, no group_by: the same global rollup, but one row per time
    # bucket carrying its timestamp (group stays empty). All rows share one 1h
    # bucket, so a single row comes back. ---
    assert client.server.feedback_aggregate(
        FeedbackAggregateReq(
            project_id=project_id,
            after_ms=after_ms,
            before_ms=before_ms,
            time_bucket_seconds=3600,
            feedback_types=["wandb.agent_monitor"],
        )
    ) == FeedbackAggregateRes(
        time_bucket_seconds=3600,
        after_ms=after_ms,
        before_ms=before_ms,
        buckets=[
            FeedbackAggregateBucket(
                time_bucket_start_ms=expected_bucket_start,
                group={},
                total_count=4,
                scored_count=3,
                tag_counts={"good": 1, "nsfw": 1, "slow": 1},
                rating_counts={"_rating_": 2},
                rating_sums={"_rating_": 1.25},
            ),
        ],
    )

    # --- All-time total: a from-the-epoch range that exceeds the usual 31-day cap.
    # Past the cap only a bare project-wide total is allowed (no bucket, no
    # group_by, no filters), so this rolls up EVERY feedback row in the project --
    # including the non-agent-monitor note (total 5, not 4). ---
    assert client.server.feedback_aggregate(
        FeedbackAggregateReq(
            project_id=project_id,
            after_ms=0,
            before_ms=before_ms,
        )
    ) == FeedbackAggregateRes(
        time_bucket_seconds=None,
        after_ms=0,
        before_ms=before_ms,
        buckets=[
            FeedbackAggregateBucket(
                time_bucket_start_ms=None,
                group={},
                total_count=5,  # 4 agent_monitor rows + the note
                scored_count=3,  # a3 and the note emitted nothing
                tag_counts={"good": 1, "nsfw": 1, "slow": 1},
                rating_counts={"_rating_": 2},
                rating_sums={"_rating_": 1.25},
            ),
        ],
    )

    # --- Filter: scorer_ids match the scorer's id exactly, so "scorer_a" selects
    # only scorer A. A trailing "*" opts into prefix matching, which here yields
    # the same single scorer.
    for scorer_filter in ("scorer_a", "scorer_a*"):
        assert client.server.feedback_aggregate(
            FeedbackAggregateReq(
                project_id=project_id,
                after_ms=after_ms,
                before_ms=before_ms,
                feedback_types=["wandb.agent_monitor"],
                scorer_ids=[scorer_filter],
                group_by=["scorer_id"],
            )
        ) == FeedbackAggregateRes(
            time_bucket_seconds=None,
            after_ms=after_ms,
            before_ms=before_ms,
            buckets=[scorer_a_bucket],
        ), scorer_filter

    # --- Filter: tags keeps rows whose scorer_tags include "nsfw" (just b1); the
    # rollup still counts all of that row's tags. ---
    assert client.server.feedback_aggregate(
        FeedbackAggregateReq(
            project_id=project_id,
            after_ms=after_ms,
            before_ms=before_ms,
            feedback_types=["wandb.agent_monitor"],
            tags=["nsfw"],
            group_by=["scorer_id"],
        )
    ) == FeedbackAggregateRes(
        time_bucket_seconds=None,
        after_ms=after_ms,
        before_ms=before_ms,
        buckets=[scorer_b_bucket],
    )

    # --- Filter: rating_min keeps rows whose _rating_ >= 0.7 (just a1 at 0.75);
    # a2 (0.5) and the rating-less rows drop out. ---
    assert client.server.feedback_aggregate(
        FeedbackAggregateReq(
            project_id=project_id,
            after_ms=after_ms,
            before_ms=before_ms,
            feedback_types=["wandb.agent_monitor"],
            rating_min=0.7,
        )
    ) == FeedbackAggregateRes(
        time_bucket_seconds=None,
        after_ms=after_ms,
        before_ms=before_ms,
        buckets=[
            FeedbackAggregateBucket(
                time_bucket_start_ms=None,
                group={},
                total_count=1,
                scored_count=1,
                tag_counts={"good": 1},
                rating_counts={"_rating_": 1},
                rating_sums={"_rating_": 0.75},
            ),
        ],
    )


def test_agent_monitor_feedback_sort_by_map_column(client: WeaveClient) -> None:
    """Sorting by a map-column key (e.g. `scorer_ratings._rating_`) must work.

    Regression: the ORDER BY path used to pass the field name into the
    function's `cast` slot, which silently no-op'd for pre-existing column
    types but raised on the new map_string_string branch. Locks in the
    fix so future refactors don't reintroduce that mismatch.
    """
    project_id = client.project_id
    runnable_ref = f"weave:///{project_id}/object/my_scorer:obj_id_123"
    call_ref = f"weave:///{project_id}/call/call_id_123"
    trigger_ref = f"weave:///{project_id}/object/my_scorer:trigger_id_123"

    # Reasons in alphabetical order match the rating order so a single
    # set of rows exercises both Map(*, Float64) and Map(*, String) sorts.
    rows = [
        ("low", 0.1, "alpha"),
        ("mid", 0.5, "beta"),
        ("high", 0.9, "gamma"),
    ]
    for suffix, rating, reason in rows:
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=f"weave:///{project_id}/call/{suffix}",
                feedback_type="wandb.agent_monitor",
                payload={"value": rating},
                runnable_ref=runnable_ref,
                call_ref=call_ref,
                trigger_ref=trigger_ref,
                scorer_ratings={"_rating_": rating},
                scorer_rating_reasons={"_rating_": reason},
            )
        )

    asc = client.server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
            sort_by=[SortBy(field="scorer_ratings._rating_", direction="asc")],
        )
    )
    assert [r["weave_ref"].rsplit("/", 1)[-1] for r in asc.result] == [
        "low",
        "mid",
        "high",
    ]

    desc = client.server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
            sort_by=[SortBy(field="scorer_ratings._rating_", direction="desc")],
        )
    )
    assert [r["weave_ref"].rsplit("/", 1)[-1] for r in desc.result] == [
        "high",
        "mid",
        "low",
    ]

    by_reason = client.server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
            sort_by=[SortBy(field="scorer_rating_reasons._rating_", direction="asc")],
        )
    )
    assert [r["weave_ref"].rsplit("/", 1)[-1] for r in by_reason.result] == [
        "low",
        "mid",
        "high",
    ]


async def populate_feedback(client: WeaveClient) -> None:
    @weave.op
    def my_scorer(x: int, output: int) -> int:
        expected = ["a", "b", "c", "d"][x]
        return {
            "model_output": output,
            "expected": expected,
            "match": output == expected,
            "score": x + 0.5,
        }

    @weave.op
    def my_model(x: int) -> str:
        return [
            "a",
            "x",  # intentional "mistake"
            "c",
            "y",  # intentional "mistake"
        ][x]

    ids = []
    for x in range(4):
        _, c = my_model.call(x)
        ids.append(c.id)
        await c.apply_scorer(my_scorer)
    client.flush()

    assert len(list(my_scorer.calls())) == 4
    assert len(list(my_model.calls())) == 4

    return ids, my_scorer, my_model


@pytest.mark.asyncio
async def test_sort_by_feedback(client: WeaveClient, no_autoflush) -> None:
    """Test sorting by feedback."""
    ids, my_scorer, my_model = await populate_feedback(client)

    for fields, asc_ids in [
        (
            ["feedback.[wandb.runnable.my_scorer].payload.output.model_output"],
            [ids[0], ids[2], ids[1], ids[3]],
        ),
        (
            ["feedback.[wandb.runnable.my_scorer].payload.output.expected"],
            [ids[0], ids[1], ids[2], ids[3]],
        ),
        (
            [
                "feedback.[wandb.runnable.my_scorer].payload.output.match",
                "feedback.[wandb.runnable.my_scorer].payload.output.model_output",
            ],
            [ids[1], ids[3], ids[0], ids[2]],
        ),
    ]:
        calls = client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri]),
                sort_by=[
                    SortBy(
                        field=field,
                        direction="asc",
                    )
                    for field in fields
                ],
            )
        )

        found_ids = [c.id for c in calls]
        assert found_ids == asc_ids, (
            f"Sorting by {fields} ascending failed, expected {asc_ids}, got {found_ids}"
        )

        calls = client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri]),
                sort_by=[
                    SortBy(
                        field=field,
                        direction="desc",
                    )
                    for field in fields
                ],
            )
        )

        found_ids = [c.id for c in calls]
        assert found_ids == asc_ids[::-1], (
            f"Sorting by {fields} descending failed, expected {asc_ids[::-1]}, got {found_ids}"
        )


@pytest.mark.asyncio
async def test_filter_by_feedback(client: WeaveClient, no_autoflush) -> None:
    """Test filtering by feedback."""
    ids, my_scorer, my_model = await populate_feedback(client)
    for field, value, eq_ids, gt_ids in [
        (
            "feedback.[wandb.runnable.my_scorer].payload.output.model_output",
            "a",
            [ids[0]],
            [ids[1], ids[2], ids[3]],
        ),
        (
            "feedback.[wandb.runnable.my_scorer].payload.output.expected",
            "c",
            [ids[2]],
            [ids[3]],
        ),
        (
            "feedback.[wandb.runnable.my_scorer].payload.output.match",
            "false",
            [ids[1], ids[3]],
            [ids[0], ids[2]],
        ),
    ]:
        calls = client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri]),
                query={
                    "$expr": {
                        "$eq": [
                            {"$getField": field},
                            {"$literal": value},
                        ]
                    }
                },
            )
        )

        found_ids = [c.id for c in calls]
        assert found_ids == eq_ids, (
            f"Filtering by {field} == {value} failed, expected {eq_ids}, got {found_ids}"
        )

        calls = client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri]),
                query={
                    "$expr": {
                        "$gt": [
                            {"$getField": field},
                            {"$literal": value},
                        ]
                    }
                },
            )
        )

        found_ids = [c.id for c in calls]
        assert found_ids == gt_ids, (
            f"Filtering by {field} > {value} failed, expected {gt_ids}, got {found_ids}"
        )

    for field, value, expected_ids in [
        (
            "feedback.[wandb.runnable.my_scorer].payload.output.match",
            True,
            [ids[0], ids[2]],
        ),
        (
            "feedback.[wandb.runnable.my_scorer].payload.output.score",
            1.5,
            [ids[2], ids[3]],
        ),
    ]:
        operation = "$gt" if isinstance(value, float) else "$eq"
        calls = client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri]),
                query={
                    "$expr": {
                        operation: [
                            {"$getField": field},
                            {"$literal": value},
                        ]
                    }
                },
            )
        )
        found_ids = [c.id for c in calls]
        assert found_ids == expected_ids, (
            f"Typed filtering by {field} with {value} failed, expected {expected_ids}, got {found_ids}"
        )

    # Also test $contains on feedback fields (substring matching).
    # model_output values are: "a", "x", "c", "y" for ids[0..3].
    # expected values are: "a", "b", "c", "d" for ids[0..3].
    model_output_field = (
        "feedback.[wandb.runnable.my_scorer].payload.output.model_output"
    )
    model_ref = get_ref(my_model).uri
    for substr, expected_ids in [
        # "a" appears as model_output for ids[0] only
        ("a", [ids[0]]),
        # "x" appears as model_output for ids[1] only
        ("x", [ids[1]]),
    ]:
        calls = client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                filter=tsi.CallsFilter(op_names=[model_ref]),
                query={
                    "$expr": {
                        "$contains": {
                            "input": {"$getField": model_output_field},
                            "substr": {"$literal": substr},
                        }
                    }
                },
            )
        )

        found_ids = [c.id for c in calls]
        assert found_ids == expected_ids, (
            f"Filtering by {model_output_field} $contains '{substr}' failed, "
            f"expected {expected_ids}, got {found_ids}"
        )


@pytest.mark.skipif(
    NOT_CLICKHOUSE_BACKEND,
    reason="ClickHouse-only: executes the built SQL directly via server._query",
)
def test_feedback_aggregate_filter_matching_functional(client: WeaveClient) -> None:
    """Functional checks (ClickHouse-only) that the WHERE filters match precisely.

    The aggregate endpoint lands separately, so this executes the built query
    directly. Guards against over-broad matching that string assertions miss:
    object-id filters match the id exactly (a trailing '*' opts into prefix), and
    span_types matches the ref's span-type segment, not an arbitrary substring.
    """
    project_id = client.project_id
    now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    after_ms = now_ms - 3_600_000
    before_ms = now_ms + 3_600_000

    def _monitor(suffix: str, monitor_id: str, weave_ref: str) -> None:
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="wandb.agent_monitor",
                payload={"value": []},
                runnable_ref=f"weave:///{project_id}/object/scorer_{suffix}:obj_{suffix}",
                call_ref=f"weave:///{project_id}/call/{suffix}",
                trigger_ref=f"weave:///{project_id}/object/{monitor_id}:trig_{suffix}",
            )
        )

    # Two monitors whose ids share a prefix ("mon" vs "monday"), one scoring an
    # agent_turn ref and one an agent_conversation ref.
    _monitor("t1", "mon", f"weave:///{project_id}/agent_turn/trace_t1")
    _monitor("c1", "monday", f"weave:///{project_id}/agent_conversation/conv_c1")

    # feedback_create (via the external adapter) stores the internal project_id and
    # internalized refs; query against that internal id, not the external one.
    internal_project_id = DummyIdConverter().ext_to_int_project_id(project_id)

    def _total(**filters) -> int:
        """Run the aggregate (global rollup) and return the total matched rows."""
        pb = ParamBuilder()
        built = build_feedback_aggregate_query(
            FeedbackAggregateReq(
                project_id=internal_project_id,
                after_ms=after_ms,
                before_ms=before_ms,
                feedback_types=["wandb.agent_monitor"],
                **filters,
            ),
            pb,
        )
        result = client.server._query(built.sql, built.parameters)
        rows = [
            dict(zip(built.columns, row, strict=True)) for row in result.result_rows
        ]
        return sum(int(r["total_count"]) for r in rows)

    # Sanity: both rows are present absent any id/type filter.
    assert _total() == 2

    # monitor_ids: exact by default, so "mon" must NOT match "monday".
    assert _total(monitor_ids=["mon"]) == 1
    assert _total(monitor_ids=["monday"]) == 1
    assert _total(monitor_ids=["mond"]) == 0  # no partial match without '*'
    # A trailing '*' opts into prefix matching -> matches both ids.
    assert _total(monitor_ids=["mon*"]) == 2

    # span_types: matches the exact span-type segment of the ref, not a substring.
    assert _total(span_types=["agent_turn"]) == 1
    assert _total(span_types=["agent_conversation"]) == 1
    assert _total(span_types=["agent_turn", "agent_conversation"]) == 2


class MatchAnyDatetime:  # noqa: PLW1641
    def __eq__(self, other):
        return isinstance(other, datetime.datetime)


@pytest.mark.asyncio
async def test_filter_and_sort_by_feedback(client: WeaveClient, no_autoflush) -> None:
    """Test filtering and sorting by feedback."""
    ids, my_scorer, my_model = await populate_feedback(client)
    calls = client.server.calls_query_stream(
        tsi.CallsQueryReq(
            project_id=client.project_id,
            filter=tsi.CallsFilter(op_names=[get_ref(my_model).uri]),
            # Filter down to just correct matches
            query={
                "$expr": {
                    "$eq": [
                        {
                            "$getField": "feedback.[wandb.runnable.my_scorer].payload.output.match"
                        },
                        {"$literal": "true"},
                    ]
                }
            },
            # Sort by the model output desc
            sort_by=[
                {
                    "field": "feedback.[wandb.runnable.my_scorer].payload.output.model_output",
                    "direction": "desc",
                }
            ],
        )
    )
    calls = list(calls)
    assert len(calls) == 2
    assert [c.id for c in calls] == [ids[2], ids[0]]


@pytest.mark.asyncio
async def test_filter_by_wildcard_feedback_with_multiple_items(
    client: WeaveClient,
) -> None:
    """Test that wildcard feedback filtering finds values across multiple feedback entries.

    Each scorer writes to a unique nested path within its output. The wildcard
    feedback filter uses anyIf() to pick the non-empty value from whichever
    feedback row has data at the requested path.
    """

    @weave.op
    def my_scorer_a(x: int, output: str) -> dict:
        return {"scorer_a": {"is_match": True, "score": x * 10}}

    @weave.op
    def my_scorer_b(x: int, output: str) -> dict:
        return {"scorer_b": {"is_match": True, "score": x * 100}}

    @weave.op
    def my_model(x: int) -> str:
        return f"result_{x}"

    # Create 3 calls, each scored by both scorers
    ids = []
    for x in range(3):
        _, c = my_model.call(x)
        ids.append(c.id)
        await c.apply_scorer(my_scorer_a)
        await c.apply_scorer(my_scorer_b)

    model_ref = get_ref(my_model).uri

    # Each call now has 2 feedback items (one per scorer).
    # Each scorer writes to a unique key, so anyIf picks the non-empty value
    # from the correct feedback row.

    # Filter for scorer_b's is_match — should match all 3 calls.
    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                filter=tsi.CallsFilter(op_names=[model_ref]),
                query={
                    "$expr": {
                        "$eq": [
                            {
                                "$getField": "feedback.[*].payload.output.scorer_b.is_match"
                            },
                            {"$literal": "true"},
                        ]
                    }
                },
            )
        )
    )
    assert len(calls) == 3, (
        f"Expected all 3 calls to match wildcard filter for scorer_b.is_match, got {len(calls)}"
    )

    # Also verify scorer_a is findable via its own unique path
    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                filter=tsi.CallsFilter(op_names=[model_ref]),
                query={
                    "$expr": {
                        "$eq": [
                            {
                                "$getField": "feedback.[*].payload.output.scorer_a.is_match"
                            },
                            {"$literal": "true"},
                        ]
                    }
                },
            )
        )
    )
    assert len(calls) == 3, (
        f"Expected all 3 calls to match wildcard filter for scorer_a.is_match, got {len(calls)}"
    )

    # Filter using a specific scorer type (non-wildcard) still works
    calls = list(
        client.server.calls_query_stream(
            tsi.CallsQueryReq(
                project_id=client.project_id,
                filter=tsi.CallsFilter(op_names=[model_ref]),
                query={
                    "$expr": {
                        "$eq": [
                            {
                                "$getField": "feedback.[wandb.runnable.my_scorer_a].payload.output.scorer_a.is_match"
                            },
                            {"$literal": "true"},
                        ]
                    }
                },
            )
        )
    )
    assert len(calls) == 3, (
        f"Expected all 3 calls to match specific feedback type filter, got {len(calls)}"
    )


def test_feedback_replace(client) -> None:
    # Create initial feedback
    create_req = FeedbackCreateReq(
        project_id="test/project",
        weave_ref="weave:///test/project/obj/123:abc",
        feedback_type="reaction",
        payload={"emoji": "👍"},
        wb_user_id="test_user",
    )
    initial_feedback = client.server.feedback_create(create_req)

    # Create another feedback with different type
    note_feedback = client.server.feedback_create(
        FeedbackCreateReq(
            project_id="test/project",
            weave_ref="weave:///test/project/obj/456:def",
            feedback_type="note",
            payload={"note": "This is a test note"},
            wb_user_id="test_user",
        )
    )

    # Replace the first feedback with new content
    replace_req = FeedbackReplaceReq(
        project_id="test/project",
        weave_ref="weave:///test/project/obj/123:abc",
        feedback_type="note",
        payload={"note": "Updated feedback"},
        feedback_id=initial_feedback.id,
        wb_user_id="test_user",
    )
    replaced_feedback = client.server.feedback_replace(replace_req)

    # Verify the replacement
    assert note_feedback.id != replaced_feedback.id

    # Verify the other feedback remains unchanged
    query_res = client.server.feedback_query(
        FeedbackQueryReq(
            project_id="test/project", fields=["id", "feedback_type", "payload"]
        )
    )

    feedbacks = query_res.result
    assert len(feedbacks) == 2

    # Find the non-replaced feedback and verify it's unchanged
    other_feedback = next(f for f in feedbacks if f["id"] == note_feedback.id)
    assert other_feedback["feedback_type"] == "note"
    assert other_feedback["payload"] == {"note": "This is a test note"}

    # now replace the replaced feedback with the original content
    replace_req = FeedbackReplaceReq(
        project_id="test/project",
        weave_ref="weave:///test/project/obj/123:abc",
        feedback_type="reaction",
        payload={"emoji": "👍"},
        feedback_id=replaced_feedback.id,
        wb_user_id="test_user",
    )
    replaced_feedback = client.server.feedback_replace(replace_req)

    assert replaced_feedback.id != initial_feedback.id

    # Verify the latest feedback payload
    query_res = client.server.feedback_query(
        FeedbackQueryReq(
            project_id="test/project", fields=["id", "feedback_type", "payload"]
        )
    )
    feedbacks = query_res.result
    assert len(feedbacks) == 2
    new_feedback = next(f for f in feedbacks if f["id"] == replaced_feedback.id)
    assert new_feedback["feedback_type"] == "reaction"
    assert new_feedback["payload"] == {"emoji": "👍"}


def test_feedback_replace_validates_before_purge(client) -> None:
    """Replace must reject invalid payloads BEFORE deleting the existing row."""
    project_id = client.project_id
    weave_ref = f"weave:///{project_id}/obj/123:abc"

    initial = client.server.feedback_create(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=weave_ref,
            feedback_type="reaction",
            payload={"emoji": "👍"},
            wb_user_id="test_user",
        )
    )

    # The replace payload would fail validation (non-empty scorer_tags on a
    # non-agent-monitor type). Without validate-before-purge, the purge would
    # run first and destroy the original row.
    with pytest.raises(InvalidRequest):
        client.server.feedback_replace(
            FeedbackReplaceReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="reaction",
                payload={"emoji": "👍"},
                feedback_id=initial.id,
                wb_user_id="test_user",
                scorer_tags=["nsfw"],
            )
        )

    # The original row must still be there.
    query_res = client.server.feedback_query(
        FeedbackQueryReq(project_id=project_id, fields=["id"])
    )
    assert [r["id"] for r in query_res.result] == [initial.id]


def test_get_feedback_with_dict_query(client) -> None:
    """Test that get_feedback works with dict queries as shown in the docstring example."""
    # Create some test feedback using the server API
    project_id = client.project_id

    # Create a call to attach feedback to
    call_ref_uri = f"weave:///{project_id}/call/call_id_123"

    # Create feedback with specific feedback_type
    feedback_req1 = FeedbackCreateReq(
        project_id=project_id,
        weave_ref=call_ref_uri,
        feedback_type="wandb.reaction.1",
        payload={"emoji": "👍"},
    )
    feedback_res1 = client.server.feedback_create(feedback_req1)

    # Create feedback with different feedback_type
    feedback_req2 = FeedbackCreateReq(
        project_id=project_id,
        weave_ref=call_ref_uri,
        feedback_type="custom.score.1",
        payload={"score": 0.95},
    )
    feedback_res2 = client.server.feedback_create(feedback_req2)

    # Test the dict query example from the docstring
    query = Query(
        **{
            "$expr": {
                "$eq": [
                    {"$getField": "feedback_type"},
                    {"$literal": "wandb.reaction.1"},
                ]
            }
        }
    )

    feedback_results = client.get_feedback(query=query)

    # Verify we get the expected feedback
    feedback_list = list(feedback_results)
    assert len(feedback_list) == 1
    assert feedback_list[0].feedback_type == "wandb.reaction.1"
    assert feedback_list[0].payload["emoji"] == "👍"

    # Test another dict query for the custom feedback type
    custom_query = Query(
        **{
            "$expr": {
                "$eq": [
                    {"$getField": "feedback_type"},
                    {"$literal": "custom.score.1"},
                ],
            }
        }
    )

    custom_feedback_results = client.get_feedback(query=custom_query)
    custom_feedback_list = list(custom_feedback_results)
    assert len(custom_feedback_list) == 1
    assert custom_feedback_list[0].feedback_type == "custom.score.1"
    assert custom_feedback_list[0].payload["score"] == 0.95

    # Test dict query that should return no results
    no_results_query = Query(
        **{
            "$expr": {
                "$eq": [
                    {"$getField": "feedback_type"},
                    {"$literal": "nonexistent.type"},
                ],
            }
        }
    )

    no_results = client.get_feedback(query=no_results_query)
    assert len(list(no_results)) == 0


def test_feedback_query_bad_json_path(client) -> None:
    """Test that querying for nonexistent JSON paths raises appropriate error."""
    # Create some test feedback
    project_id = client.project_id

    # Create a call to attach feedback to
    call = client.create_call("test_op", {"input": "test"})
    client.finish_call(call, {"output": "test"})

    # Add feedback with a known structure
    trace_object = client.get_call(call.id)
    trace_object.feedback.add_note("test note")

    # Try to query for a field that doesn't exist in the feedback table schema
    # "inputs" is not a valid column or JSON field in the feedback table
    with pytest.raises(ValueError, match="Unknown field: inputs.message_id"):
        client.server.feedback_query(
            FeedbackQueryReq(
                project_id=project_id,
                query=Query(
                    **{
                        "$expr": {
                            "$contains": {
                                "input": {"$getField": "inputs.message_id"},
                                "substr": {"$literal": "test-id"},
                            }
                        }
                    }
                ),
            )
        )


@pytest.mark.disable_logging_error_check
def test_feedback_query_contains_numeric_literal(client) -> None:
    """$contains with a numeric literal raises a guided error; string substr works."""
    project_id = client.project_id
    call_ref_uri = f"weave:///{project_id}/call/call_id_456"

    # Create feedback with a payload containing a dataset_id
    feedback_req = FeedbackCreateReq(
        project_id=project_id,
        weave_ref=call_ref_uri,
        feedback_type="custom.annotation",
        payload={"dataset_id": 94, "dataset_id_str": "94"},
    )
    client.server.feedback_create(feedback_req)

    # A numeric literal on a JSON field surfaces a guided error pointing at $convert.
    with pytest.raises(
        QueryIllegalTypeofArgumentError,
        match="Illegal type of argument in query",
    ):
        client.server.feedback_query(
            FeedbackQueryReq(
                project_id=project_id,
                query=Query(
                    **{
                        "$expr": {
                            "$contains": {
                                "input": {"$getField": "payload.dataset_id"},
                                "substr": {
                                    "$literal": 94
                                },  # Numeric literal, not string
                            }
                        }
                    }
                ),
            )
        )

    res = client.server.feedback_query(
        FeedbackQueryReq(
            project_id=project_id,
            query=Query(
                **{
                    "$expr": {
                        "$contains": {
                            "input": {"$getField": "payload.dataset_id_str"},
                            "substr": {"$literal": "9"},  # Numeric literal, not string
                        }
                    }
                }
            ),
        )
    )
    assert len(res.result) == 1
    assert res.result[0]["payload"]["dataset_id_str"] == "94"


def test_feedback_query_typed_payload_filters(client: WeaveClient) -> None:
    """Regression for WB-33832: /feedback/query 500s on typed payload literals.

    Without inferred field-side casts, ClickHouse refuses `JSON_VALUE(...)`
    (String) compared against a typed param (Bool / Int64 / Float64) with
    `Code: 386 NO_COMMON_TYPE`. JSON_VALUE on a JSON boolean emits the
    literal string `'true'` / `'false'`, so the bool path must coerce
    those before any numeric fallback.

    """
    project_id = client.project_id
    call_ref = f"weave:///{project_id}/call/call_id_typed_payload"

    client.server.feedback_create(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=call_ref,
            feedback_type="custom.annotation",
            payload={"is_positive": True, "score": 0.9, "rank": 1},
        )
    )
    client.server.feedback_create(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=call_ref,
            feedback_type="custom.annotation",
            payload={"is_positive": False, "score": 0.1, "rank": 2},
        )
    )

    def query(expr: dict) -> list[dict]:
        return client.server.feedback_query(
            FeedbackQueryReq(project_id=project_id, query=Query(**{"$expr": expr}))
        ).result

    # Bool literal: this is the exact shape that was 502'ing in production.
    rows = query({"$eq": [{"$getField": "payload.is_positive"}, {"$literal": False}]})
    assert len(rows) == 1
    assert rows[0]["payload"]["is_positive"] is False

    rows = query({"$eq": [{"$getField": "payload.is_positive"}, {"$literal": True}]})
    assert len(rows) == 1
    assert rows[0]["payload"]["is_positive"] is True

    # Int literal: previously fell through to lexicographic string comparison.
    rows = query({"$eq": [{"$getField": "payload.rank"}, {"$literal": 2}]})
    assert len(rows) == 1
    assert rows[0]["payload"]["rank"] == 2

    # Float literal with $gt: same compat note as #6729.
    rows = query({"$gt": [{"$getField": "payload.score"}, {"$literal": 0.5}]})
    assert len(rows) == 1
    assert rows[0]["payload"]["score"] == 0.9

    # AND-wrapped bool comparison: inference is per-binary-op, but this pins
    # that nesting doesn't regress the lookup.
    rows = query(
        {
            "$and": [
                {"$eq": [{"$getField": "payload.is_positive"}, {"$literal": False}]},
                {"$gt": [{"$getField": "payload.rank"}, {"$literal": 1}]},
            ]
        }
    )
    assert len(rows) == 1
    assert rows[0]["payload"] == {"is_positive": False, "score": 0.1, "rank": 2}


def test_feedback_with_queue_id(client: WeaveClient) -> None:
    """Test feedback creation with queue_id field."""
    project_id = client.project_id
    weave_ref = f"weave:///{project_id}/call/call_id_789"

    # Create an annotation queue first
    queue_create_req = tsi.AnnotationQueueCreateReq(
        project_id=project_id,
        name="Test Queue",
        description="Queue for testing feedback",
        scorer_refs=[],
        wb_user_id="test_user",
    )
    queue_res = client.server.annotation_queue_create(queue_create_req)
    queue_id = queue_res.id

    # Case 1: Create feedback with valid queue_id
    feedback_req = FeedbackCreateReq(
        project_id=project_id,
        weave_ref=weave_ref,
        feedback_type="custom.score",
        payload={"score": 5},
        queue_id=queue_id,
    )
    create_res = client.server.feedback_create(feedback_req)
    assert create_res.id is not None

    # Verify queue_id is in query results
    query_res = client.server.feedback_query(FeedbackQueryReq(project_id=project_id))
    assert len(query_res.result) == 1
    assert query_res.result[0]["queue_id"] == queue_id

    # Case 2: Create feedback without queue_id (should still work)
    feedback_req_no_queue = FeedbackCreateReq(
        project_id=project_id,
        weave_ref=weave_ref,
        feedback_type="custom.score2",
        payload={"score": 3},
    )
    create_res_no_queue = client.server.feedback_create(feedback_req_no_queue)
    assert create_res_no_queue.id is not None

    # Verify queue_id is None in query results
    query_res = client.server.feedback_query(FeedbackQueryReq(project_id=project_id))
    assert len(query_res.result) == 2
    no_queue_feedback = next(
        f for f in query_res.result if f["id"] == create_res_no_queue.id
    )
    assert no_queue_feedback["queue_id"] is None


def test_feedback_with_invalid_queue_id(client: WeaveClient) -> None:
    """Test feedback creation with invalid queue_id."""
    project_id = client.project_id
    weave_ref = f"weave:///{project_id}/call/call_id_invalid"
    invalid_queue_id = "00000000-0000-0000-0000-000000000000"

    # Case 1: Error with non-existent queue_id
    with pytest.raises(InvalidRequest, match="Queue .* not found or has been deleted"):
        client.server.feedback_create(
            FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="custom.score",
                payload={"score": 5},
                queue_id=invalid_queue_id,
            )
        )


def test_feedback_with_queue_id_from_different_project(client: WeaveClient) -> None:
    """Test feedback creation with queue_id from a different project."""
    project_id = client.project_id
    other_project_id = f"{project_id}_other"

    # Create a queue in the original project
    queue_create_req = tsi.AnnotationQueueCreateReq(
        project_id=project_id,
        name="Original Project Queue",
        description="Queue in original project",
        scorer_refs=[],
        wb_user_id="test_user",
    )
    queue_res = client.server.annotation_queue_create(queue_create_req)
    queue_id = queue_res.id

    # Try to create feedback in a different project with the queue_id
    # This should fail because the queue doesn't belong to the target project
    with pytest.raises(InvalidRequest, match="Queue .* not found or has been deleted"):
        client.server.feedback_create(
            FeedbackCreateReq(
                project_id=other_project_id,
                weave_ref=f"weave:///{other_project_id}/call/call_id_123",
                feedback_type="custom.score",
                payload={"score": 5},
                queue_id=queue_id,
            )
        )


def test_feedback_query_by_queue_id(client: WeaveClient) -> None:
    """Test querying feedback filtered by queue_id."""
    project_id = client.project_id

    # Create two queues
    queue1_res = client.server.annotation_queue_create(
        tsi.AnnotationQueueCreateReq(
            project_id=project_id,
            name="Queue 1",
            description="First queue",
            scorer_refs=[],
            wb_user_id="test_user",
        )
    )
    queue1_id = queue1_res.id

    queue2_res = client.server.annotation_queue_create(
        tsi.AnnotationQueueCreateReq(
            project_id=project_id,
            name="Queue 2",
            description="Second queue",
            scorer_refs=[],
            wb_user_id="test_user",
        )
    )
    queue2_id = queue2_res.id

    # Create feedback for queue 1
    client.server.feedback_create(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=f"weave:///{project_id}/call/call1",
            feedback_type="custom.score",
            payload={"score": 1},
            queue_id=queue1_id,
        )
    )

    # Create feedback for queue 2
    client.server.feedback_create(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=f"weave:///{project_id}/call/call2",
            feedback_type="custom.score",
            payload={"score": 2},
            queue_id=queue2_id,
        )
    )

    # Create feedback without queue
    client.server.feedback_create(
        FeedbackCreateReq(
            project_id=project_id,
            weave_ref=f"weave:///{project_id}/call/call3",
            feedback_type="custom.score",
            payload={"score": 3},
        )
    )

    # Query feedback for queue 1
    queue1_feedback = client.server.feedback_query(
        FeedbackQueryReq(
            project_id=project_id,
            query=Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "queue_id"},
                            {"$literal": queue1_id},
                        ]
                    }
                }
            ),
        )
    )
    assert len(queue1_feedback.result) == 1
    assert queue1_feedback.result[0]["payload"]["score"] == 1
    assert queue1_feedback.result[0]["queue_id"] == queue1_id

    # Query feedback for queue 2
    queue2_feedback = client.server.feedback_query(
        FeedbackQueryReq(
            project_id=project_id,
            query=Query(
                **{
                    "$expr": {
                        "$eq": [
                            {"$getField": "queue_id"},
                            {"$literal": queue2_id},
                        ]
                    }
                }
            ),
        )
    )
    assert len(queue2_feedback.result) == 1
    assert queue2_feedback.result[0]["payload"]["score"] == 2
    assert queue2_feedback.result[0]["queue_id"] == queue2_id

    # Query all feedback
    all_feedback = client.server.feedback_query(FeedbackQueryReq(project_id=project_id))
    assert len(all_feedback.result) == 3


# ---------------------------------------------------------------------------
# feedback_stats / feedback_payload_schema integration tests
# ---------------------------------------------------------------------------


def _seed_numeric_feedback(
    client: WeaveClient,
    scores: list[float],
    feedback_type: str = "wandb.runnable.test-scorer",
    trigger_ref: str | None = None,
) -> None:
    """Create feedback rows with numeric payload for stats testing."""
    project_id = client.project_id
    call = client.create_call("x", {"a": 1})
    client.finish_call(call, "done")
    weave_ref = get_ref(client.get_call(call.id)).uri()
    call_ref = f"weave:///{project_id}/call/{call.id}"
    runnable_name = feedback_type.rsplit(".", 1)[-1]
    runnable_ref = f"weave:///{project_id}/op/{runnable_name}:op_digest_1"

    for score in scores:
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type=feedback_type,
                payload={"output": {"score": score}},
                runnable_ref=runnable_ref,
                call_ref=call_ref,
                trigger_ref=trigger_ref,
            )
        )


def test_feedback_stats(client: WeaveClient) -> None:
    """End-to-end: seed feedback, query aggregated stats, verify buckets and window_stats."""
    project_id = client.project_id
    trigger = f"weave:///{project_id}/object/test-scorer:trig_1"
    scores = [0.5, 0.8, 1.0]
    _seed_numeric_feedback(
        client,
        scores,
        feedback_type="wandb.runnable.test-scorer",
        trigger_ref=trigger,
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    res = client.server.feedback_stats(
        tsi.FeedbackStatsReq(
            project_id=project_id,
            start=now - datetime.timedelta(hours=1),
            end=now + datetime.timedelta(minutes=5),
            feedback_type="wandb.runnable.test-scorer",
            trigger_ref=trigger,
            metrics=[
                tsi.FeedbackMetricSpec(
                    json_path="output.score",
                    value_type="numeric",
                    aggregations=[
                        tsi.AggregationType.AVG,
                        tsi.AggregationType.MIN,
                        tsi.AggregationType.MAX,
                    ],
                )
            ],
        )
    )

    assert isinstance(res.buckets, list)
    assert len(res.buckets) >= 1
    total_count = sum(b.get("count", 0) for b in res.buckets)
    assert total_count == len(scores)
    assert res.granularity > 0

    assert res.window_stats is not None
    assert "output_score" in res.window_stats
    ws = res.window_stats["output_score"]
    assert ws["min"] == pytest.approx(0.5)
    assert ws["max"] == pytest.approx(1.0)
    assert ws["avg"] == pytest.approx(sum(scores) / len(scores), abs=1e-6)


def test_feedback_payload_schema(client: WeaveClient) -> None:
    """End-to-end: seed varied feedback, discover payload schema paths."""
    project_id = client.project_id
    call = client.create_call("x", {"a": 1})
    client.finish_call(call, "done")
    weave_ref = get_ref(client.get_call(call.id)).uri()
    call_ref = f"weave:///{project_id}/call/{call.id}"
    runnable_ref = f"weave:///{project_id}/op/schema-scorer:op_digest_1"
    trigger = f"weave:///{project_id}/object/schema-scorer:trig_schema"

    for payload in [
        {"output": {"score": 0.9}},
        {"output": {"score": 0.5}, "label": "good"},
    ]:
        client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=weave_ref,
                feedback_type="wandb.runnable.schema-scorer",
                payload=payload,
                runnable_ref=runnable_ref,
                call_ref=call_ref,
                trigger_ref=trigger,
            )
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    res = client.server.feedback_payload_schema(
        tsi.FeedbackPayloadSchemaReq(
            project_id=project_id,
            start=now - datetime.timedelta(hours=1),
            end=now + datetime.timedelta(minutes=5),
            feedback_type="wandb.runnable.schema-scorer",
            trigger_ref=trigger,
        )
    )

    path_map = {p.json_path: p.value_type for p in res.paths}
    assert "output.score" in path_map
    assert path_map["output.score"] == "numeric"
    assert "label" in path_map
    assert path_map["label"] == "categorical"


def test_feedback_stats_empty_metrics(client: WeaveClient) -> None:
    """Empty metrics list returns empty buckets without error."""
    project_id = client.project_id
    now = datetime.datetime.now(datetime.timezone.utc)
    res = client.server.feedback_stats(
        tsi.FeedbackStatsReq(
            project_id=project_id,
            start=now - datetime.timedelta(hours=1),
            end=now + datetime.timedelta(minutes=5),
            metrics=[],
        )
    )

    assert res.buckets == []
    assert res.granularity == 3600


def test_feedback_query_returns_tz_aware_created_at(client: WeaveClient) -> None:
    """Ensure `feedback_query` returns tz-aware `created_at`."""
    project_id = client.project_id
    client.server.feedback_create(
        tsi.FeedbackCreateReq(
            project_id=project_id,
            weave_ref="weave:///entity/project/object/test:digest",
            feedback_type="custom",
            payload={"k": "v"},
            wb_user_id="",
        )
    )
    res = client.server.feedback_query(tsi.FeedbackQueryReq(project_id=project_id))
    assert len(res.result) == 1
    created_at = res.result[0]["created_at"]
    assert isinstance(created_at, datetime.datetime)
    assert created_at.tzinfo is not None, (
        "feedback_query returned a naive datetime; browsers will misinterpret it"
    )
    assert created_at.utcoffset() == datetime.timedelta(0), (
        "feedback created_at must be tz-aware UTC"
    )


def test_feedback_query_by_collection_size(client: WeaveClient) -> None:
    project_id = client.project_id

    def create_feedback(
        feedback_id: str,
        *,
        tags: list[str] | None = None,
        ratings: dict[str, float] | None = None,
    ) -> str:
        result = client.server.feedback_create(
            tsi.FeedbackCreateReq(
                project_id=project_id,
                weave_ref=f"weave:///{project_id}/call/{feedback_id}",
                feedback_type="wandb.agent_monitor",
                payload={},
                runnable_ref=f"weave:///{project_id}/object/scorer:v1",
                call_ref=f"weave:///{project_id}/call/judge-{feedback_id}",
                trigger_ref=f"weave:///{project_id}/object/monitor:v1",
                scorer_tags=tags or [],
                scorer_ratings=ratings or {},
            )
        )
        return result.id

    empty_id = create_feedback("empty")
    tagged_id = create_feedback("tagged", tags=["helpful"])
    rated_id = create_feedback("rated", ratings={"_rating_": 0.8})

    all_feedback = client.server.feedback_query(
        tsi.FeedbackQueryReq(project_id=project_id, fields=["id"])
    )
    scored_feedback = client.server.feedback_query(
        tsi.FeedbackQueryReq(
            project_id=project_id,
            fields=["id"],
            query=tsi.Query.model_validate(
                {
                    "$expr": {
                        "$or": [
                            {
                                "$gt": [
                                    {"$size": {"$getField": "scorer_tags"}},
                                    {"$literal": 0},
                                ]
                            },
                            {
                                "$gt": [
                                    {"$size": {"$getField": "scorer_ratings"}},
                                    {"$literal": 0},
                                ]
                            },
                        ]
                    }
                }
            ),
        )
    )

    assert sorted(all_feedback.result, key=lambda row: row["id"]) == sorted(
        [{"id": empty_id}, {"id": rated_id}, {"id": tagged_id}],
        key=lambda row: row["id"],
    )
    assert sorted(scored_feedback.result, key=lambda row: row["id"]) == sorted(
        [{"id": rated_id}, {"id": tagged_id}],
        key=lambda row: row["id"],
    )
