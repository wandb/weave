from __future__ import annotations

import logging
from typing import Any

import weave
from weave.evaluation.eval_imperative import EvaluationLogger
from weave.trace.call import Call
from weave.trace.context import weave_client_context

logger = logging.getLogger(__name__)

# Default name used when publishing candidate prompts as a versioned Weave
# object. Each iteration's accepted candidate becomes a new version of this
# object so users can browse the full prompt history in the Weave UI.
CANDIDATE_OBJECT_NAME = "gepa_candidate"


def _safe(value: Any) -> Any:
    """Return a value that is safe to log without mutating the caller's state."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    return repr(value)


def _kind_attrs(kind: str) -> dict[str, Any]:
    return {"weave": {"kind": kind}}


def _count_trajectory_failures(trajectories: list[Any] | None) -> int:
    """Heuristically count per-example failures in an adapter's trajectories.

    Adapter trajectory shapes vary: DSPy emits `FailedPrediction` objects on
    parse/runtime errors, DefaultAdapter surfaces an error string in a
    `feedback` field, and other adapters can use arbitrary dict keys. We
    detect a few common shapes and count conservatively. Never raises —
    returns 0 on any unexpected input.
    """
    if not trajectories:
        return 0
    count = 0
    for traj in trajectories:
        try:
            type_name = type(traj).__name__
            if type_name == "FailedPrediction":
                count += 1
                continue
            if isinstance(traj, dict):
                if traj.get("error") or traj.get("exception"):
                    count += 1
                    continue
                prediction = traj.get("prediction")
                if (
                    prediction is not None
                    and type(prediction).__name__ == "FailedPrediction"
                ):
                    count += 1
        except Exception:
            continue
    return count


def _publish_candidate(candidate: dict[str, str]) -> str | None:
    """Publish a candidate prompt dict as a versioned Weave object.

    Returns the ref URI as a string, or None if publishing failed (e.g.,
    weave client not initialized). Failures are logged but never raised —
    callbacks must not abort the optimization loop.
    """
    if not candidate:
        return None
    try:
        ref = weave.publish(dict(candidate), name=CANDIDATE_OBJECT_NAME)
        return str(ref.uri()) if ref is not None else None
    except Exception:
        logger.exception("Failed to publish GEPA candidate version")
        return None


class WeaveGEPACallback:
    """GEPA callback that mirrors optimization lifecycle events into Weave.

    Implements a subset of the `gepa.core.callbacks.GEPACallback` protocol.
    GEPA dispatches callbacks via `getattr(..., method_name, None)`, so only
    the methods we care about need to be defined.

    Side effects beyond span emission:
    - Publishes the seed candidate (on optimization start) and each accepted
      candidate (on valset evaluation) as versioned `gepa_candidate` Weave
      objects, so prompt history is browsable in the UI.
    - Logs a Weave Evaluation on each full-valset evaluation, with per-example
      judge scores and candidate metadata.
    """

    def __init__(self) -> None:
        self._iteration_call: Call | None = None
        self._evaluation_call: Call | None = None
        self._proposal_call: Call | None = None
        self._valset_call: Call | None = None

    def on_optimization_start(self, event: dict[str, Any]) -> None:
        # Seed the candidate version history with the initial prompt so the
        # first published version matches what GEPA started from.
        seed = event.get("seed_candidate") or {}
        _publish_candidate(seed)

    def on_iteration_start(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        iteration = event.get("iteration")
        self._iteration_call = gc.create_call(
            "gepa.iteration",
            inputs={"iteration": iteration},
            display_name=f"gepa.iteration.{iteration}",
        )

    def on_iteration_end(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        if self._iteration_call is not None:
            # try/finally so a transient `finish_call` failure can't leak the
            # call reference. GEPA's notify_callbacks swallows exceptions and
            # only logs a warning; without this, the next iteration_start
            # would overwrite the still-set reference and the previous span
            # would stay open in the trace forever.
            try:
                gc.finish_call(
                    self._iteration_call,
                    {
                        "iteration": event.get("iteration"),
                        "proposal_accepted": event.get("proposal_accepted"),
                    },
                )
            finally:
                self._iteration_call = None

    def on_evaluation_start(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        inputs = {
            "iteration": event.get("iteration"),
            "candidate_idx": event.get("candidate_idx"),
            "batch_size": event.get("batch_size"),
            "capture_traces": event.get("capture_traces"),
            "is_seed_candidate": event.get("is_seed_candidate"),
        }
        self._evaluation_call = gc.create_call(
            "gepa.evaluate",
            inputs=inputs,
            attributes=_kind_attrs("scorer"),
            display_name="gepa.evaluate",
        )

    def on_evaluation_end(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        if self._evaluation_call is not None:
            scores = event.get("scores") or []
            avg = sum(scores) / len(scores) if scores else None
            trajectories = event.get("trajectories")
            num_failures = _count_trajectory_failures(trajectories)
            outputs = {
                "scores": _safe(scores),
                "average_score": avg,
                "has_trajectories": event.get("has_trajectories"),
                "objective_scores": _safe(event.get("objective_scores")),
                "num_failures": num_failures,
            }
            try:
                gc.finish_call(self._evaluation_call, outputs)
            finally:
                self._evaluation_call = None

    def on_reflective_dataset_built(self, event: dict[str, Any]) -> None:
        """Capture the dataset that will be fed to the reflection LM.

        This is the single most distinctive GEPA artifact: the per-component
        `{Inputs, Generated Outputs, Feedback}` records the reflection LM
        reads to propose prompt rewrites. We emit it as a point span so the
        exact feedback driving each proposal is inspectable from the trace.
        """
        gc = weave_client_context.require_weave_client()
        dataset = event.get("dataset") or {}
        components = event.get("components") or list(dataset.keys())
        call = gc.create_call(
            "gepa.reflective_dataset",
            inputs={
                "iteration": event.get("iteration"),
                "candidate_idx": event.get("candidate_idx"),
                "components": _safe(components),
            },
            display_name="gepa.reflective_dataset",
        )
        examples_per_component = {
            str(name): len(rows) if isinstance(rows, list) else 0
            for name, rows in dataset.items()
        }
        gc.finish_call(
            call,
            {
                "examples_per_component": examples_per_component,
                "dataset": _safe(dataset),
            },
        )

    def on_proposal_start(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        reflective_dataset = event.get("reflective_dataset") or {}
        inputs = {
            "iteration": event.get("iteration"),
            "parent_candidate": _safe(event.get("parent_candidate")),
            "components": _safe(event.get("components")),
            # Pass the full dataset so the proposal span is self-contained:
            # click into `gepa.propose` and you see both the feedback that
            # drove the proposal AND the reflection-LM chat completion that
            # nested underneath.
            "reflective_dataset": _safe(reflective_dataset),
        }
        self._proposal_call = gc.create_call(
            "gepa.propose",
            inputs=inputs,
            display_name="gepa.propose",
        )

    def on_proposal_end(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        if self._proposal_call is not None:
            outputs = {
                "new_instructions": _safe(event.get("new_instructions")),
            }
            try:
                gc.finish_call(self._proposal_call, outputs)
            finally:
                self._proposal_call = None

    def on_valset_evaluated(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        iteration = event.get("iteration")
        candidate_idx = event.get("candidate_idx")
        candidate = event.get("candidate") or {}

        # Publish this candidate as a new version of the `gepa_candidate`
        # Weave object so each iteration's prompt is browsable.
        candidate_ref = _publish_candidate(candidate)

        call = gc.create_call(
            "gepa.valset_evaluated",
            inputs={
                "iteration": iteration,
                "candidate_idx": candidate_idx,
                "num_examples_evaluated": event.get("num_examples_evaluated"),
                "total_valset_size": event.get("total_valset_size"),
                "candidate_ref": candidate_ref,
            },
            attributes=_kind_attrs("scorer"),
            display_name="gepa.valset_evaluated",
        )

        # Log a Weave Evaluation using the per-example judge/metric scores so
        # each valset eval is inspectable in the Evaluations tab.
        self._log_valset_evaluation(event, candidate_ref)

        gc.finish_call(
            call,
            {
                "average_score": event.get("average_score"),
                "is_best_program": event.get("is_best_program"),
                "candidate_ref": candidate_ref,
            },
        )

    def on_error(self, event: dict[str, Any]) -> None:
        """Mark any still-open span as errored when GEPA catches an exception.

        GEPA dispatches `ErrorEvent` when a step raises in a way that might
        still let optimization continue. The span where the error actually
        happened (usually `gepa.evaluate` or `gepa.propose`) is still open
        on the Weave call stack at this point; finishing it with the
        exception both terminates the span cleanly AND surfaces the error
        in the UI at the exact call that produced it. We also annotate the
        closed span's output with GEPA's engine-level metadata (iteration,
        `will_continue`) so the "was this fatal?" context isn't lost.

        Aggregate error counts ("how many errors did this run hit?") fall
        out of filtering Weave calls by `status=error` under the
        `gepa.optimize` root — no separate `gepa.error` span needed.

        If nothing is open when the error fires (rare), we fall back to a
        point span so the event is still visible.
        """
        gc = weave_client_context.require_weave_client()
        exception = event.get("exception")
        exc_for_finish = exception if isinstance(exception, BaseException) else None
        error_output = {
            "iteration": event.get("iteration"),
            "exception_type": type(exception).__name__
            if exception is not None
            else None,
            "exception_message": str(exception) if exception is not None else None,
            "will_continue": event.get("will_continue"),
        }

        finished_any = False
        # Close open spans in inner-to-outer order so the deepest span (where
        # the exception actually originated) is the one annotated with the
        # error detail.
        for attr in ("_proposal_call", "_evaluation_call"):
            call = getattr(self, attr, None)
            if call is None:
                continue
            try:
                gc.finish_call(call, error_output, exc_for_finish)
                finished_any = True
            except Exception:
                logger.exception("Failed to finish %s on error", attr)
            setattr(self, attr, None)

        if finished_any:
            return

        # Fallback: no open span to annotate. Emit a point span so the error
        # is still visible in the trace.
        point = gc.create_call(
            "gepa.error",
            inputs=error_output,
            display_name=f"gepa.error.{error_output['exception_type'] or 'Error'}",
        )
        gc.finish_call(point, None, exc_for_finish)

    def _log_valset_evaluation(
        self, event: dict[str, Any], candidate_ref: str | None
    ) -> None:
        scores_by_val_id = event.get("scores_by_val_id") or {}
        if not scores_by_val_id:
            return
        outputs_by_val_id = event.get("outputs_by_val_id") or {}
        candidate = event.get("candidate") or {}
        iteration = event.get("iteration")
        candidate_idx = event.get("candidate_idx")

        try:
            ev = EvaluationLogger(
                name=f"gepa_valset_iter{iteration}_cand{candidate_idx}",
                model={
                    "name": f"gepa_candidate_iter{iteration}_cand{candidate_idx}",
                    "candidate": _safe(candidate),
                    "candidate_ref": candidate_ref,
                    "iteration": iteration,
                    "candidate_idx": candidate_idx,
                },
                dataset=[{"val_id": str(k)} for k in scores_by_val_id.keys()],
            )
            for val_id, score in scores_by_val_id.items():
                output = outputs_by_val_id.get(val_id) if outputs_by_val_id else None
                with ev.log_prediction(
                    inputs={"val_id": str(val_id)}, output=_safe(output)
                ) as pred:
                    try:
                        pred.log_score(scorer="metric", score=float(score))
                    except (TypeError, ValueError):
                        pred.log_score(scorer="metric", score=_safe(score))
            ev.log_summary(
                {
                    "average_score": event.get("average_score"),
                    "is_best_program": event.get("is_best_program"),
                    "num_examples_evaluated": event.get("num_examples_evaluated"),
                    "total_valset_size": event.get("total_valset_size"),
                }
            )
        except Exception:
            logger.exception("Failed to log GEPA valset evaluation")
