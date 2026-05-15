"""rescore_worker.py — applies scorer(s) to predictions from a source eval.

Separate from evaluate_model_worker.py: rescoring does not load a model and
does not run predictions. It produces a new evaluation run whose trace tree
mirrors a normal ``Evaluation.evaluate`` run — same predict_and_score
hierarchy, same Evaluation.summarize at the end — but reuses the source
run's model outputs instead of re-invoking the model.

Entry points:
  rescore_predictions(args)       — async def; called directly by SDK (awaited)
  rescore_predictions_sync(args)  — sync wrapper; called by the Kafka worker
"""

import asyncio
import datetime
import logging
from collections.abc import Iterator
from typing import Any, cast

import ddtrace

import weave
from weave.flow.scorer import Scorer, apply_scorer_async, get_scorer_attributes
from weave.flow.util import make_memorable_name
from weave.trace.call import Call
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.isinstance import weave_isinstance
from weave.trace.refs import ObjectRef, Ref
from weave.trace.weave_client import WeaveClient
from weave.trace_server import constants
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_server_interface import RescoringArgs
from weave.trace_server.validation import assert_safe_payload
from weave.trace_server.workers.evaluate_model_worker._rescore_source import (
    _RescoreSource,
    _SourcePredict,
)

logger = logging.getLogger(__name__)

RESCORE_WORKER_MARKER = {"_weave_eval_meta": {"rescore_worker": True}}
PREDICTION_PAGE_SIZE = 100


def rescore_predictions_sync(args: RescoringArgs) -> None:
    """Sync entry point for the Kafka worker. One asyncio.run() at the outer layer."""
    asyncio.run(rescore_predictions(args))


