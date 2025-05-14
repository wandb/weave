import json
import unittest.mock
from typing import Any
from unittest.mock import MagicMock

import pytest

from weave.flow.playground_model import (
    LLMStructuredCompletionModel,
    LLMStructuredCompletionModelDefaultParams,
    Message,
    PlaygroundModel,
    ResponseFormat,
    parse_params_to_litellm_params,
)
from weave.trace.weave_client import WeaveClient
from weave.trace_server.trace_server_interface import (
    CompletionsCreateReq,
    CompletionsCreateRes,
)


@pytest.fixture
def mock_weave_client() -> WeaveClient:
    client = MagicMock(spec=WeaveClient)
    client.entity = "test_entity"
    client.project = "test_project"
    client.server = (
        MagicMock()
    )  # Mock the server attribute completions_create is called on
    return client


@pytest.fixture
def basic_llm_config_params() -> LLMStructuredCompletionModelDefaultParams:
    return LLMStructuredCompletionModelDefaultParams(
        messages_template=[Message(role="system", content="You are a test assistant.")],
        temperature=0.7,
        max_tokens=150,
        response_format=ResponseFormat.TEXT,
        stop=["""\n"""],  # Corrected multiline string for stop sequence
        functions=[],  # Empty list
    )


@pytest.fixture
def basic_llm_model_obj(
    basic_llm_config_params: LLMStructuredCompletionModelDefaultParams,
) -> LLMStructuredCompletionModel:
    return LLMStructuredCompletionModel(
        name="test_llm_model",
        llm_model_id="gpt-test-dummy",
        default_params=basic_llm_config_params,
    )


# --- Tests for parse_params_to_litellm_params ---


def test_parse_params_from_pydantic_model(
    basic_llm_config_params: LLMStructuredCompletionModelDefaultParams,
):
    expected = {
        "temperature": 0.7,
        "max_tokens": 150,
        "response_format": {"type": "text"},
        "stop": ["""\n"""],  # Corrected
        # messages_template is excluded
        # functions (empty list) is excluded by the logic in parse_params_to_litellm_params
    }
    actual = parse_params_to_litellm_params(basic_llm_config_params)
    assert actual == expected


def test_parse_params_from_pydantic_model_with_functions():
    params_obj = LLMStructuredCompletionModelDefaultParams(
        messages_template=[],
        functions=[{"name": "get_weather"}],
        response_format=ResponseFormat.JSON,  # "json_object"
    )
    expected = {
        "functions": [{"name": "get_weather"}],
        "response_format": {"type": "json_object"},
    }
    actual = parse_params_to_litellm_params(params_obj)
    assert actual == expected


def test_parse_params_from_dict():
    config_dict: dict[str, Any] = {
        "temperature": 0.5,
        "max_tokens": 50,
        "response_format": "json",  # Test string alias
        "n_times": 3,
        "stop": [],  # Empty list for stop
        "functions": [{"name": "custom_func"}],
        "custom_param": "value",
        "messages_template": [Message(role="user", content="this should be ignored")],
    }
    expected: dict[str, Any] = {
        "temperature": 0.5,
        "max_tokens": 50,
        "response_format": {"type": "json_object"},  # "json" string should map to this
        "n": 3,
        "functions": [{"name": "custom_func"}],
        "custom_param": "value",
        # messages_template excluded
        # stop (empty list) excluded
    }
    actual = parse_params_to_litellm_params(config_dict)
    assert actual == expected


def test_parse_params_from_dict_response_format_enum():
    config_dict: dict[str, Any] = {"response_format": ResponseFormat.TEXT}
    expected: dict[str, Any] = {"response_format": {"type": "text"}}
    actual = parse_params_to_litellm_params(config_dict)
    assert actual == expected


def test_parse_params_from_dict_response_format_direct_dict():
    config_dict: dict[str, Any] = {"response_format": {"type": "json_object"}}
    expected: dict[str, Any] = {"response_format": {"type": "json_object"}}
    actual = parse_params_to_litellm_params(config_dict)
    assert actual == expected


# --- Helper to create mock LLM responses ---
def mock_llm_api_response(
    content: str,
    role: str = "assistant",
    is_error: bool = False,
    error_msg: str = "LLM Error",
) -> CompletionsCreateRes:
    if is_error:
        return CompletionsCreateRes(response={"error": error_msg})

    message_payload: dict[str, Any] = {"role": role, "content": content}
    # Add other fields if needed, but keep it simple if not tested directly
    # message_payload["name"] = None
    # message_payload["function_call"] = None
    # message_payload["tool_call_id"] = None

    return CompletionsCreateRes(
        response={
            "choices": [{"message": message_payload}],
            "usage": {
                "total_tokens": 20,
                "prompt_tokens": 10,
                "completion_tokens": 10,
            },  # Example
        }
    )


# --- Tests for PlaygroundModel.predict ---


def test_predict_string_input_return_message(
    mock_weave_client: WeaveClient, basic_llm_model_obj: LLMStructuredCompletionModel
):
    mock_weave_client.server.completions_create.return_value = mock_llm_api_response(
        "Hello from LLM!"
    )
    with unittest.mock.patch(
        "weave.flow.playground_model.get_weave_client", return_value=mock_weave_client
    ):
        model = PlaygroundModel(basic_llm_model_obj, return_type="message")

        result = model.predict("Hi there")

    assert isinstance(result, Message)
    assert result.content == "Hello from LLM!"
    assert result.role == "assistant"

    mock_weave_client.server.completions_create.assert_called_once()
    called_req: CompletionsCreateReq = (
        mock_weave_client.server.completions_create.call_args[1]["req"]
    )

    assert len(called_req.inputs.messages) == 2  # system + user
    assert called_req.inputs.messages[0]["role"] == "system"
    assert called_req.inputs.messages[1]["role"] == "user"
    assert called_req.inputs.messages[1]["content"] == "Hi there"
    assert called_req.inputs.temperature == 0.7  # from default
    assert called_req.inputs.response_format == {"type": "text"}


