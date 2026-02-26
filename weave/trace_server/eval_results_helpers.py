"""Helper functions for eval_results_query.

These are shared between ClickHouse and SQLite trace server implementations.
Most helpers are pure (operate on in-memory data). The orchestration functions
(eval_results_grouped_rows, fetch_eval_root_metadata, eval_results_query) take
a TraceServerInterface and perform DB access via calls_query_stream and
refs_read_batch.
"""

import json
import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from weave.shared import refs_internal as ri

try:
    import ddtrace
except ImportError:
    ddtrace = None  # type: ignore[assignment]

F = TypeVar("F", bound=Callable[..., Any])


def _trace_wrap(name: str) -> Callable[[F], F]:
    """No-op if ddtrace unavailable; otherwise wrap with ddtrace.tracer.wrap."""

    def decorator(fn: F) -> F:
        if ddtrace is not None:
            return ddtrace.tracer.wrap(name=name)(fn)  # type: ignore[return-value]
        return fn

    return decorator  # type: ignore[return-value]


from weave.shared.digest import str_digest
from weave.trace_server import constants
from weave.trace_server import trace_server_common as tsc
from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)


def resolve_eval_root_ids(
    req: tsi.EvalResultsQueryReq,
) -> list[str]:
    """Return de-duplicated evaluation root IDs preserving request order."""
    combined = (req.evaluation_call_ids or []) + (req.evaluation_run_ids or [])
    return list(dict.fromkeys(combined))


def extract_eval_root_metadata_from_calls(
    calls: Iterable[tsi.CallSchema],
) -> dict[str, dict[str, Any]]:
    """Extract metadata from eval root calls for summary enrichment.

    Args:
        calls: Iterable of CallSchema objects (e.g. from calls_query_stream).

    Returns:
        Dict mapping call_id -> metadata dict with keys: evaluation_ref,
        model_ref, display_name, trace_id, started_at.
    """
    metadata: dict[str, dict[str, Any]] = {}
    for call in calls:
        inputs = call.inputs if isinstance(call.inputs, dict) else {}
        eval_ref = inputs.get("self") or inputs.get("this")
        started_at = None
        if call.started_at is not None:
            started_at = call.started_at.isoformat()
        metadata[call.id] = {
            "evaluation_ref": eval_ref,
            "model_ref": inputs.get("model"),
            "display_name": call.display_name,
            "trace_id": call.trace_id,
            "started_at": started_at,
        }
    return metadata


def build_pas_calls_query_req(
    project_id: str, eval_root_ids: list[str]
) -> tsi.CallsQueryReq:
    """Build CallsQueryReq for predict-and-score child calls of eval roots."""
    return tsi.CallsQueryReq(
        project_id=project_id,
        filter=tsi.CallsFilter(parent_ids=eval_root_ids),
        columns=["id", "parent_id", "op_name", "inputs", "output"],
        sort_by=[tsi.SortBy(field="started_at", direction="asc")],
    )


def build_child_calls_query_req(
    project_id: str, pas_ids: list[str]
) -> tsi.CallsQueryReq:
    """Build CallsQueryReq for child calls of predict-and-score calls."""
    return tsi.CallsQueryReq(
        project_id=project_id,
        filter=tsi.CallsFilter(parent_ids=pas_ids),
        columns=[
            "id",
            "parent_id",
            "op_name",
            "attributes",
            "inputs",
            "output",
            "summary",
            "started_at",
            "ended_at",
        ],
    )


def filter_predict_and_score_calls(
    calls: Iterable[tsi.CallSchema],
    eval_root_ids: list[str],
) -> list[tsi.CallSchema]:
    """Filter to predict-and-score calls whose parent is in eval_root_ids."""
    eval_root_set = frozenset(eval_root_ids)
    return [
        call
        for call in calls
        if call.parent_id in eval_root_set
        and tsc.op_name_matches(
            call.op_name, constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME
        )
    ]


