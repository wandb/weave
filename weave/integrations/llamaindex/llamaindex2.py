from typing import Dict, List, Any

from weave.integrations.patcher import Patcher
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.weave_client import Call

import weave

import_failed = False

try:
    from llama_index.core.instrumentation.events.base import BaseEvent
    from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler

    from llama_index.core.instrumentation.events.agent import (
        AgentChatWithStepStartEvent,
        AgentChatWithStepEndEvent,
        AgentRunStepStartEvent,
        AgentRunStepEndEvent,
        AgentToolCallEvent,
    )
    from llama_index.core.instrumentation.events.chat_engine import (
        StreamChatErrorEvent,
        StreamChatDeltaReceivedEvent,
    )
    from llama_index.core.instrumentation.events.embedding import (
        EmbeddingStartEvent,
        EmbeddingEndEvent,
    )
    from llama_index.core.instrumentation.events.llm import (
        LLMPredictEndEvent,
        LLMPredictStartEvent,
        LLMStructuredPredictEndEvent,
        LLMStructuredPredictStartEvent,
        LLMCompletionEndEvent,
        LLMCompletionStartEvent,
        LLMChatEndEvent,
        LLMChatStartEvent,
        LLMChatInProgressEvent,
    )
    from llama_index.core.instrumentation.events.query import (
        QueryStartEvent,
        QueryEndEvent,
    )
    from llama_index.core.instrumentation.events.rerank import (
        ReRankStartEvent,
        ReRankEndEvent,
    )
    from llama_index.core.instrumentation.events.retrieval import (
        RetrievalStartEvent,
        RetrievalEndEvent,
    )
    from llama_index.core.instrumentation.events.span import (
        SpanDropEvent,
    )
    from llama_index.core.instrumentation.events.synthesis import (
        SynthesizeStartEvent,
        SynthesizeEndEvent,
        GetResponseEndEvent,
        GetResponseStartEvent,
    )
except ImportError:
    # This occurs if llama_index is not installed.
    import_failed = True
except Exception:
    # This occurs if llama_index is installed but there is an error in the import or some other error occured in the interaction between packages.
    import_failed = True
    print(
        "Failed to autopatch llama_index. If you are tracing Llama calls, please upgrade llama_index to be version>=0.10.35"
    )


def handle_events(event: BaseEvent):
    print("-----------------------")
    # all events have these attributes
    print(event.id_)
    print(event.timestamp)
    print(event.span_id)


class WeaveEventHandler(BaseEventHandler):
    def __init__(self) -> None:
        pass

    @classmethod
    def class_name(cls) -> str:
        return "WeaveEventHandler"

    def handle(self, event: BaseEvent) -> None:
        handle_events(event)


class LLamaIndexPatcher(Patcher):
    def __init__(self) -> None:
        pass

    def attempt_patch(self) -> bool:
        if import_failed:
            return False
        try:
            import llama_index.core.instrumentation as instrument

            self.dispatcher = instrument.get_dispatcher()
            self._original_event_handlers = self.dispatcher.event_handlers
            self.dispatcher.add_event_handler(WeaveEventHandler())
        except Exception:
            return False
        else:
            return True

    def undo_patch(self) -> bool:
        if not hasattr(self, "dispatcher"):
            return False
        try:
            import llama_index.core.instrumentation as instrument

            self.dispatcher.event_handlers = self._original_event_handlers
        except Exception:
            return False
        else:
            return True


llamaindex_patcher = LLamaIndexPatcher()