@ddtrace.tracer.wrap(name="rescore_worker.rescore_predictions")
async def rescore_predictions(args: RescoringArgs) -> None:
    """Async implementation — called directly from SDK (await) or via
    rescore_predictions_sync.

    Produces a new-eval trace tree shaped like a normal ``Evaluation.evaluate``
    run, fully owned by the worker:

        Evaluation.evaluate                  (new id, trace_id == id, parent_id=None)
        ├── Evaluation.predict_and_score     (one per source row)
        │   ├── <Model>.predict              (synthetic; faithful copy of source predict
        │   │                                 when present, else generic ``predict``)
        │   └── <Scorer>.score               (one per scorer, traced via
        │                                    apply_scorer_async)
        ├── Evaluation.predict_and_score
        │   └── ...
        └── Evaluation.summarize

    Call ownership invariant: BOTH ``call_start`` and ``call_end`` for the
    eval root are emitted from this client / this process. The rescore
    endpoint deliberately does NOT pre-create the row — pre-creating
    server-side would leave the worker's call_end orphaned in the
    CallBatchProcessor's pairing buffer (see invariant on
    ``CallBatchProcessor``).

    Scorer parenting: ``apply_scorer_async``'s op-traced scorer calls
    naturally land under the current predict_and_score thanks to the
    call-stack push from ``client.create_call(..., use_stack=True)`` on the
    new pas. We do NOT call ``score_create`` — normal evals don't either;
    per-row scores live in ``predict_and_score.output["scores"]`` and
    aggregate scores are emitted via a per-eval ``Evaluation.summarize``
    child.

    column_map handling: ``apply_scorer_async`` invokes
    ``prepare_scorer_op_args``, which honors any ``column_map`` baked into
    the serialized Scorer object. Do not bypass apply_scorer_async or call
    ``scorer.score`` directly — that path drops column_map.
    """
    client = require_weave_client()

    for ref_uri in args.scorer_refs:
        _assert_safe_ref(client, ref_uri, "scorer_ref")

    # ``args.project_id`` arrives at the worker in INTERNAL form (e.g.
    # ``ProjectInternalId:42709008``) — the universal int-to-ext ref converter
    # in run_as_user.py only rewrites strings prefixed with the internal ref
    # scheme, not raw project_id fields. Every call we make through
    # ``client.server`` here goes through the externalize adapter on the worker
    # side, which expects EXTERNAL ``entity/project`` form. Derive the external
    # form from a scorer ref (which IS converted by the int-to-ext walker).
    scorer_obj_ref = Ref.parse_uri(args.scorer_refs[0])
    if not isinstance(scorer_obj_ref, ObjectRef):
        raise TypeError(
            f"Expected an object ref for scorer, got: {args.scorer_refs[0]}"
        )
    project_id = f"{scorer_obj_ref.entity}/{scorer_obj_ref.project}"

    scorers = [_get_valid_scorer(client, ref) for ref in args.scorer_refs]
    scorer_attributes_list = [get_scorer_attributes(s) for s in scorers]

    # raw_scores_by_scorer: indexed by scorer index (not ref URI, not name) to
    # avoid collisions if two scorers share a name. Summary is keyed by
    # scorer_name at the end.
    raw_scores_by_scorer: list[list[Any]] = [[] for _ in scorers]
    failed_score_counts: list[int] = [0 for _ in scorers]
    # Collected per-row to aggregate onto the eval root's output as
    # ``model_latency.mean`` — the compare-table header reads latency from
    # there, not from individual predict subcalls. Mirrors eval.py's
    # auto_summarize over the model_latency column.
    row_model_latencies: list[float] = []

    # Read the source eval call once to lift its self/model refs onto the
    # new-eval's call inputs and per-row predict_and_score calls. Without
    # this the new run's inputs would be missing the Evaluation/Model
    # linkage the frontend uses to render the dataset/model header.
    source_call_res = client.server.call_read(
        tsi.CallReadReq(project_id=project_id, id=args.source_evaluation_run_id)
    )
    source_inputs = (
        source_call_res.call.inputs
        if source_call_res.call and isinstance(source_call_res.call.inputs, dict)
        else {}
    )
    source_eval_ref = source_inputs.get("self") or source_inputs.get("this") or ""
    source_model_ref = source_inputs.get("model") or ""

    # Clone the source Evaluation, swap its ``scorers`` for the new refs,
    # publish as a new version. Without this the new eval's ``self`` would
    # point at the source Evaluation object whose ``scorers`` list still
    # references the OLD scorers — list-view and detail-view surfaces show
    # the source's scorers on the new run, even though per-row scoring was
    # done with the new ones. Falls back to the source ref on any failure
    # (best-effort: the rescore itself still produces correct per-row
    # scores under predict_and_score).
    new_eval_ref = _publish_rescored_evaluation(
        client,
        project_id=project_id,
        source_eval_ref=source_eval_ref,
        new_scorer_refs=list(args.scorer_refs),
        wb_user_id=args.wb_user_id,
    )

    # eval-{date}-{memorable} matches ``default_evaluation_display_name``
    # in eval.py so rescored runs are visually indistinguishable from
    # normal eval runs in the list view.
    display_name = (
        f"eval-{datetime.datetime.now().strftime('%Y-%m-%d')}-{make_memorable_name()}"
    )

    # Emit the new-eval call's call_start from THIS client. The rescore
    # endpoint allocated args.new_evaluation_run_id but deliberately did
    # NOT call_start the row — that's the worker's job (see the
    # call-ownership invariant on CallBatchProcessor).
    #
    # We deliberately bypass ``client.create_call`` here because that
    # helper generates a fresh random ``trace_id`` for parent=None roots,
    # which violates the ``trace_id == id`` invariant the frontend expects
    # for trace roots. evaluation_run_create did ``trace_id=id`` and we
    # mirror that here. Children below pass ``new_eval_call`` as their
    # explicit parent, so they inherit ``trace_id=args.new_evaluation_run_id``
    # — the entire new-eval tree shares one trace_id matching the eval's
    # id, exactly like a normal Evaluation.evaluate run.
    new_eval_call = _start_new_eval_root(
        client,
        new_evaluation_run_id=args.new_evaluation_run_id,
        source_evaluation_run_id=args.source_evaluation_run_id,
        evaluation_ref=new_eval_ref,
        model_ref=source_model_ref,
        display_name=display_name,
    )

    try:
        with weave.attributes(RESCORE_WORKER_MARKER):
            for source in _yield_predict_and_score_sources(
                client, args, project_id, source_model_ref=source_model_ref
            ):
                new_pas_call = client.create_call(
                    op=constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
                    inputs={
                        "self": new_eval_ref,
                        "model": source_model_ref,
                        "example": source.inputs_for_call,
                    },
                    parent=new_eval_call,
                    use_stack=True,
                )

                # Emit a synthetic ``predict`` subcall whose duration mirrors
                # the source row's model_latency, so the eval compare table
                # can display a per-row Latency value. Both the imperative
                # and non-imperative frontend paths derive model_latency
                # from ``ended_at - started_at`` of a predict child of pas
                # — without this subcall the Latency column renders "N/A"
                # for rescored runs.
                _emit_synthetic_predict_call(
                    client,
                    parent_pas_call=new_pas_call,
                    model_ref=source_model_ref,
                    example=source.inputs_for_call,
                    output=source.output,
                    model_latency_seconds=source.model_latency,
                    source_predict=source.source_predict,
                )

                # apply_scorer_async creates op-traced calls; with the new pas
                # on the call stack (use_stack=True above), each scorer call
                # parents to it automatically — same shape as a normal eval
                # where scorers parent to predict_and_score.
                # return_exceptions=True so one scorer failure doesn't abort
                # the whole batch.
                results = await asyncio.gather(
                    *[
                        apply_scorer_async(
                            scorer, source.inputs_for_scorer, source.output
                        )
                        for scorer in scorers
                    ],
                    return_exceptions=True,
                )

                scores_dict: dict[str, Any] = {}
                for i, (result, scorer_ref) in enumerate(
                    zip(results, args.scorer_refs, strict=True)
                ):
                    scorer_name = scorer_attributes_list[i].scorer_name
                    if isinstance(result, Exception):
                        logger.warning(
                            "Scorer %s failed on row in new pas %s: %s",
                            scorer_ref,
                            new_pas_call.id,
                            result,
                        )
                        failed_score_counts[i] += 1
                        scores_dict[scorer_name] = None
                        continue
                    raw_value = result.result
                    scores_dict[scorer_name] = raw_value
                    raw_scores_by_scorer[i].append(raw_value)

                # Per-row predict_and_score output mirrors what
                # ``Evaluation.predict_and_score`` returns in eval.py — output
                # plus the per-scorer score dict plus model_latency. The
                # frontend reads this shape directly.
                client.finish_call(
                    new_pas_call,
                    output={
                        "output": source.output,
                        "scores": scores_dict,
                        "model_latency": source.model_latency,
                    },
                )
                row_model_latencies.append(source.model_latency)

        # Per-scorer failure logs — a scorer failing on 50% of rows is
        # invisible without this.
        for i, scorer_attrs in enumerate(scorer_attributes_list):
            if failed_score_counts[i] > 0:
                logger.warning(
                    "Scorer %s failed on %d row(s) — summary computed on %d/%d results",
                    scorer_attrs.scorer_name,
                    failed_score_counts[i],
                    len(raw_scores_by_scorer[i]),
                    len(raw_scores_by_scorer[i]) + failed_score_counts[i],
                )

        # Mirror eval.py: a normal eval emits an Evaluation.summarize call
        # as a child of the eval run with the aggregate summary as its
        # output. The frontend uses this to render the per-scorer summary
        # panel.
        #
        # Open this call BEFORE invoking ``summarize_fn`` so that when
        # ``summarize_fn`` is itself ``@weave.op``-decorated (i.e. a
        # ``Scorer.summarize`` method on a real Scorer subclass), the op
        # machinery picks up ``summarize_call`` from the call stack as
        # parent. Otherwise each ``Scorer.summarize`` lands as an orphan
        # trace root and the wrapping ``Evaluation.summarize`` shows 0ms
        # because no work happens between create_call and finish_call.
        summarize_call = client.create_call(
            op=constants.EVALUATION_SUMMARIZE_OP_NAME,
            inputs={"self": new_eval_ref},
            parent=new_eval_call,
            use_stack=True,
        )
        try:
            # Mirrors eval.py:230-235: summarize_fn handles both Scorer
            # subclasses (scorer.summarize) and Op-based scorers
            # (auto_summarize). Summary keyed by scorer_attributes.scorer_name
            # — NOT the ref URI.
            summary: dict[str, Any] = {}
            for i, scorer_attrs in enumerate(scorer_attributes_list):
                summary[scorer_attrs.scorer_name] = scorer_attrs.summarize_fn(
                    raw_scores_by_scorer[i]
                )

            # Aggregate model_latency onto the eval root output as
            # ``{"mean": avg}``. The compare-page header reads latency from
            # ``output.model_latency.mean`` on the eval root — without this
            # aggregate the Latency cell renders "N/A" even though per-row
            # latency is correctly recorded on each pas. Mirrors how
            # ``Evaluation.summarize`` in eval.py auto_summarizes the
            # numeric model_latency column over all eval rows.
            if row_model_latencies:
                summary["model_latency"] = {
                    "mean": sum(row_model_latencies) / len(row_model_latencies)
                }
        except Exception as summarize_exc:
            client.fail_call(summarize_call, exception=summarize_exc)
            raise
        client.finish_call(summarize_call, output=summary)

        # End the new-eval call with the rich summary as its output —
        # mirrors a normal Evaluation.evaluate op finish where the eval
        # call's ``output`` IS the summary dict. ``finish_call`` pairs
        # with the ``create_call`` we did at the top via the
        # CallBatchProcessor, sending a single complete record to the
        # trace server.
        client.finish_call(new_eval_call, output=summary)
    except Exception as exc:
        # Always finish the new-eval call so it never dangles in "started"
        # state. ``fail_call`` records the exception on the call so the UI
        # can show why the rescore failed.
        logger.exception(
            "rescore_predictions failed for evaluation_run_id=%s",
            args.new_evaluation_run_id,
        )
        try:
            client.fail_call(new_eval_call, exception=exc)
        except Exception:
            logger.exception(
                "Failed to fail evaluation run %s after rescore failure",
                args.new_evaluation_run_id,
            )
        raise