def build_child_by_parent(
    child_calls: list[tsi.CallSchema],
) -> dict[str, list[tsi.CallSchema]]:
    """Group child calls by parent_id."""
    result: dict[str, list[tsi.CallSchema]] = defaultdict(list)
    for call in child_calls:
        if call.parent_id is not None:
            result[call.parent_id].append(call)
    return result


def collect_dataset_refs_for_resolution(
    rows: list[tsi.EvalResultsRow], project_id: str
) -> dict[str, str]:
    """Collect dataset row refs from rows that need resolution.

    Returns:
        Dict mapping row_digest -> ref URI for refs_read_batch.
    """
    dataset_ref_by_digest: dict[str, str] = {}
    internal_prefix = f"{ri.WEAVE_INTERNAL_SCHEME}:///"
    for row in rows:
        raw = row.raw_data_row
        if isinstance(raw, str) and ri.DATASET_ROW_REF_PATH_SUFFIX in raw:
            result = ri.try_parse_dataset_row_ref(raw)
            if result is not None:
                uri, _ = result
                dataset_ref_by_digest[row.row_digest] = uri
            else:
                dataset_ref_by_digest[row.row_digest] = (
                    f"{internal_prefix}{project_id}/object/{raw}"
                )
    return dataset_ref_by_digest


def apply_resolved_refs_to_rows(
    rows: list[tsi.EvalResultsRow],
    dataset_ref_by_digest: dict[str, str],
    resolved_vals: list[Any],
) -> None:
    """Apply resolved values to rows in-place. resolved_vals order must match dataset_ref_by_digest keys."""
    row_lookup = {row.row_digest: row for row in rows}
    for row_digest, val in zip(
        dataset_ref_by_digest.keys(), resolved_vals, strict=False
    ):
        if val is not None and row_digest in row_lookup:
            row_lookup[row_digest].raw_data_row = val


def extract_row_digest_from_example(example: Any) -> tuple[str, bool]:
    """Extract row digest from dataset refs or derive a stable digest.

    Returns:
        tuple[str, bool]: (digest, was_extracted_from_ref)
    """
    if isinstance(example, str):
        digest = ri.extract_row_digest_from_ref_path(example)
        if digest is not None:
            return digest, True
    if not isinstance(example, str):
        example = json.dumps(example, sort_keys=True, default=str)
    return str_digest(example), False


def select_predict_call(
    child_calls: list[tsi.CallSchema], model_ref: Any
) -> tsi.CallSchema | None:
    """Best-effort selection of the model predict child call."""
    for call in child_calls:
        weave_attrs = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})
        if weave_attrs.get(constants.SCORE_ATTR_KEY) == "true":
            continue
        eval_meta = call.attributes.get("_weave_eval_meta", {})
        if isinstance(eval_meta, dict) and eval_meta.get("score"):
            continue
        if isinstance(call.inputs, dict) and call.inputs.get("self") == model_ref:
            return call
        op_name = call.op_name.lower()
        if "predict" in op_name or "invoke" in op_name:
            return call
    return None


def extract_total_tokens(
    summary: "dict[str, Any] | tsi.SummaryMap | None",
) -> int | None:
    """Return the total token count from summary usage if present."""
    if not isinstance(summary, dict):
        return None
    usage = summary.get("usage")
    if not isinstance(usage, dict):
        return None
    total_tokens = 0
    found_any = False
    for model_usage in usage.values():
        if not isinstance(model_usage, dict):
            continue
        tokens = model_usage.get("total_tokens")
        if isinstance(tokens, (int, float)):
            total_tokens += int(tokens)
            found_any = True
    return total_tokens if found_any else None


