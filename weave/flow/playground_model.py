import json
from typing import Any, Literal, Optional, Union

from weave import op
from weave.flow.model import Model
from weave.trace.context.weave_client_context import get_weave_client
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
    LLMStructuredCompletionModelDefaultParams,
    Message,
    ResponseFormat,
)
from weave.trace_server.trace_server_interface import (
    CompletionsCreateReq,
    CompletionsCreateRequestInputs,
)


class PlaygroundModel(Model):
    """
    A model that returns a completions output, configured by an LLMStructuredCompletionModel from the Playground.
    The predict method of this model will call the completions_create endpoint.

    You can specify the return type of the predict method by setting the return_type attribute, either "string", "message", or "json".
    The default return type is "message".

    """

    llm: LLMStructuredCompletionModel
    return_type: Literal["string", "message", "json"] = "message"

    def __init__(
        self,
        llm_structured_model_input: LLMStructuredCompletionModel,
        return_type: Optional[Literal["string", "message", "json"]] = "message",
    ):
        # Pass both llm_structured_model_input and client to super().__init__
        # so that Pydantic can correctly initialize these fields.
        super().__init__(
            llm=llm_structured_model_input,
            return_type=return_type,
        )

    @op()
    def predict(
        self,
        user_input: Union[Message, list[Message], str],
        config: Optional[dict[str, Any]] = None,
    ) -> Union[Message, str, dict[str, Any]]:
        """
        Generates a prediction by preparing messages (template + user_input)
        and calling the LLM completions endpoint with overridden config, using the provided client.
        """
        current_client = get_weave_client()
        if current_client is None:
            raise ValueError(
                "Error in PlaygroundModel.predict: No client found in context"
            )

        # 1. Prepare messages
        template_msgs = None
        if self.llm.default_params and self.llm.default_params.messages_template:
            template_msgs = self.llm.default_params.messages_template

        prepared_messages_dicts = _prepare_llm_messages(template_msgs, user_input)

        # 2. Prepare completion parameters, starting with defaults from LLMStructuredCompletionModel
        completion_params: dict[str, Any] = {}
        default_p_model = self.llm.default_params
        if default_p_model:
            completion_params = parse_params_to_litellm_params(default_p_model)

        # 3. Override parameters with the provided config dictionary
        if config:
            completion_params = {
                **completion_params,
                **parse_params_to_litellm_params(config),
            }

        # 4. Create the completion inputs
        model_id_str = str(self.llm.llm_model_id)
        completion_inputs = CompletionsCreateRequestInputs(
            model=model_id_str, messages=prepared_messages_dicts, **completion_params
        )
        req = CompletionsCreateReq(
            project_id=f"{current_client.entity}/{current_client.project}",
            inputs=completion_inputs,
        )

        # 5. Call the LLM API
        api_response = current_client.server.completions_create(req=req)

        # 6. Extract the message from the API response
        try:
            # The 'response' attribute of CompletionsCreateRes is a dict
            response_payload = api_response.response
            if response_payload.get("error"):
                # Or handle more gracefully depending on desired behavior
                raise RuntimeError(
                    f"LLM API returned an error: {response_payload['error']}"
                )

            # Assuming OpenAI-like structure: a list of choices, first choice has the message
            output_message_dict = response_payload["choices"][0]["message"]

            if self.return_type == "string":
                return output_message_dict["content"]
            elif self.return_type == "message":
                return Message.model_validate(output_message_dict)
            elif self.return_type == "json":
                return json.loads(output_message_dict["content"])
            else:
                raise ValueError(f"Invalid return_type: {self.return_type}")
        except (
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
            json.JSONDecodeError,
        ) as e:
            raise RuntimeError(
                f"Failed to extract message from LLM response payload. Response: {api_response.response}, Error: {e}"
            ) from e


def _prepare_llm_messages(
    template_messages: Optional[list[Message]],
    user_input: Union[Message, list[Message], str],
) -> list[dict[str, Any]]:
    """
    Prepares a list of message dictionaries for the LLM API from a message template and user input.
    Helper function for PlaygroundModel.predict.
    Returns a list of message dictionaries.
    """
    final_messages_dicts: list[dict[str, Any]] = []

    # 1. Initialize messages from template
    if template_messages:
        for msg_template in template_messages:
            msg_dict = msg_template.model_dump(exclude_none=True)
            final_messages_dicts.append(msg_dict)

    # 2. Parse user_input messages
    user_input_list: list[Message]
    if isinstance(user_input, str):
        user_input_list = [
            Message(
                role="user",
                content=user_input,
                name=None,
                function_call=None,
                tool_call_id=None,
            )
        ]
    elif isinstance(user_input, Message):
        user_input_list = [user_input]
    elif isinstance(user_input, list):
        user_input_list = user_input  # Assumes it's List[Message]
    else:
        raise TypeError(
            f"user_input must be a string, Message, or list of Messages, got {type(user_input)}"
        )

    # 3. Append user_input messages
    for u_msg in user_input_list:
        if not isinstance(u_msg, Message):
            # This check is important if user_input_list could come from an untyped list
            raise TypeError(
                f"Each item in user_input list must be of type Message, got {type(u_msg)}"
            )
        final_messages_dicts.append(u_msg.model_dump(exclude_none=True))

    return final_messages_dicts


def parse_params_to_litellm_params(
    params_source: Union[LLMStructuredCompletionModelDefaultParams, dict[str, Any]],
) -> dict[str, Any]:
    final_params: dict[str, Any] = {}
    source_dict_to_iterate: dict[str, Any]

    if isinstance(params_source, dict):
        source_dict_to_iterate = params_source
    elif hasattr(params_source, "model_dump"):  # Pydantic model
        source_dict_to_iterate = params_source.model_dump(exclude_none=True)
    else:
        raise TypeError(f"Unsupported type for params_source: {type(params_source)}")

    for key, value in source_dict_to_iterate.items():
        if key == "response_format":
            litellm_response_format_value = None
            if isinstance(value, ResponseFormat):  # Enum instance
                litellm_response_format_value = {"type": value.value}
            elif isinstance(value, str):  # String value
                if value.lower() == "text" or value == ResponseFormat.TEXT.value:
                    litellm_response_format_value = {"type": ResponseFormat.TEXT.value}
                elif (
                    value.lower() == "json"
                    or value.lower() == "json_object"
                    or value == ResponseFormat.JSON.value
                ):
                    litellm_response_format_value = {"type": ResponseFormat.JSON.value}
                # else: unknown string, might be a direct pass-through if LiteLLM supports it, or ignored
            elif isinstance(value, dict) and "type" in value:  # Pre-formed dict
                litellm_response_format_value = value

            if litellm_response_format_value is not None:
                final_params["response_format"] = litellm_response_format_value

        elif key == "n_times":
            final_params["n"] = value
        elif key == "messages_template":
            pass
        elif key == "functions" or key == "stop":
            if isinstance(value, list) and len(value) > 0:
                final_params[key] = value
        else:
            final_params[key] = value

    return final_params
