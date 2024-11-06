from typing import Any

from weave.trace_server.interface.base_object_classes.actions import (
    ContainsWordsActionSpec,
)
from weave.trace_server.trace_server_interface import (
    CallSchema,
    TraceServerInterface,
)


def do_contains_words_action(
    config: ContainsWordsActionSpec,
    call: CallSchema,
    trace_server: TraceServerInterface,
) -> Any:
    pass
