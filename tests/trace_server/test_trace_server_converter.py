import datetime

from weave.trace_server import ch_sentinel_values
from weave.trace_server.clickhouse.schema_converters import (
    ch_call_to_row,
    ch_complete_call_to_row,
)
from weave.trace_server.clickhouse_schema import (
    ALL_CALL_COMPLETE_INSERT_COLUMNS,
    ALL_CALL_INSERT_COLUMNS,
    CallCompleteCHInsertable,
    CallStartCHInsertable,
)
from weave.trace_server.interface.query import Query
from weave.trace_server.trace_server_converter import universal_ext_to_int_ref_converter
from weave.trace_server.trace_server_interface import (
    CallStartReq,
    StartedCallSchemaForInsert,
)


def test_universal_ext_to_int_ref_converter_reuses_models_and_untouched_branches():
    project_id = "entity/project"
    internal_project_id = "internal-project"
    external_ref = f"weave:///{project_id}/op/some-op:latest"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/op/some-op:latest"
    started_at = datetime.datetime.now(datetime.timezone.utc)

    # No-op request: the same model and container objects should be reused.
    no_ref_req = CallStartReq(
        start=StartedCallSchemaForInsert(
            project_id=internal_project_id,
            op_name="plain-op",
            started_at=started_at,
            attributes={"status": "ok"},
            inputs={"nested": {"value": "plain"}},
            otel_dump={"span": "plain"},
        )
    )
    original_no_ref_start = no_ref_req.start
    original_no_ref_inputs = no_ref_req.start.inputs
    original_no_ref_nested = no_ref_req.start.inputs["nested"]

    converted_no_ref = universal_ext_to_int_ref_converter(
        no_ref_req, lambda project: internal_project_id
    )

    assert converted_no_ref is no_ref_req
    assert converted_no_ref.start is original_no_ref_start
    assert converted_no_ref.start.inputs is original_no_ref_inputs
    assert converted_no_ref.start.inputs["nested"] is original_no_ref_nested

    # One rewritten ref: only the path to the changed value should be rebuilt.
    changed_branch = {"payload": ["plain", external_ref]}
    untouched_branch = {"keep": ["still", {"plain": "value"}]}
    req = CallStartReq(
        start=StartedCallSchemaForInsert(
            project_id=internal_project_id,
            op_name=external_ref,
            started_at=started_at,
            attributes={"status": "ok"},
            inputs={
                "changed": changed_branch,
                "untouched": untouched_branch,
            },
            otel_dump={"span": "plain"},
        )
    )
    original_start = req.start
    original_inputs = req.start.inputs
    original_changed_branch = req.start.inputs["changed"]
    original_payload = req.start.inputs["changed"]["payload"]
    original_untouched_branch = req.start.inputs["untouched"]
    original_attributes = req.start.attributes
    original_otel_dump = req.start.otel_dump

    converted = universal_ext_to_int_ref_converter(
        req, lambda project: internal_project_id
    )

    assert converted is req
    assert converted.start is original_start
    assert converted.start.attributes is original_attributes
    assert converted.start.otel_dump is original_otel_dump
    assert converted.start.inputs is not original_inputs
    assert converted.start.inputs["changed"] is not original_changed_branch
    assert converted.start.inputs["changed"]["payload"] is not original_payload
    assert converted.start.inputs["untouched"] is original_untouched_branch
    assert converted.start.op_name == internal_ref
    assert converted.start.inputs["changed"]["payload"] == ["plain", internal_ref]

    # The old branch objects stay untouched, proving the walk is copy-on-write.
    assert original_payload == ["plain", external_ref]


def test_universal_ext_to_int_ref_converter_handles_aliased_query_models():
    project_id = "entity/project"
    internal_project_id = "internal-project"
    external_ref = f"weave:///{project_id}/object/name:digest"
    internal_ref = f"weave-trace-internal:///{internal_project_id}/object/name:digest"

    query = Query.model_validate(
        {
            "$expr": {
                "$eq": [
                    {"$literal": external_ref},
                    {"$literal": "plain"},
                ]
            }
        }
    )
    original_expr = query.expr_
    original_eq = query.expr_.eq_
    original_left_literal = query.expr_.eq_[0]

    converted = universal_ext_to_int_ref_converter(
        query, lambda project: internal_project_id
    )

    assert converted is query
    assert converted.expr_ is original_expr
    assert converted.expr_.eq_ is not original_eq
    assert converted.expr_.eq_[0] is original_left_literal
    aliased_query = converted.model_dump(by_alias=True)
    assert aliased_query["$expr"]["$eq"][0]["$literal"] == internal_ref
    assert aliased_query["$expr"]["$eq"][1]["$literal"] == "plain"


def test_clickhouse_row_helpers_match_previous_model_dump_behavior():
    now = datetime.datetime.now(datetime.timezone.utc)
    project_id = "cHJvamVjdC1pZA=="
    call_id = "0123456789abcdef"
    trace_id = "0123456789abcdef0123456789abcdef"
    start_row = CallStartCHInsertable(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        parent_id=None,
        thread_id=None,
        turn_id=None,
        op_name="op-name",
        display_name="display-name",
        started_at=now,
        attributes_dump="{}",
        inputs_dump="{}",
        input_refs=[f"weave-trace-internal:///{project_id}/object/name:digest"],
        output_refs=[],
        otel_dump=None,
        wb_user_id="dXNlci1pZA==",
        wb_run_id="dXNlci1pZA==:run",
        wb_run_step=1,
    )
    complete_row = CallCompleteCHInsertable(
        project_id=project_id,
        id=call_id,
        trace_id=trace_id,
        parent_id=None,
        thread_id=None,
        turn_id=None,
        op_name="op-name",
        display_name="display-name",
        started_at=now,
        ended_at=None,
        exception=None,
        attributes_dump="{}",
        inputs_dump="{}",
        output_dump="null",
        summary_dump="{}",
        input_refs=[],
        output_refs=[],
        otel_dump=None,
        wb_user_id=None,
        wb_run_id=None,
        wb_run_step=None,
        wb_run_step_end=None,
    )

    # Start-call rows should still line up with the old model_dump-based ordering.
    expected_start_row = [
        start_row.model_dump().get(col) for col in ALL_CALL_INSERT_COLUMNS
    ]
    assert ch_call_to_row(start_row) == expected_start_row

    # Complete-call rows must also keep sentinel conversion behavior unchanged.
    expected_complete_row = [
        ch_sentinel_values.to_ch_value(col, complete_row.model_dump().get(col))
        for col in ALL_CALL_COMPLETE_INSERT_COLUMNS
    ]
    assert ch_complete_call_to_row(complete_row) == expected_complete_row
