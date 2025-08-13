from __future__ import annotations

import functools
import threading
from collections.abc import Sequence
from typing import Any

from weave.evaluation.eval_imperative import EvaluationLogger
from weave.integrations.dspy.dspy_utils import get_symbol_patcher
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, Patcher
from weave.trace.autopatch import IntegrationSettings
from weave.trace.serialization.serialize import dictify

_dspy_patcher: MultiPatcher | None = None
_evaluate_patched = False
_patch_lock = threading.Lock()


class DSPyPatcher(MultiPatcher):
    def __init__(self, patchers: Sequence[Patcher]) -> None:
        super().__init__(patchers)
        try:
            import dspy

            from weave.integrations.dspy.dspy_callback import WeaveCallback

            is_callback_present = False
            for callback in dspy.settings.callbacks:
                if isinstance(callback, WeaveCallback):
                    is_callback_present = True
                    break

            if not is_callback_present:
                dspy.settings.callbacks.append(WeaveCallback())

            # Monkey-patch dspy.Evaluate.__call__ for clean evaluation logging
            self._patch_evaluate()

        except ImportError:
            pass

    def _patch_evaluate(self: DSPyPatcher) -> None:
        """Monkey-patch dspy.Evaluate.__call__ to replay results into Weave EvaluationLogger."""
        from dspy.utils.callback import with_callbacks

        global _evaluate_patched

        with _patch_lock:
            if _evaluate_patched:
                return

            try:
                from dspy.evaluate import Evaluate

                # Keep reference to original method
                orig_call = Evaluate.__call__

                @functools.wraps(orig_call)
                def _wrapped_call(
                    self: Evaluate, program: Any, *args: Any, **kwargs: Any
                ) -> Any:
                    """
                    Patched Evaluate.__call__ that logs a full Weave Evaluation **and**
                    ensures every program call is nested inside that evaluation so the
                    full trace is visible in the UI.
                    """
                    import types

                    from weave.trace.context import call_context

                    # Capture the caller's requested return shape
                    want_outputs = kwargs.get("return_outputs", self.return_outputs)
                    want_scores = kwargs.get(
                        "return_all_scores", self.return_all_scores
                    )

                    # Create a Weave EvaluationLogger
                    model_name = getattr(program, "__class__", type(program)).__name__
                    devset = (
                        kwargs.get("devset", getattr(self, "devset", None))
                        or self.devset
                    )
                    metric = kwargs.get("metric", None) or self.metric
                    num_threads = kwargs.get("num_threads", None) or self.num_threads
                    display_progress = (
                        kwargs.get("display_progress", None) or self.display_progress
                    )
                    failure_score = getattr(self, "failure_score", 0.0)
                    max_errors = getattr(self, "max_errors", 5)
                    provide_traceback = getattr(self, "provide_traceback", None)

                    raw_dump_state = getattr(program, "dump_state", lambda: None)()
                    safe_dump_state = dictify(raw_dump_state)

                    module_meta: dict[str, Any] = {
                        "name": model_name,
                        "dump_state": safe_dump_state,
                        "_compiled": getattr(program, "_compiled", None),
                        "callbacks": [
                            repr(cb) for cb in getattr(program, "callbacks", [])
                        ],
                        "repr": repr(program),
                        "metric": repr(metric),
                        "num_threads": num_threads,
                        "display_progress": display_progress,
                        "failure_score": failure_score,
                        "return_outputs": want_outputs,
                        "return_all_scores": want_scores,
                        "max_errors": max_errors,
                        "provide_traceback": provide_traceback,
                    }

                    ev = EvaluationLogger(
                        name=f"dspy_{model_name}",
                        model=module_meta,
                        dataset=[dict(ex.inputs()) for ex in devset],
                    )

                    # Prepare parallel executor so that every worker thread
                    # inherits the evaluation's call-stack. We'll re-implement
                    # DSPy's evaluation loop here so that traces are captured
                    # where they belong.
                    from dspy.utils.parallelizer import ParallelExecutor

                    executor = ParallelExecutor(
                        num_threads=num_threads,
                        disable_progress_bar=not display_progress,
                        max_errors=max_errors,
                        provide_traceback=provide_traceback,
                        compare_results=True,
                    )

                    # Will accumulate (example, prediction, score)
                    result_triples: list[tuple[Any, Any, float]] = [None] * len(devset)  # type: ignore

                    def _worker(
                        index_and_example: tuple[int, Any],
                    ) -> tuple[Any, float]:
                        idx, example = index_and_example
                        with call_context.set_call_stack([ev._evaluate_call]):  # type: ignore
                            prediction = program(**example.inputs())
                            score = metric(example, prediction) if metric else 0.0

                            # Increment assert and suggest failures to program's attributes
                            if hasattr(program, "_assert_failures"):
                                import dspy as _dspy_mod

                                program._assert_failures += _dspy_mod.settings.get(
                                    "assert_failures"
                                )
                            if hasattr(program, "_suggest_failures"):
                                import dspy as _dspy_mod

                                program._suggest_failures += _dspy_mod.settings.get(
                                    "suggest_failures"
                                )

                            import dspy as _dspy_mod

                            if isinstance(example, _dspy_mod.Example):
                                serialized_inputs = example.items()
                            else:
                                serialized_inputs = example.inputs()

                            if isinstance(prediction, _dspy_mod.Prediction):
                                serialized_pred = prediction.items()
                            elif isinstance(prediction, _dspy_mod.Completions):
                                serialized_pred = prediction.items()
                            else:
                                serialized_pred = prediction

                            pl = ev.log_prediction(
                                inputs=serialized_inputs, output=serialized_pred
                            )
                            pl.log_score(scorer=scorer_name, score=score)
                            pl.finish()
                            result_triples[idx] = (example, prediction, score)
                            # Return a 2-tuple to match DSPy's expected shape (prediction, score)
                            return (prediction, score)

                    # Determine scorer name once, outside threads
                    if metric is None:
                        scorer_name = "score"
                    elif isinstance(metric, types.FunctionType):
                        scorer_name = metric.__name__
                    else:
                        scorer_name = metric.__class__.__name__

                    if scorer_name == "method":
                        scorer_name = "score"

                    # Kick off parallel execution
                    indices_examples = list(enumerate(devset))
                    executor.execute(_worker, indices_examples)

                    # Fill in any failed results with default failure_score
                    for i, triple in enumerate(result_triples):
                        if triple is None:
                            ex = devset[i]
                            result_triples[i] = (ex, None, failure_score)  # type: ignore

                    triples = result_triples  # rename for downstream logic
                    individual = [s for *_, s in triples]
                    overall = round(100 * sum(individual) / len(individual), 2)

                    ev.log_summary({"mean_score": overall / 100.0})

                    # ── 3️⃣  Return exactly what the caller expected ─────────────────────
                    if want_outputs and want_scores:
                        return overall, triples, individual
                    if want_outputs:
                        return overall, triples
                    if want_scores:
                        return overall, individual
                    return overall

                # Apply the patch
                Evaluate.__call__ = with_callbacks(_wrapped_call)
                _evaluate_patched = True

            except Exception as e:
                # Don't let patching errors break DSPy integration
                print(f"Warning: Failed to patch DSPy Evaluate: {e}")


