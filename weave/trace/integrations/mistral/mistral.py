import importlib

import weave
from weave.trace.patcher import SymbolPatcher

mistral_patches = {
    "MistralClient.chat": SymbolPatcher(
        lambda: importlib.import_module("mistralai.client"),
        "MistralClient.chat",
        weave.op(),
    )
}


def autopatch_mistral() -> None:
    for patch in mistral_patches.values():
        patch.attempt_patch()


def undo_patch_mistral() -> None:
    for patch in mistral_patches.values():
        patch.undo_patch()
