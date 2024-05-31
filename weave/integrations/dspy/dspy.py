import importlib
import functools
from typing import Any, Callable, List, TypeVar
from typing_extensions import ParamSpec

import weave
from weave import context_state
from weave.trace.op import Op
from weave.trace.patcher import SymbolPatcher, MultiPatcher


P = ParamSpec("P")
R = TypeVar("R")


def teleprompter_compile_op(
    *args: Any, **kwargs: Any
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    if context_state.get_loading_built_ins():
        from weave.decorator_op import op

        return op(*args, **kwargs)

    def wrap(f: Callable[P, R]) -> Callable[P, R]:
        op = Op(f)
        functools.update_wrapper(op, f)
        return op  # type: ignore

    if "metric" in kwargs:
        kwargs["metric"] = weave.op()(kwargs["metric"])

    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        return wrap(args[0])

    return wrap


def get_patched_lm_functions(
    base_symbol: str, lm_class_name: str
) -> list[SymbolPatcher]:
    patchable_functional_attributes = [
        "__init__",
        "basic_request",
        "request",
        "__call__",
    ]
    return [
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module(base_symbol),
            attribute_name=f"{lm_class_name}.{functional_attribute}",
            make_new_value=weave.op(),
        )
        for functional_attribute in patchable_functional_attributes
    ]


def get_patched_teleprompters(
    teleprompter_class_name: str, base_symbol: str = "dspy.teleprompt"
) -> List[SymbolPatcher]:
    patchable_functional_attributes = ["__init__", "compile"]
    return [
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module(base_symbol),
            attribute_name=f"{teleprompter_class_name}.{functional_attribute}",
            make_new_value=weave.op(),
        )
        for functional_attribute in patchable_functional_attributes
    ]


patched_functions = [
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Predict.__init__",
        make_new_value=weave.op(),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Predict.__call__",
        make_new_value=weave.op(),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Predict.forward",
        make_new_value=weave.op(),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Module.__init__",
        make_new_value=weave.op(),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Module.__call__",
        make_new_value=weave.op(),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Retrieve.__init__",
        make_new_value=weave.op(),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Retrieve.__call__",
        make_new_value=weave.op(),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("dspy"),
        attribute_name="Retrieve.forward",
        make_new_value=weave.op(),
    ),
]

# Patch Teleprompter classes
patched_functions += get_patched_teleprompters(
    teleprompter_class_name="BootstrapFewShot"
)

# Patch LM classes
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="AzureOpenAI"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="OpenAI"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Databricks"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Cohere"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="ColBERTv2"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Pyserini"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Clarifai"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Google"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="HFClientTGI"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="HFClientVLLM"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Anyscale"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Together"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="OllamaLocal"
)
patched_functions += get_patched_lm_functions(
    base_symbol="dspy", lm_class_name="Bedrock"
)

dspy_patcher = MultiPatcher(patched_functions)