def get_dspy_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _dspy_patcher
    if _dspy_patcher is not None:
        return _dspy_patcher

    base = settings.op_settings

    _dspy_patcher = DSPyPatcher(
        [
            # Adapters
            get_symbol_patcher("dspy", "ChatAdapter.__call__", base),
            get_symbol_patcher("dspy", "JSONAdapter.__call__", base),
            # Models
            get_symbol_patcher("dspy", "Embedder.__call__", base),
            # Tools
            get_symbol_patcher("dspy", "ColBERTv2.__call__", base),
            get_symbol_patcher("dspy", "PythonInterpreter.__call__", base),
            get_symbol_patcher("dspy.retrievers", "Embeddings.__call__", base),
            # Optimizers
            get_symbol_patcher("dspy", "BetterTogether.compile", base),
            get_symbol_patcher("dspy", "BootstrapFewShot.compile", base),
            get_symbol_patcher(
                "dspy", "BootstrapFewShotWithRandomSearch.compile", base
            ),
            get_symbol_patcher("dspy", "BootstrapFinetune.compile", base),
            get_symbol_patcher("dspy", "COPRO.compile", base),
            get_symbol_patcher("dspy", "Ensemble.compile", base),
            # TODO: add dspy.InferRules.compile
            get_symbol_patcher("dspy", "KNN.__call__", base),
            get_symbol_patcher("dspy", "KNNFewShot.compile", base),
            get_symbol_patcher("dspy", "LabeledFewShot.compile", base),
            get_symbol_patcher("dspy", "MIPROv2.compile", base),
            # TODO: add dspy.InferRules.compile
            # LM
            get_symbol_patcher("dspy", "LM.forward", base),
        ]
    )

    return _dspy_patcher
