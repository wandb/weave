import logging

from weave.trace_server import refs_internal as ri
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import (
    InvalidRequest,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def evaluation_status(
    server: tsi.TraceServerInterface, req: tsi.EvaluationStatusReq
) -> tsi.EvaluationStatusRes:
    eval_call = server.call_read(
        tsi.CallReadReq(
            project_id=req.project_id,
            id=req.call_id,
        )
    )

    if eval_call.call is None:
        return tsi.EvaluationStatusRes(status=tsi.EvaluationStatusNotFound())

    if "Evaluation.evaluate" not in eval_call.call.op_name:
        raise InvalidRequest("Call is not an evaluation")

    if eval_call.call.exception is not None:
        return tsi.EvaluationStatusRes(status=tsi.EvaluationStatusFailed())

    if eval_call.call.ended_at is not None:
        return tsi.EvaluationStatusRes(
            status=tsi.EvaluationStatusComplete(output=eval_call.call.output)
        )

    # determine completed rows (children complete)
    children_stats = server.calls_query_stats(
        tsi.CallsQueryReq(
            project_id=req.project_id,
            filter=tsi.CallsFilter(
                parent_ids=[req.call_id],
            ),
            query=tsi.Query.model_validate(
                {
                    "$expr": {
                        "$not": [
                            {
                                "$eq": [
                                    {"$getField": "summary.weave.status"},
                                    {"$literal": tsi.TraceStatus.RUNNING},
                                ]
                            }
                        ]
                    }
                }
            ),
        ),
    )

    completed_rows = children_stats.count

    # Default to completed rows if no dataset is provided
    total_rows = completed_rows

    def get_total_rows() -> int:
        if eval_call.call is None:
            return 0

        eval_def_ref = eval_call.call.inputs.get("self")
        if eval_def_ref is None:
            return 0

        parsed_eval_def_ref = ri.parse_internal_uri(eval_def_ref)
        if not isinstance(parsed_eval_def_ref, ri.InternalObjectRef):
            raise InvalidRequest("Evaluation definition is not an Evaluation")
        eval_def_obj = server.obj_read(
            tsi.ObjReadReq(
                project_id=req.project_id,
                object_id=parsed_eval_def_ref.name,
                digest=parsed_eval_def_ref.version,
            )
        )
        dataset_ref = eval_def_obj.obj.val["dataset"]
        parsed_dataset_ref = ri.parse_internal_uri(dataset_ref)
        if not isinstance(parsed_dataset_ref, ri.InternalObjectRef):
            raise InvalidRequest("Dataset is not an object")
        dataset_obj = server.obj_read(
            tsi.ObjReadReq(
                project_id=req.project_id,
                object_id=parsed_dataset_ref.name,
                digest=parsed_dataset_ref.version,
            )
        )
        table_rows_ref = dataset_obj.obj.val["rows"]
        parsed_table_rows_ref = ri.parse_internal_uri(table_rows_ref)
        if not isinstance(parsed_table_rows_ref, ri.InternalTableRef):
            raise InvalidRequest("Table rows is not a table")
        table_rows_stats = server.table_query_stats(
            tsi.TableQueryStatsReq(
                project_id=req.project_id,
                digest=parsed_table_rows_ref.digest,
            )
        )
        return table_rows_stats.count

    # Safely attempt to get total rows (let's not error if we can't get it)
    try:
        total_rows = max(get_total_rows(), completed_rows)
    except Exception as e:
        logger.exception(
            "Error getting total rows for evaluation", extra={"error": str(e)}
        )

    return tsi.EvaluationStatusRes(
        status=tsi.EvaluationStatusRunning(
            completed_rows=completed_rows, total_rows=total_rows
        )
    )
