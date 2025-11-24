from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel

from weave.evaluation.eval_imperative import EvaluationLogger
from weave.integrations.dspy.dspy_utils import dictify, get_symbol_patcher
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, Patcher
from weave.trace.autopatch import IntegrationSettings
from weave.trace.context import call_context

logger = logging.getLogger(__name__)

_dspy_patcher: MultiPatcher | None = None
_evaluate_patched = False


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
        global _evaluate_patched

        if _evaluate_patched:
            return
        try:
            import dspy
            from dspy.evaluate import Evaluate
            from dspy.evaluate.evaluate import EvaluationResult
            from dspy.utils.callback import with_callbacks
            from dspy.utils.parallelizer import ParallelExecutor

            orig_call = Evaluate.__call__

            @functools.wraps(orig_call)
            def _wrapped_call(
                self: Evaluate,
                program: dspy.Module,
                metric: Callable | None = None,
                devset: list[dspy.Example] | None = None,
                num_threads: int | None = None,
                display_progress: bool | None = None,
                display_table: bool | int | None = None,
                callback_metadata: dict[str, Any] | None = None,
            ) -> EvaluationResult:
                import types

                # Create model metadata for EvaluationLogger
                metric = metric if metric is not None else self.metric
                devset = devset if devset is not None else self.devset
                num_threads = (
                    num_threads if num_threads is not None else self.num_threads
                )
                display_progress = (
                    display_progress
                    if display_progress is not None
                    else self.display_progress
                )
                display_table = (
                    display_table if display_table is not None else self.display_table
                )
                # get the name of the program we are evaluating
                model_name = getattr(program, "__class__", type(program)).__name__

                if callback_metadata:
                    logger.debug(
                        f"Evaluate is called with callback metadata: {callback_metadata}"
                    )

                max_errors = getattr(self, "max_errors", dspy.settings.max_errors)
                provide_traceback = getattr(self, "provide_traceback", None)
                failure_score = getattr(self, "failure_score", 0.0)

                # Serialize the program's state
                raw_dump_state = getattr(program, "dump_state", lambda: None)
                if callable(raw_dump_state):
                    raw_dump_state = dictify(raw_dump_state())

                # prepare metadata for the evaluation logger
                module_meta: dict[str, Any] = {
                    "name": model_name,
                    "dump_state": raw_dump_state,
                    "_compiled": getattr(program, "_compiled", None),
                    "callbacks": [repr(cb) for cb in getattr(program, "callbacks", [])],
                    "program_repr": repr(program),
                    "metric_repr": repr(metric),
                    "num_threads": num_threads,
                    "display_progress": display_progress,
                    "failure_score": failure_score,
                    "max_errors": max_errors,
                    "provide_traceback": provide_traceback,
                }

                # prepare dataset for the evaluation logger
                dataset = (
                    [dictify(ex.toDict()) for ex in devset]
                    if devset is not None
                    else []
                )

                ev = EvaluationLogger(
                    name=f"dspy_eval_{model_name}",
                    model=module_meta,
                    dataset=dataset,
                )

                executor = ParallelExecutor(
                    num_threads=num_threads,
                    disable_progress_bar=not display_progress,
                    max_errors=max_errors,
                    provide_traceback=provide_traceback,
                    compare_results=True,
                )

                def process_item(
                    example: dspy.Example,
                ) -> tuple[dspy.Prediction | dspy.Completions, float]:
                    with call_context.set_call_stack([ev._evaluate_call]):  # type: ignore
                        # DSPy expects the inputs to be wrapped in an Example object
                        with ev.log_prediction(
                            inputs=dictify(example.toDict())
                        ) as pred:
                            prediction = program(**example.inputs())
                            score = metric(example, prediction)

                            # Increment assert and suggest failures to program's attributes
                            if hasattr(program, "_assert_failures"):
                                program._assert_failures += dspy.settings.get(
                                    "assert_failures"
                                )
                            if hasattr(program, "_suggest_failures"):
                                program._suggest_failures += dspy.settings.get(
                                    "suggest_failures"
                                )

                            serialized_pred = None
                            if isinstance(prediction, dspy.Prediction):
                                # Prediction is inherited from Example
                                serialized_pred = dictify(prediction.toDict())
                            if isinstance(prediction, dspy.Completions):
                                # Completions exposes the `items` method
                                serialized_pred = dictify(prediction.items())
                            if isinstance(prediction, BaseModel):
                                serialized_pred = dictify(prediction.model_dump())

                            pred.output = serialized_pred
                            pred.log_score(scorer=scorer_name, score=score)

                        return prediction, score

                # Determine scorer name once, outside threads
                scorer_name = (
                    metric.__name__
                    if isinstance(metric, types.FunctionType)
                    else metric.__class__.__name__
                )
                if scorer_name == "method":
                    scorer_name = "score"

                results = executor.execute(process_item, devset)
                assert len(devset) == len(results)

                results = [
                    ((dspy.Prediction(), failure_score) if r is None else r)
                    for r in results
                ]
                results = [
                    (example, prediction, score)
                    for example, (prediction, score) in zip(
                        devset,
                        results,
                        strict=False,  # type: ignore[arg-type, call-overload]
                    )
                ]
                ncorrect, ntotal = sum(score for *_, score in results), len(devset)

                logger.info(
                    f"Average Metric: {ncorrect} / {ntotal} ({round(100 * ncorrect / ntotal, 1)}%)"
                )

                ev.log_summary({"Average Metric": ncorrect / ntotal})

                if display_table:
                    logger.warning(
                        "We don't support `display_table` via this patched `Evaluate.__call__` method. Set `display_table=False` to disable this warning."
                    )

                return EvaluationResult(
                    score=round(100 * ncorrect / ntotal, 2),
                    results=results,
                )

            # Apply the patch
            Evaluate.__call__ = with_callbacks(_wrapped_call)
            _evaluate_patched = True

        except Exception as e:
            # Don't let patching errors break DSPy integration
            logger.warning(f"Failed to patch DSPy Evaluate: {e}")


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
            # TODO (ayulockin): add dspy.InferRules.compile
            get_symbol_patcher("dspy", "KNN.__call__", base),
            get_symbol_patcher("dspy", "KNNFewShot.compile", base),
            get_symbol_patcher("dspy", "LabeledFewShot.compile", base),
            get_symbol_patcher("dspy", "MIPROv2.compile", base),
            # LM
            get_symbol_patcher("dspy", "LM.forward", base),
        ]
    )

    return _dspy_patcher