def test_predict_message_input_return_string(
    mock_weave_client: WeaveClient, basic_llm_model_obj: LLMStructuredCompletionModel
):
    mock_weave_client.server.completions_create.return_value = mock_llm_api_response(
        "LLM says: string output"
    )
    with unittest.mock.patch(
        "weave.flow.playground_model.get_weave_client", return_value=mock_weave_client
    ):
        model = PlaygroundModel(basic_llm_model_obj, return_type="string")

        user_message = Message(role="user", content="Give me a string.")
        result = model.predict(user_message)

    assert isinstance(result, str)
    assert result == "LLM says: string output"


def test_predict_list_message_input_return_json_valid(
    mock_weave_client: WeaveClient, basic_llm_model_obj: LLMStructuredCompletionModel
):
    json_str_output = """{"data": "sample", "isValid": true}"""
    mock_weave_client.server.completions_create.return_value = mock_llm_api_response(
        json_str_output
    )

    # Modify model to expect JSON for this test
    basic_llm_model_obj.default_params.response_format = ResponseFormat.JSON
    with unittest.mock.patch(
        "weave.flow.playground_model.get_weave_client", return_value=mock_weave_client
    ):
        model = PlaygroundModel(basic_llm_model_obj, return_type="json")

        user_messages = [
            Message(role="user", content="Requesting JSON."),
            Message(
                role="assistant", content="Sure, I will provide JSON."
            ),  # Example of multi-turn
            Message(role="user", content="Proceed."),
        ]
        result = model.predict(user_messages)

    assert isinstance(result, dict)
    assert result == {"data": "sample", "isValid": True}

    called_req: CompletionsCreateReq = (
        mock_weave_client.server.completions_create.call_args[1]["req"]
    )
    assert called_req.inputs.response_format == {"type": "json_object"}
    assert len(called_req.inputs.messages) == 1 + len(
        user_messages
    )  # system + user_messages


def test_predict_return_json_invalid_content(
    mock_weave_client: WeaveClient, basic_llm_model_obj: LLMStructuredCompletionModel
):
    mock_weave_client.server.completions_create.return_value = mock_llm_api_response(
        "This is not valid JSON."
    )
    basic_llm_model_obj.default_params.response_format = (
        ResponseFormat.JSON
    )  # Ensure model asks for JSON
    with unittest.mock.patch(
        "weave.flow.playground_model.get_weave_client", return_value=mock_weave_client
    ):
        model = PlaygroundModel(basic_llm_model_obj, return_type="json")

        with pytest.raises(RuntimeError) as excinfo:
            model.predict("Input for invalid JSON.")
    assert "Failed to extract message" in str(excinfo.value)  # General wrapper error
    # The underlying error is json.JSONDecodeError
    assert isinstance(excinfo.value.__cause__, json.JSONDecodeError)


def test_predict_with_config_override(
    mock_weave_client: WeaveClient, basic_llm_model_obj: LLMStructuredCompletionModel
):
    mock_weave_client.server.completions_create.return_value = mock_llm_api_response(
        "Override successful."
    )
    with unittest.mock.patch(
        "weave.flow.playground_model.get_weave_client", return_value=mock_weave_client
    ):
        model = PlaygroundModel(
            basic_llm_model_obj, return_type="string"
        )  # Default temp 0.7

        config_override = {
            "temperature": 0.1,
            "max_tokens": 200,
            "response_format": "json",
        }
        result = model.predict("Test override", config=config_override)

    assert result == "Override successful."
    called_req: CompletionsCreateReq = (
        mock_weave_client.server.completions_create.call_args[1]["req"]
    )
    assert called_req.inputs.temperature == 0.1
    assert called_req.inputs.max_tokens == 200
    assert called_req.inputs.response_format == {"type": "json_object"}


def test_predict_llm_api_error_response(
    mock_weave_client: WeaveClient, basic_llm_model_obj: LLMStructuredCompletionModel
):
    mock_weave_client.server.completions_create.return_value = mock_llm_api_response(
        "", is_error=True, error_msg="Service Unavailable"
    )
    with unittest.mock.patch(
        "weave.flow.playground_model.get_weave_client", return_value=mock_weave_client
    ):
        model = PlaygroundModel(basic_llm_model_obj)

        with pytest.raises(RuntimeError) as excinfo:
            model.predict("Trigger error.")
    assert "LLM API returned an error: Service Unavailable" in str(excinfo.value)


def test_predict_malformed_llm_response_no_choices(
    mock_weave_client: WeaveClient, basic_llm_model_obj: LLMStructuredCompletionModel
):
    # Response that's a dict but doesn't conform to OpenAI structure
    malformed_res = CompletionsCreateRes(response={"unexpected_data": "value"})
    mock_weave_client.server.completions_create.return_value = malformed_res
    with unittest.mock.patch(
        "weave.flow.playground_model.get_weave_client", return_value=mock_weave_client
    ):
        model = PlaygroundModel(basic_llm_model_obj)

        with pytest.raises(RuntimeError) as excinfo:
            model.predict("Test malformed.")
    assert "Failed to extract message" in str(excinfo.value)
    # Check for underlying KeyError because "choices" will be missing
    assert isinstance(excinfo.value.__cause__, KeyError)
