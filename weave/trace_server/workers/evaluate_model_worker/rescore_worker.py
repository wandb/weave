"""rescore_worker.py — applies scorer(s) to existing predictions from an evaluation run.

Separate from evaluate_model_worker.py: rescoring does not load a model, does not run
predictions, and is not coupled to LLMStructuredCompletionModel or the Evaluation class.

Entry points:
  rescore_predictions(args)       — async def; called directly by SDK (awaited)
  rescore_predictions_sync(args)  — sync wrapper; called by the Kafka worker
"""

import asyncio
import logging
from typing import Any, cast

import ddtrace

import weave
from weave.flow.scorer import Scorer, apply_scorer_async, get_scorer_attributes
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.isinstance import weave_isinstance
from weave.trace.refs import ObjectRef, Ref
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_server_interface import RescoringArgs
from weave.trace_server.validation import assert_safe_payload

logger = logging.getLogger(__name__)

RESCORE_WORKER_MARKER = {"_weave_eval_meta": {"rescore_worker": True}}
PREDICTION_PAGE_SIZE = 100


def rescore_predictions_sync(args: RescoringArgs) -> None:
    """Sync entry point for the Kafka worker. One asyncio.run() at the outer layer."""
    asyncio.run(rescore_predictions(args))


@ddtrace.tracer.wrap(name="rescore_worker.rescore_predictions")
async def rescore_predictions(args: RescoringArgs) -> None:
    """Async implementation — called directly from SDK (await) or via rescore_predictions_sync.

    Applies scorer(s) to all predictions from source_evaluation_run_id, stores raw scorer
    output as Score.value (Any, not flattened to float), then summarizes via
    get_scorer_attributes(scorer).summarize_fn(rows) — matching eval.py:230-235 exactly.
    Summary is keyed by scorer_attributes.scorer_name, NOT the scorer ref URI.

    Note on column_map: apply_scorer_async handles column_map internally via
    prepare_scorer_op_args. The scorer's column_map is part of the serialized Scorer
    object and is restored when the scorer is loaded via client.get(ref). This means
    a scorer that was originally used with a column_map will have its mapping applied
    correctly on rescore — do not bypass apply_scorer_async or call scorer.score() directly.

    Note on call parenting (V1): apply_scorer_async creates traced calls. In the original
    eval flow they are parented to predict_and_score. In the rescore flow, no parent call
    ID is set — scorer calls will be top-level orphaned calls. This is acceptable for V1.
    """
    client = require_weave_client()

    for ref_uri in args.scorer_refs:
        _assert_safe_ref(client, ref_uri, "scorer_ref")

    scorers = [_get_valid_scorer(client, ref) for ref in args.scorer_refs]
    scorer_attributes_list = [get_scorer_attributes(s) for s in scorers]

    try:
        summary = await _score_all_predictions(
            client, args, scorers, scorer_attributes_list
        )
        client.server.evaluation_run_finish(
            tsi.EvaluationRunFinishReq(
                project_id=args.project_id,
                evaluation_run_id=args.new_evaluation_run_id,
                summary=summary,
                wb_user_id=args.wb_user_id,
            )
        )
    except Exception:
        # Always call evaluation_run_finish so the run never dangles in "started" state.
        # On unexpected failure, finish with empty summary so the UI can show it as failed.
        logger.exception(
            "rescore_predictions failed for evaluation_run_id=%s",
            args.new_evaluation_run_id,
        )
        try:
            client.server.evaluation_run_finish(
                tsi.EvaluationRunFinishReq(
                    project_id=args.project_id,
                    evaluation_run_id=args.new_evaluation_run_id,
                    summary={},
                    wb_user_id=args.wb_user_id,
                )
            )
        except Exception:
            logger.exception(
                "Failed to finish evaluation run %s after rescore failure",
                args.new_evaluation_run_id,
            )
        raise


