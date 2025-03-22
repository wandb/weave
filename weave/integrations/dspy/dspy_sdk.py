from __future__ import annotations

from collections.abc import Sequence

from weave.integrations.dspy.dspy_utils import get_symbol_patcher
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, Patcher
from weave.trace.autopatch import IntegrationSettings

_dspy_patcher: MultiPatcher | None = None


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
        except ImportError:
            pass


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
            get_symbol_patcher("dspy", "LM.__call__", base),
            get_symbol_patcher("dspy", "Embedder.__call__", base),
            get_symbol_patcher("dspy", "ColBERTv2.__call__", base),
            get_symbol_patcher("dspy", "BootstrapFinetune.compile", base),
            get_symbol_patcher("dspy", "MIPROv2.compile", base),
            get_symbol_patcher("dspy", "LabeledFewShot.compile", base),
            get_symbol_patcher("dspy", "KNNFewShot.compile", base),
            get_symbol_patcher("dspy", "KNN.__call__", base),
            get_symbol_patcher("dspy", "Ensemble.compile", base),
            get_symbol_patcher("dspy", "COPRO.compile", base),
            get_symbol_patcher(
                "dspy", "BootstrapFewShotWithRandomSearch.compile", base
            ),
            get_symbol_patcher("dspy", "BootstrapFewShot.compile", base),
            get_symbol_patcher("dspy", "BetterTogether.compile", base),
            get_symbol_patcher("dspy", "Evaluate.__call__", base),
            get_symbol_patcher("dspy.retrievers", "Embeddings.__call__", base),
            get_symbol_patcher("dspy.retrievers", "Embeddings.forward", base),
            get_symbol_patcher("dspy", "PythonInterpreter.__call__", base),
            get_symbol_patcher("dspy", "PythonInterpreter.execute", base),
            get_symbol_patcher("dspy", "ChatAdapter.__call__", base),
            get_symbol_patcher("dspy", "JSONAdapter.__call__", base),
        ]
    )

    return _dspy_patcher
