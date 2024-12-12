from __future__ import annotations

import importlib
from typing import Callable

import weave
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.patcher import MultiPatcher, NoOpPatcher, SymbolPatcher

_dspy_patcher: MultiPatcher | None = None


def dspy_wrapper(settings: OpSettings) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op_kwargs = settings.model_dump()
        op = weave.op(fn, **op_kwargs)
        return op

    return wrapper


def dspy_get_patched_lm_functions(
    base_symbol: str, lm_class_name: str, settings: OpSettings
) -> list[SymbolPatcher]:
    patchable_functional_attributes = [
        "basic_request",
        "request",
        "__call__",
    ]
    basic_request_settings = settings.model_copy(
        update={"name": settings.name or f"{base_symbol}.{lm_class_name}.basic_request"}
    )
    request_settings = settings.model_copy(
        update={"name": settings.name or f"{base_symbol}.{lm_class_name}.request"}
    )
    call_settings = settings.model_copy(
        update={"name": settings.name or f"{base_symbol}.{lm_class_name}"}
    )
    return [
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module(base_symbol),
            attribute_name=f"{lm_class_name}.basic_request",
            make_new_value=dspy_wrapper(basic_request_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module(base_symbol),
            attribute_name=f"{lm_class_name}.request",
            make_new_value=dspy_wrapper(request_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module(base_symbol),
            attribute_name=f"{lm_class_name}.__call__",
            make_new_value=dspy_wrapper(call_settings),
        ),
    ]


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

    predict_call_settings = base.model_copy(
        update={"name": base.name or "dspy.Predict"}
    )
    predict_forward_settings = base.model_copy(
        update={"name": base.name or "dspy.Predict.forward"}
    )
    typed_predictor_call_settings = base.model_copy(
        update={"name": base.name or "dspy.TypedPredictor"}
    )
    typed_predictor_forward_settings = base.model_copy(
        update={"name": base.name or "dspy.TypedPredictor.forward"}
    )
    module_call_settings = base.model_copy(update={"name": base.name or "dspy.Module"})
    typed_chain_of_thought_call_settings = base.model_copy(
        update={"name": base.name or "dspy.TypedChainOfThought"}
    )
    retrieve_call_settings = base.model_copy(
        update={"name": base.name or "dspy.Retrieve"}
    )
    retrieve_forward_settings = base.model_copy(
        update={"name": base.name or "dspy.Retrieve.forward"}
    )
    evaluate_call_settings = base.model_copy(
        update={"name": base.name or "dspy.evaluate.Evaluate"}
    )
    bootstrap_few_shot_compile_settings = base.model_copy(
        update={"name": base.name or "dspy.teleprompt.BootstrapFewShot.compile"}
    )
    copro_compile_settings = base.model_copy(
        update={"name": base.name or "dspy.teleprompt.COPRO.compile"}
    )
    ensemble_compile_settings = base.model_copy(
        update={"name": base.name or "dspy.teleprompt.Ensemble.compile"}
    )
    bootstrap_finetune_compile_settings = base.model_copy(
        update={"name": base.name or "dspy.teleprompt.BootstrapFinetune.compile"}
    )
    knn_few_shot_compile_settings = base.model_copy(
        update={"name": base.name or "dspy.teleprompt.KNNFewShot.compile"}
    )
    mipro_compile_settings = base.model_copy(
        update={"name": base.name or "dspy.teleprompt.MIPRO.compile"}
    )
    bootstrap_few_shot_with_random_search_compile_settings = base.model_copy(
        update={
            "name": base.name
            or "dspy.teleprompt.BootstrapFewShotWithRandomSearch.compile"
        }
    )
    signature_optimizer_compile_settings = base.model_copy(
        update={"name": base.name or "dspy.teleprompt.SignatureOptimizer.compile"}
    )
    bayesian_signature_optimizer_compile_settings = base.model_copy(
        update={
            "name": base.name or "dspy.teleprompt.BayesianSignatureOptimizer.compile"
        }
    )
    signature_opt_typed_optimize_signature_settings = base.model_copy(
        update={
            "name": base.name
            or "dspy.teleprompt.signature_opt_typed.optimize_signature"
        }
    )
    bootstrap_few_shot_with_optuna_compile_settings = base.model_copy(
        update={
            "name": base.name or "dspy.teleprompt.BootstrapFewShotWithOptuna.compile"
        }
    )
    labeled_few_shot_compile_settings = base.model_copy(
        update={"name": base.name or "dspy.teleprompt.LabeledFewShot.compile"}
    )

    patched_functions = [
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Predict.__call__",
            make_new_value=dspy_wrapper(predict_call_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Predict.forward",
            make_new_value=dspy_wrapper(predict_forward_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="TypedPredictor.__call__",
            make_new_value=dspy_wrapper(typed_predictor_call_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="TypedPredictor.forward",
            make_new_value=dspy_wrapper(typed_predictor_forward_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Module.__call__",
            make_new_value=dspy_wrapper(module_call_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="TypedChainOfThought.__call__",
            make_new_value=dspy_wrapper(typed_chain_of_thought_call_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Retrieve.__call__",
            make_new_value=dspy_wrapper(retrieve_call_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Retrieve.forward",
            make_new_value=dspy_wrapper(retrieve_forward_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.evaluate.evaluate"),
            attribute_name="Evaluate.__call__",
            make_new_value=dspy_wrapper(evaluate_call_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="BootstrapFewShot.compile",
            make_new_value=dspy_wrapper(bootstrap_few_shot_compile_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="COPRO.compile",
            make_new_value=dspy_wrapper(copro_compile_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="Ensemble.compile",
            make_new_value=dspy_wrapper(ensemble_compile_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="BootstrapFinetune.compile",
            make_new_value=dspy_wrapper(bootstrap_finetune_compile_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="KNNFewShot.compile",
            make_new_value=dspy_wrapper(knn_few_shot_compile_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="MIPRO.compile",
            make_new_value=dspy_wrapper(mipro_compile_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="BootstrapFewShotWithRandomSearch.compile",
            make_new_value=dspy_wrapper(
                bootstrap_few_shot_with_random_search_compile_settings
            ),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="SignatureOptimizer.compile",
            make_new_value=dspy_wrapper(signature_optimizer_compile_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="BayesianSignatureOptimizer.compile",
            make_new_value=dspy_wrapper(bayesian_signature_optimizer_compile_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module(
                "dspy.teleprompt.signature_opt_typed"
            ),
            attribute_name="optimize_signature",
            make_new_value=dspy_wrapper(
                signature_opt_typed_optimize_signature_settings
            ),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="BootstrapFewShotWithOptuna.compile",
            make_new_value=dspy_wrapper(
                bootstrap_few_shot_with_optuna_compile_settings
            ),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
            attribute_name="LabeledFewShot.compile",
            make_new_value=dspy_wrapper(labeled_few_shot_compile_settings),
        ),
    ]

    # Patch LM classes
    patched_functions += dspy_get_patched_lm_functions(
        base_symbol="dspy", lm_class_name="AzureOpenAI", settings=base
    )
    patched_functions += dspy_get_patched_lm_functions(
        base_symbol="dspy", lm_class_name="OpenAI", settings=base
    )
    patched_functions += dspy_get_patched_lm_functions(
        base_symbol="dspy", lm_class_name="Cohere", settings=base
    )
    patched_functions += dspy_get_patched_lm_functions(
        base_symbol="dspy", lm_class_name="Clarifai", settings=base
    )
    patched_functions += dspy_get_patched_lm_functions(
        base_symbol="dspy", lm_class_name="Google", settings=base
    )
    patched_functions += dspy_get_patched_lm_functions(
        base_symbol="dspy", lm_class_name="HFClientTGI", settings=base
    )
    patched_functions += dspy_get_patched_lm_functions(
        base_symbol="dspy", lm_class_name="HFClientVLLM", settings=base
    )
    patched_functions += dspy_get_patched_lm_functions(
        base_symbol="dspy", lm_class_name="Anyscale", settings=base
    )
    patched_functions += dspy_get_patched_lm_functions(
        base_symbol="dspy", lm_class_name="Together", settings=base
    )
    patched_functions += dspy_get_patched_lm_functions(
        base_symbol="dspy", lm_class_name="OllamaLocal", settings=base
    )

    databricks_basic_request_settings = base.model_copy(
        update={"name": base.name or "dspy.Databricks.basic_request"}
    )
    databricks_call_settings = base.model_copy(
        update={"name": base.name or "dspy.Databricks"}
    )
    colbertv2_call_settings = base.model_copy(
        update={"name": base.name or "dspy.ColBERTv2"}
    )
    pyserini_call_settings = base.model_copy(
        update={"name": base.name or "dspy.Pyserini"}
    )

    patched_functions += [
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Databricks.basic_request",
            make_new_value=dspy_wrapper(databricks_basic_request_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Databricks.__call__",
            make_new_value=dspy_wrapper(databricks_call_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="ColBERTv2.__call__",
            make_new_value=dspy_wrapper(colbertv2_call_settings),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Pyserini.__call__",
            make_new_value=dspy_wrapper(pyserini_call_settings),
        ),
    ]

    _dspy_patcher = MultiPatcher(patched_functions)

    return _dspy_patcher