def best_effort_scorer_call_ids(
    scores: dict[str, Any], child_calls: list[tsi.CallSchema]
) -> dict[str, str]:
    """Map scorer keys to scorer call IDs using heuristic name matching."""
    scorer_calls: list[tsi.CallSchema] = []
    for call in child_calls:
        weave_attrs = call.attributes.get(constants.WEAVE_ATTRIBUTES_NAMESPACE, {})
        eval_meta = call.attributes.get("_weave_eval_meta", {})
        if weave_attrs.get(constants.SCORE_ATTR_KEY) == "true" or (
            isinstance(eval_meta, dict) and eval_meta.get("score")
        ):
            scorer_calls.append(call)
            continue
        op_name = call.op_name.lower()
        if ".score" in op_name or "scorer" in op_name:
            scorer_calls.append(call)
    result: dict[str, str] = {}
    for scorer_key in scores:
        key_lower = scorer_key.lower()
        match = next(
            (
                call
                for call in scorer_calls
                if key_lower in call.op_name.lower()
                or call.op_name.lower() in key_lower
            ),
            None,
        )
        if match is not None:
            result[scorer_key] = match.id
    return result


@_trace_wrap("eval_results_helpers.build_eval_rows_from_calls")
def build_eval_rows_from_calls(
    predict_and_score_calls: list[tsi.CallSchema],
    child_by_parent: dict[str, list[tsi.CallSchema]],
    include_raw_data_rows: bool,
) -> tuple[
    dict[str, tsi.EvalResultsRow], dict[str, dict[str, tsi.EvalResultsRowEvaluation]]
]:
    """Build row and evaluation maps from predict-and-score calls.

    Returns:
        tuple: (row_map, row_eval_map) where row_map maps row_digest -> EvalResultsRow
            and row_eval_map maps row_digest -> {eval_call_id -> EvalResultsRowEvaluation}
    """
    row_map: dict[str, tsi.EvalResultsRow] = {}
    row_eval_map: dict[str, dict[str, tsi.EvalResultsRowEvaluation]] = defaultdict(dict)

    for pas_call in predict_and_score_calls:
        eval_call_id = pas_call.parent_id
        if eval_call_id is None:
            continue
        example = (
            pas_call.inputs.get("example")
            if isinstance(pas_call.inputs, dict)
            else None
        )
        row_digest, _ = extract_row_digest_from_example(example)

        row = row_map.get(row_digest)
        if row is None:
            row = tsi.EvalResultsRow(
                row_digest=row_digest,
                raw_data_row=example if include_raw_data_rows else None,
            )
            row_map[row_digest] = row
        elif include_raw_data_rows and row.raw_data_row is None and example is not None:
            row.raw_data_row = example

        eval_entry = row_eval_map[row_digest].get(eval_call_id)
        if eval_entry is None:
            eval_entry = tsi.EvalResultsRowEvaluation(evaluation_call_id=eval_call_id)
            row_eval_map[row_digest][eval_call_id] = eval_entry

        output = pas_call.output if isinstance(pas_call.output, dict) else {}
        scores = output.get("scores") if isinstance(output.get("scores"), dict) else {}
        trial_children = child_by_parent.get(pas_call.id, [])
        model_ref = (
            pas_call.inputs.get("model") if isinstance(pas_call.inputs, dict) else None
        )
        predict_call = select_predict_call(trial_children, model_ref)
        latency_seconds = None
        if predict_call and predict_call.started_at and predict_call.ended_at:
            latency_seconds = (
                predict_call.ended_at - predict_call.started_at
            ).total_seconds()
        elif isinstance(output.get("model_latency"), dict):
            model_latency = output.get("model_latency", {})
            mean_latency = model_latency.get("mean")
            if isinstance(mean_latency, (int, float)):
                latency_seconds = float(mean_latency)

        eval_entry.trials.append(
            tsi.EvalResultsTrial(
                predict_and_score_call_id=pas_call.id,
                predict_call_id=predict_call.id if predict_call else None,
                model_output=output.get("output"),
                scores=scores,
                model_latency_seconds=latency_seconds,
                total_tokens=extract_total_tokens(
                    predict_call.summary if predict_call else None
                ),
                scorer_call_ids=best_effort_scorer_call_ids(
                    scores if isinstance(scores, dict) else {}, trial_children
                ),
            )
        )

    return row_map, row_eval_map