def _start_new_eval_root(
    client: WeaveClient,
    *,
    new_evaluation_run_id: str,
    source_evaluation_run_id: str,
    evaluation_ref: str,
    model_ref: str,
    display_name: str,
) -> Call:
    """Start the new-eval trace root with ``trace_id == id``.

    Thin wrapper around ``client.create_call``. The ``trace_id == id``
    invariant for trace roots is provided by ``create_call`` itself: when
    ``parent=None`` and ``_call_id_override=X``, ``trace_id`` is also set
    to ``X``. The frontend's "show me everything in this trace" queries
    land on ``trace_id``, so this invariant is what keeps trace-root
    queries finding the entire new-eval tree.

    ``use_stack=False`` because the worker doesn't have a surrounding op
    context, and we don't want the eval root left on the call_context
    stack across the rescore loop. Subsequent ``create_call(parent=...)``
    invocations pass ``new_eval_call`` explicitly.
    """
    return client.create_call(
        op=constants.EVALUATION_RUN_OP_NAME,
        inputs={"self": evaluation_ref, "model": model_ref},
        parent=None,
        attributes={
            constants.WEAVE_ATTRIBUTES_NAMESPACE: {
                constants.EVALUATION_RUN_ATTR_KEY: "true",
                constants.EVALUATION_RUN_EVALUATION_ATTR_KEY: evaluation_ref,
                constants.EVALUATION_RUN_MODEL_ATTR_KEY: model_ref,
                constants.EVALUATION_RUN_SOURCE_ATTR_KEY: source_evaluation_run_id,
            }
        },
        display_name=display_name,
        use_stack=False,
        _call_id_override=new_evaluation_run_id,
    )


