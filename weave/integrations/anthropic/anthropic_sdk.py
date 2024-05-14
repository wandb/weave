import importlib

import typing

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import SymbolPatcher, MultiPatcher

if typing.TYPE_CHECKING:
    from anthropic.types import Message

anthropic_patcher = MultiPatcher(
    [
        # Patch the sync messages.create method
        SymbolPatcher(
            lambda: importlib.import_module("anthropic.resources.messages"),
            "Messages.create",
            weave.op(),
        ),
    ]
)

