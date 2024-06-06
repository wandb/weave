import importlib

import weave
from weave.trace.patcher import SymbolPatcher, MultiPatcher

from diffusers import DiffusionPipeline


diffusers_patcher = MultiPatcher(
    [
        SymbolPatcher(
            get_base_symbol=lambda: importlib.import_module("diffusers"),
            attribute_name="StableDiffusionPipeline.__call__",
            make_new_value=weave.op(),
        )
    ]
)