def _emit_synthetic_predict_call(
    client: WeaveClient,
    *,
    parent_pas_call: Call,
    model_ref: str,
    example: Any,
    output: Any,
    model_latency_seconds: float,
    source_predict: _SourcePredict | None,
) -> None:
    """Emit a synthetic predict subcall under ``parent_pas_call``.

    When ``source_predict`` is provided (standard evals where the source
    row had a real predict call), the synthetic call is a content-copy:
    op artifact name lifted from the source so the UI chip renders
    ``MyModel.predict`` (not generic ``predict``), source inputs/output/
    summary copied, and duration preserved
    (``ended_at - started_at == source.ended_at - source.started_at``)
    while both timestamps are shifted into the new eval's wall-clock
    window. The op digest will differ from the source's (anonymous-op
    placeholder source), but the chip name, inputs panel, Total Tokens
    column, and Latency column all read correctly.

    When ``source_predict`` is ``None`` (imperative sources that never
    emitted a predict — e.g. ``EvaluationLogger`` flows), fall back to a
    generic ``predict`` op whose duration mirrors the source row's
    ``model_latency``. The frontend's predict-detection still picks it up
    via ``artifactName.includes("predict")``.

    Uses ``client.create_call`` / ``client.finish_call`` with explicit
    ``started_at`` / ``ended_at`` overrides so we pin both timestamps.
    ``use_stack=False`` because scorers parent to the pas (not to
    predict), and we don't want this transient call left on the stack.
    """
    if source_predict is not None:
        op_name = _artifact_name_from_op_uri(source_predict.op_name) or "predict"
        inputs = dict(source_predict.inputs)
        emit_output = source_predict.output
        emit_summary: dict[str, Any] = dict(source_predict.summary)
        # Drop server-derived/per-call fields. The source predict's
        # `summary["weave"]` holds derived fields (trace_name, status,
        # latency_ms, display_name) populated by `make_derived_summary_fields`
        # at read time. Copying them into the synthetic call's client-side
        # summary causes `sum_dict_leaves` to bubble them up into the parent
        # pas/eval `summary["weave"]` as a *list* (one string per child) when
        # `finish_call` rolls children up — which fails CallSchema validation
        # on the next read. `status_counts` is similarly per-call.
        emit_summary.pop("weave", None)
        emit_summary.pop("status_counts", None)
        duration_s = max(
            0.0,
            (source_predict.ended_at - source_predict.started_at).total_seconds(),
        )
    else:
        op_name = "predict"
        inputs = {"self": model_ref, "example": example}
        emit_output = output
        emit_summary = {}
        duration_s = max(0.0, model_latency_seconds)

    started_at = datetime.datetime.now(datetime.timezone.utc)
    ended_at = started_at + datetime.timedelta(seconds=duration_s)

    predict_call = client.create_call(
        op=op_name,
        inputs=inputs,
        parent=parent_pas_call,
        use_stack=False,
        started_at=started_at,
    )
    # Pre-populate summary so finish_call's deep-merge preserves source
    # usage stats — the Total Tokens column reads from ``summary.usage``.
    if emit_summary:
        predict_call.summary = emit_summary
    client.finish_call(predict_call, output=emit_output, ended_at=ended_at)


