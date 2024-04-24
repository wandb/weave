import importlib

import weave
from weave.trace.patcher import SymbolPatcher, MultiPatcher


mistral_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.client"),
            "MistralClient.chat",
            weave.op(),
        )
    ]
)
