from __future__ import annotations

import functools
import types
import threading
from collections.abc import Sequence

import weave
from weave.flow.eval_imperative import EvaluationLogger
from weave.integrations.dspy.dspy_utils import get_symbol_patcher
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, Patcher
from weave.trace.autopatch import IntegrationSettings

_dspy_patcher: MultiPatcher | None = None
_evaluate_patched = False
_patch_lock = threading.Lock()


class DSPyPatcher(MultiPatcher):
    def __init__(self, patchers: Sequence[Patcher]) -> None:
        super().__init__(patchers)
        try:
            import dspy

            from weave.integrations.dspy.dspy_callback import WeaveCallback

            # Register callback for URL suppression and basic tracing
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
    
    def _patch_evaluate(self):
        """Monkey-patch dspy.Evaluate.__call__ to replay results into Weave EvaluationLogger."""
        global _evaluate_patched
        
        with _patch_lock:
            if _evaluate_patched:
                return
                
            try:
                import dspy
                from dspy.evaluate import Evaluate
                
                # Keep reference to original method
                _orig_call = Evaluate.__call__
                
                @functools.wraps(_orig_call)
                def _wrapped_call(self, program, *args, **kwargs):
                    """
                    Wrapped Evaluate.__call__ compatible with DSPy ≤ 0.4.x.

                    Captures full result triples for Weave by *temporarily* forcing
                    return_outputs & return_all_scores, then re-formats to the user's
                    originally requested shape.
                    """
                    # 0️⃣ Remember what the caller really wanted
                    want_outputs = kwargs.get("return_outputs", self.return_outputs)
                    want_scores = kwargs.get("return_all_scores", self.return_all_scores)

                    # 1️⃣ Guarantee we get full data from DSPy
                    kwargs_for_call = dict(kwargs)
                    kwargs_for_call["return_outputs"] = True
                    kwargs_for_call["return_all_scores"] = True

                    overall, triples, individual = _orig_call(
                        self, program, *args, **kwargs_for_call
                    )

                    # 2️⃣ Weave logging
                    try:
                        model_name = getattr(program, "__class__", type(program)).__name__
                        
                        ev = EvaluationLogger(
                            name=f"dspy_{model_name}",
                            model=model_name,
                            dataset=[dict(ex.inputs()) for ex, *_ in triples],
                        )
                        
                        scorer_name = (
                            self.metric.__name__ if callable(self.metric)
                            else self.metric.__class__.__name__
                        )
                        
                        for example, prediction, score in triples:
                            pl = ev.log_prediction(inputs=example.inputs(), output=prediction)
                            pl.log_score(scorer=scorer_name, score=score)
                            pl.finish()
                            
                        ev.log_summary({"mean_score": overall / 100.0})
                        
                    except Exception as e:
                        # Don't let Weave logging errors break DSPy evaluation
                        print(f"Warning: Failed to log DSPy evaluation to Weave: {e}")

                    # 3️⃣ Restore original return contract
                    if want_outputs and want_scores:
                        return overall, triples, individual
                    if want_outputs:
                        return overall, triples
                    if want_scores:
                        return overall, individual
                    return overall
                
                # Apply the patch
                Evaluate.__call__ = _wrapped_call
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