def _artifact_name_from_op_uri(op_uri: str) -> str | None:
    """Extract the artifact-name segment (``MyModel.predict``) from a
    Weave op ref URI like ``weave:///e/p/op/MyModel.predict:<digest>``.
    Returns ``None`` if the input doesn't match either Weave scheme.
    """
    if not op_uri:
        return None
    marker = "/op/"
    idx = op_uri.rfind(marker)
    if idx < 0:
        return None
    tail = op_uri[idx + len(marker) :]
    name = tail.split(":", 1)[0]
    return name or None


def _publish_rescored_evaluation(
    client: WeaveClient,
    *,
    project_id: str,
    source_eval_ref: str,
    new_scorer_refs: list[str],
    wb_user_id: str | None,
) -> str:
    """Return a ref to a new VERSION of the source Evaluation object whose
    ``scorers`` field matches ``new_scorer_refs`` and whose other fields
    (dataset, trials, etc.) are inherited from ``source_eval_ref``.

    The new eval call's ``self`` input is what list-view and detail-view
    surfaces resolve to render the run's scorer chips. The returned ref
    points at the NEW version's digest — its ``scorers`` field matches
    the run's actual scorers, so chips render correctly. Reusing the
    source digest would surface the source's (now-stale) scorer list —
    a silent mislabeling where the chip says "scorer A" but the actual
    per-row scores were computed by scorer B.

    Strategy: ``obj_read`` the source val, swap its ``scorers`` for
    ``new_scorer_refs``, ``obj_create`` under the SAME ``object_id`` so
    the rescore lands as a new version of the source. This keeps all
    states of "this eval" — author edits and rescore-derived variants
    — in a single object namespace. Source provenance is additionally
    recorded via the ``source_evaluation_run_id`` attribute on the new
    run's call, which is the canonical lineage link for any UI that
    wants to surface "this run was rescored from X".

    Tradeoff: the source object's version history accumulates entries
    not authored by the original creator. Browsing versions of the
    source eval shows rescored variants alongside user edits.

    Fails loudly on any error (bad ref shape, non-dict val, obj_read /
    obj_create failure). A silent fallback to the source ref would
    surface mislabeled chips in the UI — strictly worse than a worker
    failure that the user can retry.
    """
    if not source_eval_ref:
        raise ValueError(
            "Cannot publish rescored Evaluation: source eval ref is empty. "
            "The source call's inputs must carry self/this and model refs."
        )
    source_ref = Ref.parse_uri(source_eval_ref)
    if not isinstance(source_ref, ObjectRef):
        raise TypeError(
            f"Expected an object ref for source eval, got: {source_eval_ref!r}"
        )
    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id=source_ref.name,
            digest=source_ref.digest,
        )
    )
    val = read_res.obj.val
    if not isinstance(val, dict):
        raise TypeError(
            f"Source Evaluation {source_eval_ref!r} val is not a dict "
            f"(got {type(val).__name__}); cannot swap scorers."
        )

    new_val = dict(val)
    new_val["scorers"] = list(new_scorer_refs)

    # Land the rescore as a new version of the source object. obj_create
    # is digest-deduped on (object_id, val), so back-to-back rescores with
    # identical inputs reuse the same digest (no version churn).
    create_res = client.server.obj_create(
        tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=project_id,
                object_id=source_ref.name,
                val=new_val,
                wb_user_id=wb_user_id,
            )
        )
    )
    return f"weave:///{project_id}/object/{source_ref.name}:{create_res.digest}"


