from typing import Any, TypedDict

from weave.trace.serialization import serializer


class OpenAICompletion(serializer.Serializer):
    def __init__(self):
        super().__init__(OpenAICompletionDict, save, load, instance_check)

    def id(self) -> str:
        return "weave.type_handlers.OpenAI.completion.OpenAICompletion"


class OpenAIClient(TypedDict):
    base_url: str


class OpenAICompletionDict(TypedDict):
    client: OpenAIClient


def save(obj: Any) -> OpenAICompletionDict:
    return {
        "client": {
            "base_url": str(obj._client._base_url),
        },
    }


def load(encoded: OpenAICompletionDict) -> OpenAICompletionDict:
    # without importing openai, we can't instantiate the object, so we just return the dict
    # we could improve it in the future if there is a necessity
    return encoded


def instance_check(obj: Any) -> bool:
    # test that the obj has certain properties and methods
    return (
        hasattr(obj, "messages")
        and hasattr(obj, "_client")
        and hasattr(obj, "_get")
        and hasattr(obj, "_post")
        and hasattr(obj, "_patch")
        and hasattr(obj, "_put")
        and hasattr(obj, "_delete")
        and hasattr(obj, "_get_api_list")
        and hasattr(obj, "create")
        and hasattr(obj, "with_raw_response")
        and hasattr(obj, "with_streaming_response")
    )


def register() -> None:
    serializer.SERIALIZERS.append(OpenAICompletion())
