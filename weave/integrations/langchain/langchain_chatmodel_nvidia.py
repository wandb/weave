import importlib
from functools import wraps
from typing import Any, Callable

import weave
from weave.trace.patcher import MultiPatcher, SymbolPatcher
from weave.trace.op import Op, ProcessedInputs

try:
    from langchain_core.load import dumpd
    from langchain_core.messages import BaseMessage, AIMessage
    from langchain_core.outputs import ChatResult, ChatGeneration
    from langchain_core.tracers import Run
    from langchain_core.tracers.base import BaseTracer
    from langchain_core.tracers.context import register_configure_hook
    from openai.types.chat import ChatCompletion
except ImportError:
    import_failed = True

def chat_nvidia_input_handler(
    func: Op, args: tuple, kwargs: dict
) -> ProcessedInputs | None:
    if len(args) == 2 and isinstance(args[1], weave.EasyPrompt):
        original_args = args
        original_kwargs = kwargs
        prompt = args[1]
        args = args[:-1]
        kwargs.update(prompt.as_dict())
        inputs = {
            "prompt": prompt,
        }
        return ProcessedInputs(
            original_args=original_args,
            original_kwargs=original_kwargs,
            args=args,
            kwargs=kwargs,
            inputs=inputs,
        )
    return None

def chat_nvidia_post_processor(call, original_output, exception) -> ChatCompletion:
    if exception is not None:
        return call, original_output

    llmoutput = original_output.llm_output
    generations = original_output.generations
    usage = llmoutput.get("token_usage", {})


    # Prepare choices
    choices = [
        {
            "index": idx,
            "message": {
                "role": generation.message.role,
                "content": generation.message.content,
            },
            "finish_reason": llmoutput.get("finish_reason", "stop"),
        }
        for idx, generation in enumerate(generations)
    ]

    # Construct ChatCompletion
    chat_completion = ChatCompletion(
        id=response.get("id", "unique-id"),
        object="invoke",
        created=llmoutput.get("created", 0),
        model=llmoutput.get("model_name", "unknown-model"),
        choices=choices,
        usage={
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    )

    return chat_completion.model_dump(exclude_unset=True, exclude_none=True)

def create_wrapper_sync(
    name: str,
) -> Callable[[Callable], Callable]:
    def wrapper(fn: Callable) -> Callable:
        op = weave.op()(fn)
        op.name = name  # type: ignore
        op._set_on_input_handler(chat_nvidia_input_handler)
        op._set_on_finish_handler(chat_nvidia_post_processor)
        return op

    return wrapper


langchain_chatmodel_nvidia_patcher = MultiPatcher(
    [
        SymbolPatcher(
            lambda: importlib.import_module("langchain_nvidia_ai_endpoints"),
            "ChatNVIDIA._generate",
            create_wrapper_sync(name="langchain_nvidia_ai_endpoints.ChatNVIDIA.invoke"),
        )
    ]
)
