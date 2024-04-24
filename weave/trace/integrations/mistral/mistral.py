import importlib

import weave
from weave.trace.patcher import SymbolPatcher, MultiPatcher

mistral_patches = {
    "MistralClient.chat": SymbolPatcher(
        lambda: importlib.import_module("mistralai.client"),
        "MistralClient.chat",
        weave.op(),
    )
}

mistral_patcher = MultiPatcher(mistral_patches.values())