def _op_name_matches_any_scheme(op_name: str | None, expected_name: str) -> bool:
    """Match an op_name URI against an expected unversioned name, accepting
    any scheme.

    The trace_server_common.op_name_matches helper only handles the internal
    scheme (``weave-trace-internal://``). The rescore worker runs above the
    server boundary where URIs are typically externalized to ``weave://``,
    so we need a scheme-agnostic check here. Match policy: extract the last
    ``/op/<name>:<version>`` segment, compare ``<name>`` exactly. Falls back
    to plain-string equality for non-URI op_names.
    """
    if not op_name:
        return False
    marker = "/op/"
    idx = op_name.rfind(marker)
    if idx == -1:
        return op_name == expected_name
    tail = op_name[idx + len(marker) :]
    name = tail.split(":", 1)[0]
    return name == expected_name


def _yield_predict_and_score_sources(
    client: WeaveClient,
    args: RescoringArgs,
    project_id: str,
    *,
    source_model_ref: str,
) -> Iterator[_RescoreSource]:
    """Yield one ``_RescoreSource`` per predict_and_score child of the source
    eval call.

    Works for both standard ``Evaluation.evaluate`` runs and imperative
    ``weave.EvaluationLogger`` runs — both surface their per-row data on
    predict_and_score, which is the framework-level boundary in either flow.

    Predicate (mirrors the frontend's ``imperativeAdapter.getDatasetRowCount``):
    any call whose op_name matches ``EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME``
    (ignoring version digest), parented to the source eval call. No status
    filter — a partially-failed source eval is still a valid rescore source.

    Dataset-backed eval inputs land in storage as a ref URI (e.g. a TableRow
    ref into the Dataset's rows table) rather than the row dict. The scorer
    expects a dict, so we batch-deref any ref-shaped ``example`` per page via
    ``refs_read_batch`` — same mechanism the frontend uses in
    ``resolve_eval_inputs``. The original ref form is preserved on
    ``inputs_for_call`` so the new pas call's inputs match the source's
    storage shape; the resolved dict is exposed on ``inputs_for_scorer``.

    Per-page, we also issue one extra ``calls_query_stream`` for the
    grandchildren of source pas to pick out the source predict call (if
    any). The snapshot is attached on ``_RescoreSource.source_predict`` and
    the worker uses it to emit a faithful synthetic predict under the new
    pas (same op_name, inputs, output, summary, duration).
    """
    offset = 0
    while True:
        page = list(
            client.server.calls_query_stream(
                tsi.CallsQueryReq(
                    project_id=project_id,
                    filter=tsi.CallsFilter(
                        parent_ids=[args.source_evaluation_run_id],
                    ),
                    limit=PREDICTION_PAGE_SIZE,
                    offset=offset,
                )
            )
        )
        if not page:
            break

        pas_calls = [
            call
            for call in page
            if _op_name_matches_any_scheme(
                call.op_name,
                constants.EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
            )
        ]

        # Collect any example refs that need batch-resolution.
        example_refs: list[str] = []
        for call in pas_calls:
            example = (
                call.inputs.get("example") if isinstance(call.inputs, dict) else None
            )
            if _is_ref_uri(example):
                example_refs.append(example)

        resolved_by_ref: dict[str, Any] = {}
        if example_refs:
            res = client.server.refs_read_batch(tsi.RefsReadBatchReq(refs=example_refs))
            resolved_by_ref = dict(zip(example_refs, res.vals, strict=True))

        # Batch-query grandchildren of source pas to pick out source predict
        # calls for the synthetic-predict faithful copy. One query per page,
        # filtered down to predict-like calls afterwards.
        predicts_by_pas_id: dict[str, _SourcePredict] = {}
        if pas_calls:
            grandchildren = list(
                client.server.calls_query_stream(
                    tsi.CallsQueryReq(
                        project_id=project_id,
                        filter=tsi.CallsFilter(
                            parent_ids=[c.id for c in pas_calls],
                        ),
                    )
                )
            )
            for gc in grandchildren:
                if gc.parent_id is None:
                    continue
                if gc.parent_id in predicts_by_pas_id:
                    continue  # first predict-like child wins
                if not _is_predict_call(gc, source_model_ref):
                    continue
                predicts_by_pas_id[gc.parent_id] = _source_predict_from_call(gc)

        for call in pas_calls:
            example = (
                call.inputs.get("example") if isinstance(call.inputs, dict) else None
            )
            if isinstance(call.output, dict):
                output_val = call.output.get("output", call.output)
                model_latency = call.output.get("model_latency") or 0.0
            else:
                output_val = call.output
                model_latency = 0.0

            if _is_ref_uri(example):
                resolved = resolved_by_ref.get(example, {})
                inputs_for_scorer = resolved if isinstance(resolved, dict) else {}
                inputs_for_call = example  # preserve ref form on new pas
            elif isinstance(example, dict):
                inputs_for_scorer = example
                inputs_for_call = example
            else:
                inputs_for_scorer = {}
                inputs_for_call = {}

            yield _RescoreSource(
                inputs_for_call=inputs_for_call,
                inputs_for_scorer=inputs_for_scorer,
                output=output_val,
                model_latency=float(model_latency),
                source_predict=predicts_by_pas_id.get(call.id),
            )

        offset += len(page)
        if len(page) < PREDICTION_PAGE_SIZE:
            break


