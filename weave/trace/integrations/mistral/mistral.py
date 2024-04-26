import importlib

import weave
from weave.trace.op_extensions.accumulator import add_accumulator
from weave.trace.patcher import SymbolPatcher, MultiPatcher


def mistral_accumulator(acc, value):
    if acc is None:
        acc = []
    acc.append(value)
    return acc


def mistral_stream_wrapper(fn):
    op = weave.op()(fn)
    acc_op = add_accumulator(op, mistral_accumulator)
    return acc_op


mistral_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.client"),
            "MistralClient.chat",
            weave.op(),
        ),
        SymbolPatcher(
            lambda: importlib.import_module("mistralai.client"),
            "MistralClient.chat_stream",
            mistral_stream_wrapper,
        ),
    ]
)
