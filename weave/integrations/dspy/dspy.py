import importlib

import weave
from weave.trace.patcher import SymbolPatcher, MultiPatcher


dspy_patcher = MultiPatcher(
    [
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
            attribute_name="OpenAI.__init__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="OpenAI.__call__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="configure",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="ChainOfThought.__init__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="ChainOfThought.__call__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Cohere.__init__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Cohere.__call__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Anyscale.__init__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Anyscale.__call__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Together.__init__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Together.__call__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="HFClientTGI.__init__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="HFClientTGI.__call__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="HFClientVLLM.__init__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="HFClientVLLM.__call__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="HFModel.__init__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="HFModel.__call__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Ollama.__init__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="Ollama.__call__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="ChatModuleClient.__init__",
            make_new_value=weave.op(),
        ),
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("dspy"),
            attribute_name="ChatModuleClient.__call__",
            make_new_value=weave.op(),
        ),
    ]
)