def _is_predict_call(call: tsi.CallSchema, model_ref: str) -> bool:
    """Mirror of the frontend's predict-detection in
    ``tsDataModelHooksEvaluationComparison.ts`` (~line 1392): a subcall is
    the model's predict if ``inputs.self == model_ref`` OR the artifact
    name in ``op_name`` (lowercased) contains ``predict`` or ``invoke``.
    Using the same predicate keeps the synthetic predict we emit consistent
    with what the UI's predict-call lookup picks up.
    """
    if not call.op_name:
        return False
    inputs_self = call.inputs.get("self") if isinstance(call.inputs, dict) else None
    if model_ref and inputs_self == model_ref:
        return True
    marker = "/op/"
    idx = call.op_name.rfind(marker)
    tail = call.op_name[idx + len(marker) :] if idx >= 0 else call.op_name
    artifact_name = tail.split(":", 1)[0].lower()
    return "predict" in artifact_name or "invoke" in artifact_name


def _source_predict_from_call(call: tsi.CallSchema) -> _SourcePredict:
    """Pull just the fields needed for the synthetic-predict copy off of a
    source predict ``CallSchema``. Times default to ``now()`` (zero
    duration) when the source call is malformed/missing them — the worker
    treats that as a best-effort empty predict.
    """
    started_at = call.started_at or datetime.datetime.now(datetime.timezone.utc)
    ended_at = call.ended_at or started_at
    return _SourcePredict(
        op_name=call.op_name or "",
        inputs=call.inputs if isinstance(call.inputs, dict) else {},
        output=call.output,
        started_at=started_at,
        ended_at=ended_at,
        summary=call.summary if isinstance(call.summary, dict) else {},
    )


