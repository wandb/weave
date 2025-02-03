import json
from typing import Any

from weave.trace_server.interface.builtin_object_classes.actions import (
    ContainsWordsActionConfig,
)
from weave.trace_server.trace_server_interface import (
    CallSchema,
    TraceServerInterface,
)


def do_contains_words_action(
    project_id: str,
    config: ContainsWordsActionConfig,
    call: CallSchema,
    trace_server: TraceServerInterface,
) -> Any:
    target_words = config.target_words
    text = json.dumps(call.output)
    for word in target_words:
        if word in text:
            return True
    return False
