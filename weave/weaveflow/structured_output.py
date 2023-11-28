import typing

import weave
from .chat_model import ChatModel


@weave.type()
class StructuredOutputChatModel:
    @weave.op()
    def complete(
        self, messages: list[typing.Any], output_type: weave.types.Type
    ) -> typing.Any:
        ...


@weave.type()
class StructuredOutputChatModelSystemPrompt(StructuredOutputChatModel):
    chat_llm: ChatModel

    @weave.op()
    def complete(
        self, messages: list[typing.Any], output_type: weave.types.Type
    ) -> typing.Any:
        import json

        mess = messages + [
            {
                "role": "system",
                "content": f"Your response should only include a json object that matches the following type definition: {str(output_type)}",
            }
        ]
        response = self.chat_llm.complete(mess)
        parsed_response = json.loads(response["choices"][0]["message"]["content"])
        if not output_type.assign_type(weave.type_of(parsed_response)):
            raise ValueError("invalid response")
        return parsed_response