def _is_ref_uri(val: Any) -> bool:
    """Cheap shape check for the two URI schemes used by Weave."""
    return isinstance(val, str) and (
        val.startswith("weave:///") or val.startswith("weave-trace-internal:///")
    )


def _get_valid_scorer(client: WeaveClient, scorer_ref: str) -> Scorer:
    """Validates and loads a scorer from a ref URI.

    Accepts any Scorer subclass — intentionally more permissive than
    _get_valid_evaluation() which is restricted to LLMAsAJudgeScorer.
    Rescore is a general-purpose operation; that restriction applies only to
    the full eval-model path.

    Security: _assert_safe_ref is called on the scorer_ref before this
    function, so the scorer object has already been validated via
    assert_safe_payload. The isinstance check here is purely a type-level
    guard.
    """
    loaded = client.get(Ref.parse_uri(scorer_ref))
    if weave_isinstance(loaded, Scorer):
        return cast(Scorer, loaded)
    raise TypeError(
        f"Invalid scorer reference: expected Scorer, got {type(loaded).__name__}"
    )


def _assert_safe_ref(client: WeaveClient, ref_uri: str, label: str) -> None:
    """Validates that a ref URI points to an object that passes the
    safe-payload check. Called on all scorer_refs before loading to prevent
    injection via malicious ref payloads.

    SECURITY NOTE: Cross-project authorization is not enforced here. A
    scorer ref that points to a project the calling user cannot read will
    fail at obj_read if the server enforces read-level ACLs, but this
    function does NOT explicitly verify that ref.entity/ref.project matches
    the rescore job's project_id. In V1 this is intentional (scorers are
    naturally shared across projects) but callers should be aware that a
    sufficiently permissioned user can reference scorers from any project
    they can read. A future V2 should add an explicit authorization check
    per scorer ref.
    """
    ref = Ref.parse_uri(ref_uri)
    if not isinstance(ref, ObjectRef):
        raise TypeError(f"Expected an object ref for {label}, got: {ref_uri}")
    project_id = f"{ref.entity}/{ref.project}"
    read_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=project_id,
            object_id=ref.name,
            digest=ref.digest,
        )
    )
    assert_safe_payload(read_res.obj.val, label)