def finalize_rows(
    row_map: dict[str, tsi.EvalResultsRow],
    row_eval_map: dict[str, dict[str, tsi.EvalResultsRowEvaluation]],
    eval_root_ids: list[str],
    require_intersection: bool,
    offset: int,
    limit: int | None,
) -> tuple[list[tsi.EvalResultsRow], int]:
    """Attach evaluations to rows, apply intersection filter, sort, and paginate."""
    for row_digest, eval_entries in row_eval_map.items():
        if row_digest in row_map:
            row_map[row_digest].evaluations = list(eval_entries.values())

    rows = list(row_map.values())

    return apply_row_selection(rows, eval_root_ids, require_intersection, offset, limit)


def apply_row_selection(
    rows: list[tsi.EvalResultsRow],
    eval_root_ids: list[str],
    require_intersection: bool,
    offset: int,
    limit: int | None,
) -> tuple[list[tsi.EvalResultsRow], int]:
    """Apply intersection filtering, stable sort, and pagination to grouped rows."""
    selected_rows = rows
    if require_intersection and len(eval_root_ids) > 1:
        eval_root_id_set = set(eval_root_ids)
        selected_rows = [
            row
            for row in selected_rows
            if eval_root_id_set.issubset(
                {e.evaluation_call_id for e in row.evaluations}
            )
        ]

    selected_rows.sort(key=lambda row: row.row_digest)
    total_rows = len(selected_rows)
    start = max(offset, 0)
    end = start + limit if limit is not None else None
    return selected_rows[start:end], total_rows


def resolve_eval_row_refs(
    server: tsi.TraceServerInterface,
    rows: list[tsi.EvalResultsRow],
    project_id: str,
) -> list[str]:
    """Resolve dataset-row refs in-place via refs_read_batch.

    Returns:
        list[str]: Warnings if resolution failed (e.g. refs_read_batch error).
    """
    dataset_ref_by_digest = collect_dataset_refs_for_resolution(rows, project_id)
    if dataset_ref_by_digest:
        try:
            refs_res = server.refs_read_batch(
                tsi.RefsReadBatchReq(refs=list(dataset_ref_by_digest.values()))
            )
            apply_resolved_refs_to_rows(rows, dataset_ref_by_digest, refs_res.vals)
        except Exception:
            logger.warning("Failed to resolve dataset row refs", exc_info=True)
            return ["Failed to resolve dataset row refs; raw_data_row may contain refs"]
    return []


@_trace_wrap("eval_results_helpers.eval_results_grouped_rows")
def eval_results_grouped_rows(
    server: tsi.TraceServerInterface, req: tsi.EvalResultsQueryReq
) -> tuple[list[tsi.EvalResultsRow], int, list[str]]:
    """Build grouped eval rows before pagination. Performs DB access via server."""
    eval_root_ids = resolve_eval_root_ids(req)
    if not eval_root_ids:
        return [], 0, []

    pas_req = build_pas_calls_query_req(req.project_id, eval_root_ids)
    predict_and_score_calls = filter_predict_and_score_calls(
        server.calls_query_stream(pas_req), eval_root_ids
    )
    if not predict_and_score_calls:
        return [], 0, []

    pas_ids = [call.id for call in predict_and_score_calls]
    child_req = build_child_calls_query_req(req.project_id, pas_ids)
    child_calls = list(server.calls_query_stream(child_req))
    child_by_parent = build_child_by_parent(child_calls)

    row_map, row_eval_map = build_eval_rows_from_calls(
        predict_and_score_calls, child_by_parent, req.include_raw_data_rows
    )

    warnings: list[str] = []
    if req.include_raw_data_rows and req.resolve_row_refs:
        warnings = resolve_eval_row_refs(server, list(row_map.values()), req.project_id)

    rows, total = finalize_rows(
        row_map,
        row_eval_map,
        eval_root_ids,
        req.require_intersection,
        req.offset,
        req.limit,
    )
    return rows, total, warnings


