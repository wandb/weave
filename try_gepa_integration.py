r"""Manual smoke-test for the Weave <-> GEPA integration.

Runs `gepa.optimize()` end-to-end and exercises every surface the
integration produces, so you can click through the Weave UI and verify
each one:

    Traces tab:
        gepa.optimize
        ├── gepa.valset_evaluated         (scorer — seed full-valset eval)
        └── gepa.iteration
            ├── gepa.evaluate             (scorer — minibatch of current)
            ├── gepa.reflective_dataset   (exact feedback shown to the
            │                              reflection LM)
            ├── gepa.propose              (orchestration; the LLM call lives
            │   │                          as a nested child, below)
            │   └── reflection_lm         (the actual chat completion —
            │                              only nests when the reflection
            │                              LM is a weave.op or an auto-
            │                              patched provider like litellm
            │                              / openai)
            ├── gepa.evaluate             (scorer — minibatch of proposed)
            └── gepa.valset_evaluated     (scorer — full valset on accept)

    Evaluations tab:
        gepa_valset_iter0_cand0  — seed full-valset eval (per-example scores)
        gepa_valset_iter1_cand1  — accepted candidate eval (if improvement found)

    Objects tab:
        gepa_candidate v0  — seed prompt
        gepa_candidate v1  — iter-1 accepted prompt
        ...

Usage (from repo root):

    # Offline: stub reflection LM, no API calls.
    uv run --extra gepa python try_gepa_integration.py

    # Real reflection LM via litellm (needs OPENAI_API_KEY / etc.).
    GEPA_REAL_LM=openai/gpt-4o-mini \\
        uv run --extra gepa python try_gepa_integration.py

Env vars:
    WEAVE_PROJECT  — target Weave project (default: "gepa-smoketest")
    GEPA_REAL_LM   — litellm model string for the reflection LM; if unset,
                     a deterministic stub is used so the run stays offline.
    GEPA_BUDGET    — int, metric-call budget (default: 12)
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import gepa
from gepa.core.adapter import EvaluationBatch

import weave


class ConcisenessAdapter:
    """Toy GEPAAdapter: score = 1 - min(1, len(instructions) / 100).

    Shorter instructions win, so GEPA's job is to compress the seed prompt.
    Works fully offline — `evaluate` does no network I/O.
    """

    def evaluate(
        self,
        batch: Sequence[Any],
        candidate: dict[str, str],
        capture_traces: bool = False,
    ) -> EvaluationBatch:
        text = candidate.get("instructions", "")
        score = max(0.0, 1.0 - min(1.0, len(text) / 100.0))
        outputs = [f"[instructions: {text!r}] answered: {ex!r}" for ex in batch]
        scores = [score for _ in batch]
        trajectories = (
            [{"candidate_len": len(text), "example": ex} for ex in batch]
            if capture_traces
            else None
        )
        return EvaluationBatch(outputs=outputs, scores=scores, trajectories=trajectories)

    def make_reflective_dataset(
        self,
        candidate: dict[str, str],
        eval_batch: EvaluationBatch,
        components_to_update: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            component: [
                {
                    "Inputs": {"text": candidate.get(component, "")},
                    "Outputs": out,
                    "Score": score,
                    "Feedback": "Shorter is better.",
                }
                for out, score in zip(eval_batch.outputs, eval_batch.scores, strict=True)
            ]
            for component in components_to_update
        }

    # GEPA's reflective-mutation proposer does `if adapter.propose_new_texts
    # is not None` (no hasattr), so the attribute must exist and be None to
    # fall through to the user-supplied `reflection_lm` code path.
    propose_new_texts = None


# Wrap the stub reflection LM as a `weave.op` so that even without litellm /
# openai auto-patching configured, a Weave trace is emitted for each
# reflection call — and lands as a child of `gepa.propose`.
@weave.op
def _stub_reflection_lm(prompt: str | list[dict[str, Any]]) -> str:
    # GEPA parses the candidate out of a fenced code block in the response.
    return "```\nBe brief.\n```"


def _build_reflection_lm() -> Any:
    model = os.getenv("GEPA_REAL_LM")
    if not model:
        return _stub_reflection_lm

    import litellm

    @weave.op(name=f"litellm.{model.replace('/', '.')}")
    def _lm(prompt: str | list[dict[str, Any]]) -> str:
        messages = (
            prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]
        )
        resp = litellm.completion(model=model, messages=messages)
        return resp.choices[0].message.content or ""

    return _lm


def main() -> None:
    project = os.getenv("WEAVE_PROJECT", "gepa-smoketest")
    budget = int(os.getenv("GEPA_BUDGET", "12"))

    weave.init(project)

    seed = {
        "instructions": (
            "Please read the question very carefully and then give me a detailed, "
            "thoughtful, well-reasoned answer explaining every step."
        )
    }
    trainset = [{"q": f"train-{i}"} for i in range(3)]
    valset = [{"q": f"val-{i}"} for i in range(2)]

    print(f"Seed instructions ({len(seed['instructions'])} chars):")
    print(f"  {seed['instructions']!r}")
    print()
    print(f"Budget: {budget} metric calls")
    print(f"Reflection LM: {os.getenv('GEPA_REAL_LM') or 'stub (offline)'}")
    print()

    result = gepa.optimize(
        seed_candidate=seed,
        trainset=trainset,
        valset=valset,
        adapter=ConcisenessAdapter(),
        reflection_lm=_build_reflection_lm(),
        max_metric_calls=budget,
        display_progress_bar=False,
        raise_on_exception=True,
        skip_perfect_score=False,
    )

    print()
    print("=== GEPA run complete ===")
    print(f"best_idx:       {getattr(result, 'best_idx', None)}")
    print(f"num_candidates: {getattr(result, 'num_candidates', None)}")
    best = getattr(result, "best_candidate", None)
    if best is not None:
        best_instr = best.get("instructions", "")
        print(f"best instructions ({len(best_instr)} chars):")
        print(f"  {best_instr!r}")
    print()
    print("Now open the Weave trace URL printed above and verify:")
    print("  1. Traces tab — click a `gepa.propose` span. You should see:")
    print("       - `reflective_dataset` in the inputs (exactly what the")
    print("         reflection LM saw — Inputs/Outputs/Feedback per example).")
    print("       - a child LM call (`_stub_reflection_lm` or `litellm.*`)")
    print("         with the actual chat completion under the propose span.")
    print("  2. Click `gepa.reflective_dataset` directly to browse the")
    print("     feedback records as a point span.")
    print("  3. Evaluations tab — one `gepa_valset_iter{N}_cand{M}` eval per")
    print("     valset evaluation, with per-example scores.")
    print("  4. Objects tab — `gepa_candidate` with one version per accepted")
    print("     candidate (seed + each improvement).")


if __name__ == "__main__":
    main()