async def _score_all_predictions(
    client: WeaveClient,
    args: RescoringArgs,
    scorers: list[Scorer],
    scorer_attributes_list: list[Any],
) -> dict[str, Any]:
    """Paginate through source predictions, apply each scorer, persist scores, and return summary.

    Summary is keyed by scorer_attributes.scorer_name (NOT the scorer ref URI) to match
    eval.py:230-235. raw_scores_by_scorer is indexed by scorer position rather than name
    to avoid collisions when two scorers share a name.
    """
    # failed_score_counts tracks per-scorer failures so partial failures surface in logs —
    # a scorer failing on 50% of predictions is invisible without this.
    raw_scores_by_scorer: list[list[Any]] = [[] for _ in scorers]
    failed_score_counts: list[int] = [0 for _ in scorers]

    with weave.attributes(RESCORE_WORKER_MARKER):
        offset = 0
        while True:
            page = list(
                client.server.prediction_list(
                    tsi.PredictionListReq(
                        project_id=args.project_id,
                        evaluation_run_id=args.source_evaluation_run_id,
                        limit=PREDICTION_PAGE_SIZE,
                        offset=offset,
                    )
                )
            )
            if not page:
                break

            for prediction in page:
                await _score_one_prediction(
                    client,
                    args,
                    scorers,
                    prediction,
                    raw_scores_by_scorer,
                    failed_score_counts,
                )

            offset += len(page)
            if len(page) < PREDICTION_PAGE_SIZE:
                break

    for i, scorer_attrs in enumerate(scorer_attributes_list):
        if failed_score_counts[i] > 0:
            logger.warning(
                "Scorer %s failed on %d prediction(s) — summary computed on %d/%d results",
                scorer_attrs.scorer_name,
                failed_score_counts[i],
                len(raw_scores_by_scorer[i]),
                len(raw_scores_by_scorer[i]) + failed_score_counts[i],
            )

    # Mirrors eval.py:230-235: summarize_fn handles both Scorer subclasses
    # (scorer.summarize) and Op-based scorers (auto_summarize).
    summary: dict[str, Any] = {}
    for i, scorer_attrs in enumerate(scorer_attributes_list):
        summary[scorer_attrs.scorer_name] = scorer_attrs.summarize_fn(
            raw_scores_by_scorer[i]
        )
    return summary


async def _score_one_prediction(
    client: WeaveClient,
    args: RescoringArgs,
    scorers: list[Scorer],
    prediction: tsi.PredictionReadRes,
    raw_scores_by_scorer: list[list[Any]],
    failed_score_counts: list[int],
) -> None:
    # apply_scorer_async handles column_map, op tracing, kwargs — do not call scorer.score()
    # directly. return_exceptions=True so one scorer failure doesn't abort the batch.
    results = await asyncio.gather(
        *[
            apply_scorer_async(scorer, prediction.inputs, prediction.output)
            for scorer in scorers
        ],
        return_exceptions=True,
    )

    for i, (result, scorer_ref) in enumerate(
        zip(results, args.scorer_refs, strict=True)
    ):
        if isinstance(result, BaseException):
            logger.warning(
                "Scorer %s failed on prediction %s: %s",
                scorer_ref,
                prediction.prediction_id,
                result,
            )
            failed_score_counts[i] += 1
            continue
        raw_value = result.result  # raw Any — dict, bool, float, etc.
        client.server.score_create(
            tsi.ScoreCreateReq(
                project_id=args.project_id,
                prediction_id=prediction.prediction_id,
                scorer=scorer_ref,
                value=raw_value,
                evaluation_run_id=args.new_evaluation_run_id,
                wb_user_id=args.wb_user_id,
            )
        )
        raw_scores_by_scorer[i].append(raw_value)


def _get_valid_scorer(client: WeaveClient, scorer_ref: str) -> Scorer:
    """Validates and loads a scorer from a ref URI.

    Accepts any Scorer subclass — intentionally more permissive than _get_valid_evaluation()
    which is restricted to LLMAsAJudgeScorer. Rescore is a general-purpose operation;
    that restriction applies only to the full eval-model path.

    Security: _assert_safe_ref is called on the scorer_ref before this function, so
    the scorer object has already been validated via assert_safe_payload. The isinstance
    check here is purely a type-level guard.
    """
    loaded = client.get(Ref.parse_uri(scorer_ref))
    if weave_isinstance(loaded, Scorer):
        return cast(Scorer, loaded)
    raise TypeError(
        f"Invalid scorer reference: expected Scorer, got {type(loaded).__name__}"
    )


def _assert_safe_ref(client: WeaveClient, ref_uri: str, label: str) -> None:
    """Validates that a ref URI points to an object that passes the safe-payload check.
    Called on all scorer_refs before loading to prevent injection via malicious ref payloads.

    SECURITY NOTE: Cross-project authorization is not enforced here. A scorer ref that
    points to a project the calling user cannot read will fail at obj_read if the server
    enforces read-level ACLs, but this function does NOT explicitly verify that
    ref.entity/ref.project matches the rescore job's project_id. In V1 this is intentional
    (scorers are naturally shared across projects) but callers should be aware that a
    sufficiently permissioned user can reference scorers from any project they can read.
    A future V2 should add an explicit authorization check per scorer ref.
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
