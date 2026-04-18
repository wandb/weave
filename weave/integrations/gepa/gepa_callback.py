from __future__ import annotations

from typing import Any

from weave.trace.call import Call
from weave.trace.context import weave_client_context


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


class WeaveGEPACallback:
    """GEPA callback that mirrors optimization lifecycle events into Weave.

    Implements a subset of the `gepa.core.callbacks.GEPACallback` protocol.
    GEPA dispatches callbacks via `getattr(..., method_name, None)`, so only
    the methods we care about need to be defined.
    """

    def __init__(self) -> None:
        self._iteration_call: Call | None = None
        self._evaluation_call: Call | None = None
        self._proposal_call: Call | None = None
        self._valset_call: Call | None = None

    def on_iteration_start(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        iteration = event.get("iteration")
        self._iteration_call = gc.create_call(
            "gepa.iteration",
            inputs={"iteration": iteration},
            attributes=_kind_attrs("agent"),
            display_name=f"gepa.iteration.{iteration}",
        )

    def on_iteration_end(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        if self._iteration_call is not None:
            gc.finish_call(
                self._iteration_call,
                {
                    "iteration": event.get("iteration"),
                    "proposal_accepted": event.get("proposal_accepted"),
                },
            )
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
            outputs = {
                "scores": _safe(scores),
                "average_score": avg,
                "has_trajectories": event.get("has_trajectories"),
                "objective_scores": _safe(event.get("objective_scores")),
            }
            gc.finish_call(self._evaluation_call, outputs)
            self._evaluation_call = None

    def on_proposal_start(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        inputs = {
            "iteration": event.get("iteration"),
            "parent_candidate": _safe(event.get("parent_candidate")),
            "components": _safe(event.get("components")),
        }
        self._proposal_call = gc.create_call(
            "gepa.propose",
            inputs=inputs,
            attributes=_kind_attrs("llm"),
            display_name="gepa.propose",
        )

    def on_proposal_end(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        if self._proposal_call is not None:
            outputs = {
                "new_instructions": _safe(event.get("new_instructions")),
            }
            gc.finish_call(self._proposal_call, outputs)
            self._proposal_call = None

    def on_valset_evaluated(self, event: dict[str, Any]) -> None:
        gc = weave_client_context.require_weave_client()
        call = gc.create_call(
            "gepa.valset_evaluated",
            inputs={
                "iteration": event.get("iteration"),
                "candidate_idx": event.get("candidate_idx"),
                "num_examples_evaluated": event.get("num_examples_evaluated"),
                "total_valset_size": event.get("total_valset_size"),
            },
            attributes=_kind_attrs("scorer"),
            display_name="gepa.valset_evaluated",
        )
        gc.finish_call(
            call,
            {
                "average_score": event.get("average_score"),
                "is_best_program": event.get("is_best_program"),
            },
        )