@_trace_wrap("eval_results_helpers.fetch_eval_root_metadata")
def fetch_eval_root_metadata(
    server: tsi.TraceServerInterface,
    project_id: str,
    eval_root_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch metadata from eval root calls for summary enrichment."""
    if not eval_root_ids:
        return {}
    root_req = tsi.CallsQueryReq(
        project_id=project_id,
        filter=tsi.CallsFilter(call_ids=eval_root_ids),
        columns=["id", "inputs", "display_name", "trace_id", "started_at"],
    )
    return extract_eval_root_metadata_from_calls(server.calls_query_stream(root_req))


@_trace_wrap("eval_results_helpers.eval_results_query")
def eval_results_query(
    server: tsi.TraceServerInterface, req: tsi.EvalResultsQueryReq
) -> tsi.EvalResultsQueryRes:
    """Return grouped prediction/trial/score data for evaluation results."""
    eval_root_ids = resolve_eval_root_ids(req)
    if not eval_root_ids:
        empty_summary = tsi.EvalResultsSummaryRes() if req.include_summary else None
        return tsi.EvalResultsQueryRes(
            rows=[], total_rows=0, summary=empty_summary, warnings=[]
        )

    all_rows_req = tsi.EvalResultsQueryReq(
        project_id=req.project_id,
        evaluation_call_ids=req.evaluation_call_ids,
        evaluation_run_ids=req.evaluation_run_ids,
        require_intersection=False,
        include_raw_data_rows=req.include_raw_data_rows if req.include_rows else False,
        resolve_row_refs=req.resolve_row_refs if req.include_rows else False,
        include_rows=True,
        include_summary=False,
        summary_require_intersection=None,
        limit=None,
        offset=0,
    )
    all_rows, _, warnings = eval_results_grouped_rows(server, all_rows_req)

    rows: list[tsi.EvalResultsRow] = []
    total_rows = 0
    if req.include_rows:
        rows, total_rows = apply_row_selection(
            all_rows,
            eval_root_ids,
            req.require_intersection,
            req.offset,
            req.limit,
        )

    summary: tsi.EvalResultsSummaryRes | None = None
    if req.include_summary:
        summary_intersection = (
            req.summary_require_intersection
            if req.summary_require_intersection is not None
            else req.require_intersection
        )
        summary_rows, _ = apply_row_selection(
            all_rows,
            eval_root_ids,
            summary_intersection,
            0,
            None,
        )
        eval_call_metadata = fetch_eval_root_metadata(
            server, req.project_id, eval_root_ids
        )
        summary = compute_summary_from_rows(summary_rows, eval_call_metadata)

    return tsi.EvalResultsQueryRes(
        rows=rows, total_rows=total_rows, summary=summary, warnings=warnings
    )


def _process_scorer_output(
    scorer_val: Any,
    scorer_key: str,
    path_parts: list[str],
    eval_call_id: str,
    scorer_stats_map: dict[
        str, dict[tuple[str, str | None], tsi.EvalResultsScorerStats]
    ],
) -> None:
    """Recursively walk a scorer output and aggregate leaf values into stats.

    Creates one EvalResultsScorerStats per flattened leaf dimension.
    """
    if isinstance(scorer_val, bool):
        path_str = ".".join(path_parts) if path_parts else None
        dim_key = (scorer_key, path_str)
        if dim_key not in scorer_stats_map[eval_call_id]:
            scorer_stats_map[eval_call_id][dim_key] = tsi.EvalResultsScorerStats(
                scorer_key=scorer_key,
                path=path_str,
                value_type="binary",
            )
        stats = scorer_stats_map[eval_call_id][dim_key]
        stats.trial_count += 1
        stats.pass_known_count += 1
        if scorer_val:
            stats.pass_true_count += 1
    elif isinstance(scorer_val, (int, float)) and not isinstance(scorer_val, bool):
        path_str = ".".join(path_parts) if path_parts else None
        dim_key = (scorer_key, path_str)
        if dim_key not in scorer_stats_map[eval_call_id]:
            scorer_stats_map[eval_call_id][dim_key] = tsi.EvalResultsScorerStats(
                scorer_key=scorer_key,
                path=path_str,
                value_type="continuous",
            )
        stats = scorer_stats_map[eval_call_id][dim_key]
        stats.trial_count += 1
        numeric_val = float(scorer_val)
        current_total = (stats.numeric_mean or 0.0) * stats.numeric_count
        stats.numeric_count += 1
        stats.numeric_mean = (current_total + numeric_val) / stats.numeric_count
    elif (
        scorer_val is not None
        and isinstance(scorer_val, dict)
        and not isinstance(scorer_val, list)
    ):
        for key, val in scorer_val.items():
            _process_scorer_output(
                val, scorer_key, path_parts + [key], eval_call_id, scorer_stats_map
            )


@_trace_wrap("eval_results_helpers.compute_summary_from_rows")
def compute_summary_from_rows(
    rows: list[tsi.EvalResultsRow],
    eval_call_metadata: dict[str, dict[str, Any]] | None = None,
) -> tsi.EvalResultsSummaryRes:
    """Compute scorer aggregates and pass-rate stats from grouped rows.

    Emits one EvalResultsScorerStats per flattened leaf dimension (e.g.
    token_distance.passed, exact_match) so the summary serves as the canonical
    schema for score dimensions.

    Args:
        rows: Grouped evaluation result rows.
        eval_call_metadata: Optional dict mapping eval_call_id to metadata
            fields (evaluation_ref, model_ref, display_name, trace_id,
            started_at) from the eval root calls.
    """
    eval_summary_map: dict[str, tsi.EvalResultsEvaluationSummary] = {}
    scorer_stats_map: dict[
        str, dict[tuple[str, str | None], tsi.EvalResultsScorerStats]
    ] = {}
    meta = eval_call_metadata or {}

    for row in rows:
        for eval_entry in row.evaluations:
            eval_call_id = eval_entry.evaluation_call_id
            if eval_call_id not in eval_summary_map:
                call_meta = meta.get(eval_call_id, {})
                eval_summary_map[eval_call_id] = tsi.EvalResultsEvaluationSummary(
                    evaluation_call_id=eval_call_id,
                    trial_count=0,
                    evaluation_ref=call_meta.get("evaluation_ref"),
                    model_ref=call_meta.get("model_ref"),
                    display_name=call_meta.get("display_name"),
                    trace_id=call_meta.get("trace_id"),
                    started_at=call_meta.get("started_at"),
                )
                scorer_stats_map[eval_call_id] = {}

            for trial in eval_entry.trials:
                eval_summary_map[eval_call_id].trial_count += 1
                for scorer_key, scorer_val in trial.scores.items():
                    _process_scorer_output(
                        scorer_val,
                        scorer_key,
                        [],
                        eval_call_id,
                        scorer_stats_map,
                    )

    for stats_map in scorer_stats_map.values():
        for scorer_stats in stats_map.values():
            if scorer_stats.pass_known_count > 0:
                scorer_stats.pass_rate = (
                    scorer_stats.pass_true_count / scorer_stats.pass_known_count
                )
            if scorer_stats.trial_count > 0:
                scorer_stats.pass_signal_coverage = (
                    scorer_stats.pass_known_count / scorer_stats.trial_count
                )

    for eval_call_id, eval_summary in eval_summary_map.items():
        eval_summary.scorer_stats = list(scorer_stats_map[eval_call_id].values())

    return tsi.EvalResultsSummaryRes(
        row_count=len(rows),
        evaluations=list(eval_summary_map.values()),
    )
