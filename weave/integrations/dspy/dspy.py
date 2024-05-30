import importlib

import weave
from weave.trace.patcher import SymbolPatcher, MultiPatcher


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
]
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
