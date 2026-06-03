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
from weave.flow.scorer import (
    Scorer,
    ScorerAttributes,
    apply_scorer_async,
    get_scorer_attributes,
)
from weave.trace.context.weave_client_context import require_secure_weave_client
from weave.trace.isinstance import weave_isinstance
from weave.trace.refs import Ref
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_server_interface import RescoringArgs

logger = logging.getLogger(__name__)

RESCORE_WORKER_MARKER = {"_weave_eval_meta": {"rescore_worker": True}}
PREDICTION_PAGE_SIZE = 100
# Bounds in-flight scoring tasks per rescore job so a single job doesn't pin the
# event loop or stampede the LLM provider with every prediction at once.
PREDICTION_CONCURRENCY = 10


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

    Safety: uses require_secure_weave_client(), which locks the decode guard so any
    user-supplied custom-object payload (e.g. a malicious Op-bearing scorer) will raise
    UnsafeDeserializationError when `client.get` reconstructs it. We do not need a
    separate `obj_read`+payload check in this module — the security boundary is the
    secure client, not a pre-flight validation pass.

    Note on column_map: apply_scorer_async handles column_map internally via
    prepare_scorer_op_args. The scorer's column_map is part of the serialized Scorer
    object and is restored when the scorer is loaded via client.get(ref). This means
    a scorer that was originally used with a column_map will have its mapping applied
    correctly on rescore — do not bypass apply_scorer_async or call scorer.score() directly.

    Note on call parenting (V1): apply_scorer_async creates traced calls. In the original
    eval flow they are parented to predict_and_score. In the rescore flow, no parent call
    ID is set — scorer calls will be top-level orphaned calls. This is acceptable for V1.

    Failure handling: a single `try` wraps the scoring loop and the success-path finish
    call. On unexpected failure we still attempt evaluation_run_finish with an empty
    summary so the run never dangles in 'started' state, and we DO NOT re-raise. Re-
    raising would let Kafka redeliver the message, causing the next attempt to double-
    write scores into the (already finished) new_evaluation_run_id. Operators observe
    failures via logs and the empty-summary signal; we trade retry on transient infra
    failures for predictable behavior on persistent ones, which is the worse failure
    mode here.
    """
    client = require_secure_weave_client()

    scorers = [_get_valid_scorer(client, ref) for ref in args.scorer_refs]
    scorer_attributes_list: list[ScorerAttributes] = [
        get_scorer_attributes(s) for s in scorers
    ]

    try:
        summary = await _score_all_predictions(
            client, args, scorers, scorer_attributes_list
        )
        await asyncio.to_thread(
            client.server.evaluation_run_finish,
            tsi.EvaluationRunFinishReq(
                project_id=args.project_id,
                evaluation_run_id=args.new_evaluation_run_id,
                summary=summary,
                wb_user_id=args.wb_user_id,
            ),
        )
    except Exception:
        logger.exception(
            "rescore_predictions failed for evaluation_run_id=%s",
            args.new_evaluation_run_id,
        )
        try:
            await asyncio.to_thread(
                client.server.evaluation_run_finish,
                tsi.EvaluationRunFinishReq(
                    project_id=args.project_id,
                    evaluation_run_id=args.new_evaluation_run_id,
                    summary={},
                    wb_user_id=args.wb_user_id,
                ),
            )
        except Exception:
            logger.exception(
                "Failed to finish evaluation run %s after rescore failure",
                args.new_evaluation_run_id,
            )
        # Intentionally do not re-raise — see docstring.


async def _score_all_predictions(
    client: WeaveClient,
    args: RescoringArgs,
    scorers: list[Scorer],
    scorer_attributes_list: list[ScorerAttributes],
) -> dict[str, Any]:
    """Paginate through source predictions, score concurrently, persist, and summarize.

    Summary is keyed by ScorerAttributes.scorer_name (matches eval.py:230-235).
    `raw_scores_by_index` is keyed by scorer position rather than name to avoid
    collisions when two scorers share a name.

    Pagination uses offset/limit because PredictionListReq does not currently support
    a cursor. This is safe here because the source eval run is finished by the time
    rescore is dispatched — no rows should be added or reordered while we read.
    """
    # failed_score_counts tracks per-scorer failures (both scorer-side and persist-side)
    # so partial failures surface in logs — a scorer failing on 50% of predictions is
    # invisible without this.
    raw_scores_by_index: list[list[Any]] = [[] for _ in scorers]
    failed_score_counts: list[int] = [0 for _ in scorers]
    semaphore = asyncio.Semaphore(PREDICTION_CONCURRENCY)

    with weave.attributes(RESCORE_WORKER_MARKER):
        offset = 0
        while True:
            page = await asyncio.to_thread(_fetch_prediction_page, client, args, offset)
            await asyncio.gather(
                *[
                    _score_one_prediction(
                        client,
                        args,
                        scorers,
                        prediction,
                        raw_scores_by_index,
                        failed_score_counts,
                        semaphore,
                    )
                    for prediction in page
                ]
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
                len(raw_scores_by_index[i]),
                len(raw_scores_by_index[i]) + failed_score_counts[i],
            )

    # Mirrors eval.py:230-235: summarize_fn handles both Scorer subclasses
    # (scorer.summarize) and Op-based scorers (auto_summarize).
    summary: dict[str, Any] = {}
    for i, scorer_attrs in enumerate(scorer_attributes_list):
        summary[scorer_attrs.scorer_name] = scorer_attrs.summarize_fn(
            raw_scores_by_index[i]
        )
    return summary


def _fetch_prediction_page(
    client: WeaveClient, args: RescoringArgs, offset: int
) -> list[tsi.PredictionReadRes]:
    return list(
        client.server.prediction_list(
            tsi.PredictionListReq(
                project_id=args.project_id,
                evaluation_run_id=args.source_evaluation_run_id,
                limit=PREDICTION_PAGE_SIZE,
                offset=offset,
            )
        )
    )


async def _score_one_prediction(
    client: WeaveClient,
    args: RescoringArgs,
    scorers: list[Scorer],
    prediction: tsi.PredictionReadRes,
    raw_scores_by_index: list[list[Any]],
    failed_score_counts: list[int],
    semaphore: asyncio.Semaphore,
) -> None:
    # apply_scorer_async handles column_map, op tracing, kwargs — do not call scorer.score()
    # directly. return_exceptions=True so one scorer failure doesn't abort the batch.
    async with semaphore:
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
        try:
            await asyncio.to_thread(
                client.server.score_create,
                tsi.ScoreCreateReq(
                    project_id=args.project_id,
                    prediction_id=prediction.prediction_id,
                    scorer=scorer_ref,
                    value=raw_value,
                    evaluation_run_id=args.new_evaluation_run_id,
                    wb_user_id=args.wb_user_id,
                ),
            )
        except Exception as e:
            # Persisting a single score failed (usually transient: network, DB). Don't
            # abort the whole batch — surface in logs and per-scorer failure count.
            logger.warning(
                "Persisting score for scorer %s on prediction %s failed: %s",
                scorer_ref,
                prediction.prediction_id,
                e,
            )
            failed_score_counts[i] += 1
            continue
        raw_scores_by_index[i].append(raw_value)


def _get_valid_scorer(client: WeaveClient, scorer_ref: str) -> Scorer:
    """Validates and loads a scorer from a ref URI.

    Accepts any Scorer subclass — intentionally more permissive than _get_valid_evaluation()
    which is restricted to LLMAsAJudgeScorer. Rescore is a general-purpose operation;
    that restriction applies only to the full eval-model path.

    Safety: relies on require_secure_weave_client() in the caller — `client.get` will
    raise UnsafeDeserializationError if the scorer payload contains a code-bearing
    CustomWeaveType. No separate obj_read pre-flight is needed.

    Cross-project authorization: not enforced here. A scorer ref pointing to a different
    project will fail at obj_read if the server enforces read-level ACLs, but this
    function does not explicitly verify ref.entity/ref.project matches args.project_id.
    In V1 this is intentional (scorers are naturally shared across projects). A future
    V2 should add an explicit per-ref auth check.
    """
    loaded = client.get(Ref.parse_uri(scorer_ref))
    if weave_isinstance(loaded, Scorer):
        return cast(Scorer, loaded)
    raise TypeError(
        f"Invalid scorer reference: expected Scorer, got {type(loaded).__name__}"
    )
