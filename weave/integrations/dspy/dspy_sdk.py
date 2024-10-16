import importlib
import inspect
from typing import Callable

import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher


def dspy_wrapper(name: str) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        return op

    return wrapper


def check_member_function_exists(
    base_symbol: str, lm_class_name: str, member_function_name: str
) -> bool:
    try:
        module = importlib.import_module(base_symbol)
        XYZ = getattr(module, lm_class_name)
    except ImportError:
        print(f"{base_symbol} cannot be imported")
    except AttributeError:
        print(f"{lm_class_name} cannot be imported from {base_symbol}")
    else:
        # Get all functions (methods) of class XYZ
        methods = inspect.getmembers(XYZ, predicate=inspect.isfunction)
        method_names = [name for name, _ in methods]
        return member_function_name in method_names
    return False


def dspy_get_patched_lm_functions(
    base_symbol: str, lm_class_name: str
) -> list[SymbolPatcher]:
    if hasattr(importlib.import_module(base_symbol), lm_class_name):
        patched_functions = []
        if check_member_function_exists(base_symbol, lm_class_name, "basic_request"):
            patched_functions.append(
                SymbolPatcher(
                    get_base_symbol=lambda: importlib.import_module(base_symbol),
                    attribute_name=f"{lm_class_name}.basic_request",
                    make_new_value=dspy_wrapper(f"dspy.{lm_class_name}.basic_request"),
                )
            )
        if check_member_function_exists(base_symbol, lm_class_name, "request"):
            patched_functions.append(
                SymbolPatcher(
                    get_base_symbol=lambda: importlib.import_module(base_symbol),
                    attribute_name=f"{lm_class_name}.request",
                    make_new_value=dspy_wrapper(f"dspy.{lm_class_name}.request"),
                )
            )
        patched_functions.append(
            SymbolPatcher(
                get_base_symbol=lambda: importlib.import_module(base_symbol),
                attribute_name=f"{lm_class_name}.__call__",
                make_new_value=dspy_wrapper(f"dspy.{lm_class_name}"),
            )
        )
        return patched_functions
    return []


patched_functions = [
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Predict.__call__",
        make_new_value=dspy_wrapper("dspy.Predict"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Predict.forward",
        make_new_value=dspy_wrapper("dspy.Predict.forward"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="TypedPredictor.__call__",
        make_new_value=dspy_wrapper("dspy.TypedPredictor"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="TypedPredictor.forward",
        make_new_value=dspy_wrapper("dspy.TypedPredictor.forward"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Module.__call__",
        make_new_value=dspy_wrapper("dspy.Module"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="TypedChainOfThought.__call__",
        make_new_value=dspy_wrapper("dspy.TypedChainOfThought"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Retrieve.__call__",
        make_new_value=dspy_wrapper("dspy.Retrieve"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Retrieve.forward",
        make_new_value=dspy_wrapper("dspy.Retrieve.forward"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.evaluate.evaluate"),
        attribute_name="Evaluate.__call__",
        make_new_value=dspy_wrapper("dspy.evaluate.Evaluate"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="BootstrapFewShot.compile",
        make_new_value=dspy_wrapper("dspy.teleprompt.BootstrapFewShot.compile"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="COPRO.compile",
        make_new_value=dspy_wrapper("dspy.teleprompt.COPRO.compile"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="Ensemble.compile",
        make_new_value=dspy_wrapper("dspy.teleprompt.Ensemble.compile"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="BootstrapFinetune.compile",
        make_new_value=dspy_wrapper("dspy.teleprompt.BootstrapFinetune.compile"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="KNNFewShot.compile",
        make_new_value=dspy_wrapper("dspy.teleprompt.KNNFewShot.compile"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="MIPRO.compile",
        make_new_value=dspy_wrapper("dspy.teleprompt.MIPRO.compile"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="BootstrapFewShotWithRandomSearch.compile",
        make_new_value=dspy_wrapper(
            "dspy.teleprompt.BootstrapFewShotWithRandomSearch.compile"
        ),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="SignatureOptimizer.compile",
        make_new_value=dspy_wrapper("dspy.teleprompt.SignatureOptimizer.compile"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="BayesianSignatureOptimizer.compile",
        make_new_value=dspy_wrapper(
            "dspy.teleprompt.BayesianSignatureOptimizer.compile"
        ),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module(
            "dspy.teleprompt.signature_opt_typed"
        ),
        attribute_name="optimize_signature",
        make_new_value=dspy_wrapper(
            "dspy.teleprompt.signature_opt_typed.optimize_signature"
        ),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="BootstrapFewShotWithOptuna.compile",
        make_new_value=dspy_wrapper(
            "dspy.teleprompt.BootstrapFewShotWithOptuna.compile"
        ),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy.teleprompt"),
        attribute_name="LabeledFewShot.compile",
        make_new_value=dspy_wrapper("dspy.teleprompt.LabeledFewShot.compile"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="LM.inspect_history",
        make_new_value=dspy_wrapper("dspy.LM.inspect_history"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="LM.__call__",
        make_new_value=dspy_wrapper("dspy.LM"),
    ),
]

# Patch LM classes (for backwards compatibility with old DSPy versions)
patched_functions += dspy_get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="AzureOpenAI"
)
patched_functions += dspy_get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="OpenAI"
)
patched_functions += dspy_get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Cohere"
)
patched_functions += dspy_get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Clarifai"
)
patched_functions += dspy_get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Google"
)
patched_functions += dspy_get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="HFClientTGI"
)
patched_functions += dspy_get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="HFClientVLLM"
)
patched_functions += dspy_get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Anyscale"
)
patched_functions += dspy_get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Together"
)
patched_functions += dspy_get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="OllamaLocal"
)
patched_functions += [
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Databricks.basic_request",
        make_new_value=dspy_wrapper("dspy.Databricks.basic_request"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Databricks.__call__",
        make_new_value=dspy_wrapper("dspy.Databricks"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="ColBERTv2.__call__",
        make_new_value=dspy_wrapper("dspy.ColBERTv2"),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Pyserini.__call__",
        make_new_value=dspy_wrapper("dspy.Pyserini"),
    ),
]

dspy_patcher = MultiPatcher(patched_functions)
