from __future__ import annotations

import importlib

from weave.integrations.dspy.dspy_utils import dspy_wrapper
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings

_dspy_patcher: MultiPatcher | None = None


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

    _dspy_patcher = MultiPatcher(
        [
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Embedder.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.Embedder"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "ColBERTv2.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.ColBERTv2"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "BootstrapFinetune.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.BootstrapFinetune.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "MIPROv2.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.MIPROv2.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "LabeledFewShot.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.LabeledFewShot.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "KNNFewShot.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.KNNFewShot.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "KNN.__call__",
                dspy_wrapper(base.model_copy(update={"name": base.name or "dspy.KNN"})),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Ensemble.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.Ensemble.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "COPRO.compile",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.COPRO.compile"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "BootstrapFewShotWithRandomSearch.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name
                            or "dspy.BootstrapFewShotWithRandomSearch.compile"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "BootstrapFewShot.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.BootstrapFewShot.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "BetterTogether.compile",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.BetterTogether.compile"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "answer_passage_match",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name or "dspy.evaluate.answer_passage_match"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "answer_exact_match",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.evaluate.answer_exact_match"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "SemanticF1.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.evaluate.SemanticF1"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "SemanticF1.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.evaluate.SemanticF1.forward"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "CompleteAndGrounded.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name or "dspy.evaluate.CompleteAndGrounded"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.evaluate"),
                "CompleteAndGrounded.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name
                            or "dspy.evaluate.CompleteAndGrounded.forward"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "Evaluate.__call__",
                dspy_wrapper(
                    base.model_copy(update={"name": base.name or "dspy.Evaluate"})
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.retrievers"),
                "Embeddings.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.retrievers.Embeddings"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy.retrievers"),
                "Embeddings.forward",
                dspy_wrapper(
                    base.model_copy(
                        update={
                            "name": base.name or "dspy.retrievers.Embeddings.forward"
                        }
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "PythonInterpreter.__call__",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.PythonInterpreter"}
                    )
                ),
            ),
            SymbolPatcher(
                lambda: importlib.import_module("dspy"),
                "PythonInterpreter.execute",
                dspy_wrapper(
                    base.model_copy(
                        update={"name": base.name or "dspy.PythonInterpreter.execute"}
                    )
                ),
            ),
        ]
    )

    return _dspy_patcher
