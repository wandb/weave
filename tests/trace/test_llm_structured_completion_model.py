import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from pydantic import ValidationError

from weave import publish
from weave.prompt.prompt import MessagesPrompt
from weave.trace import object_record, vals
from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
    LLMStructuredCompletionModelDefaultParams,
    Message,
    _prepare_llm_messages,
    cast_to_llm_structured_model_params,
    cast_to_message,
    cast_to_message_list,
    parse_params_to_litellm_params,
    parse_response,
)


def test_llm_structured_completion_model_creation_and_class_assignment(
    client: WeaveClient,
):
    """Test creating LLMStructuredCompletionModel and verify base/leaf object classes are set properly."""
    # Test 1: Create with minimal parameters via builtin_object_class
    model_minimal = LLMStructuredCompletionModel(llm_model_id="gpt-4")
    minimal_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "llm_model_minimal",
                    "val": model_minimal.model_dump(by_alias=True),
                    "builtin_object_class": "LLMStructuredCompletionModel",
                }
            }
        )
    )

    # Read back and verify class assignment
    read_minimal_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id="llm_model_minimal",
            digest=minimal_res.digest,
        )
    )

    assert read_minimal_res.obj.base_object_class == "Model"
    assert read_minimal_res.obj.leaf_object_class == "LLMStructuredCompletionModel"
    assert read_minimal_res.obj.val["llm_model_id"] == "gpt-4"

    # Test 2: Create with full default parameters
    default_params = LLMStructuredCompletionModelDefaultParams(
        messages_template=[
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello {name}!"),
        ],
        temperature=0.7,
        max_tokens=1000,
        response_format="text",
    )

    model_full = LLMStructuredCompletionModel(
        llm_model_id="gpt-3.5-turbo",
        default_params=default_params,
    )

    full_res = client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "llm_model_full",
                    "val": model_full.model_dump(by_alias=True),
                    "builtin_object_class": "LLMStructuredCompletionModel",
                }
            }
        )
    )

    # Read back and verify
    read_full_res = client.server.obj_read(
        tsi.ObjReadReq(
            project_id=client.project_id,
            object_id="llm_model_full",
            digest=full_res.digest,
        )
    )

    assert read_full_res.obj.base_object_class == "Model"
    assert read_full_res.obj.leaf_object_class == "LLMStructuredCompletionModel"
    assert read_full_res.obj.val["llm_model_id"] == "gpt-3.5-turbo"
    assert read_full_res.obj.val["default_params"]["temperature"] == 0.7
    assert read_full_res.obj.val["default_params"]["max_tokens"] == 1000
    assert read_full_res.obj.val["default_params"]["response_format"] == "text"

    # Test 3: Verify the model can be instantiated correctly via class extraction
    # Read back the minimal object and verify it can be converted to the right type
    assert read_minimal_res.obj.leaf_object_class == "LLMStructuredCompletionModel"

    # The object should contain the necessary fields for the LLMStructuredCompletionModel
    obj_val = read_minimal_res.obj.val
    assert "llm_model_id" in obj_val
    assert "default_params" in obj_val

    # We can reconstruct the model from the stored data (excluding metadata fields)
    clean_val = {k: v for k, v in obj_val.items() if not k.startswith("_")}
    reconstructed_model = LLMStructuredCompletionModel.model_validate(clean_val)
    assert reconstructed_model.llm_model_id == "gpt-4"


def test_llm_structured_completion_model_filtering(client: WeaveClient):
    """Test querying LLMStructuredCompletionModel objects by leaf/base object classes."""
    # Create multiple models
    model1 = LLMStructuredCompletionModel(llm_model_id="gpt-4")
    model2 = LLMStructuredCompletionModel(llm_model_id="claude-3")

    client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "model_1",
                    "val": model1.model_dump(by_alias=True),
                    "builtin_object_class": "LLMStructuredCompletionModel",
                }
            }
        )
    )

    client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "model_2",
                    "val": model2.model_dump(by_alias=True),
                    "builtin_object_class": "LLMStructuredCompletionModel",
                }
            }
        )
    )

    # Test filtering by leaf_object_class
    leaf_filter_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"leaf_object_classes": ["LLMStructuredCompletionModel"]},
            }
        )
    )

    assert len(leaf_filter_res.objs) == 2
    assert all(
        obj.leaf_object_class == "LLMStructuredCompletionModel"
        for obj in leaf_filter_res.objs
    )
    assert all(obj.base_object_class == "Model" for obj in leaf_filter_res.objs)

    # Test filtering by base_object_class
    base_filter_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {"base_object_classes": ["Model"]},
            }
        )
    )

    assert len(base_filter_res.objs) == 2
    assert all(obj.base_object_class == "Model" for obj in base_filter_res.objs)

    # Test combined filtering
    combined_filter_res = client.server.objs_query(
        tsi.ObjQueryReq.model_validate(
            {
                "project_id": client.project_id,
                "filter": {
                    "base_object_classes": ["Model"],
                    "leaf_object_classes": ["LLMStructuredCompletionModel"],
                },
            }
        )
    )

    assert len(combined_filter_res.objs) == 2


@patch(
    "weave.trace_server.interface.builtin_object_classes.llm_structured_model.get_weave_client"
)
def test_predict_text_and_json_response(mock_get_client):
    """predict() returns raw text for response_format=text and parsed dict for json_object."""
    mock_client = _mock_client(mock_get_client)

    mock_client.server.completions_create.return_value = _completion_res(
        "Hello! How can I help you today?"
    )
    text_model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4",
        default_params=LLMStructuredCompletionModelDefaultParams(
            temperature=0.7, max_tokens=100, response_format="text"
        ),
    )
    assert text_model.predict(user_input="Hello") == "Hello! How can I help you today?"
    mock_client.server.completions_create.assert_called_once()
    text_args = mock_client.server.completions_create.call_args[1]["req"]
    assert text_args.project_id == "test_entity/test_project"
    assert text_args.inputs.model == "gpt-4"
    assert text_args.inputs.temperature == 0.7
    assert text_args.inputs.max_tokens == 100
    assert text_args.inputs.messages == [{"role": "user", "content": "Hello"}]

    json_content = {"result": "success", "data": {"message": "Hello World"}}
    mock_client.server.completions_create.return_value = _completion_res(
        json.dumps(json_content)
    )
    json_model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4",
        default_params=LLMStructuredCompletionModelDefaultParams(
            response_format="json_object"
        ),
    )
    json_result = json_model.predict(user_input="Generate JSON")
    assert isinstance(json_result, dict)
    assert json_result == json_content
    assert json_result["result"] == "success"


@patch(
    "weave.trace_server.interface.builtin_object_classes.llm_structured_model.get_weave_client"
)
def test_predict_with_template_and_config_override(mock_get_client):
    """Template vars are substituted into messages; a `config` arg overrides defaults."""
    mock_client = _mock_client(mock_get_client)

    mock_client.server.completions_create.return_value = _completion_res(
        "Hello Alice! I'm Claude, nice to meet you."
    )
    template_model = LLMStructuredCompletionModel(
        llm_model_id="claude-3",
        default_params=LLMStructuredCompletionModelDefaultParams(
            messages_template=[
                Message(role="system", content="You are {assistant_name}, a helpful AI."),
                Message(role="user", content="Hello, my name is {user_name}"),
            ],
            response_format="text",
        ),
    )
    template_result = template_model.predict(
        user_input=[Message(role="user", content="What's your name?")],
        assistant_name="Claude",
        user_name="Alice",
    )
    assert template_result == "Hello Alice! I'm Claude, nice to meet you."
    template_args = mock_client.server.completions_create.call_args[1]["req"]
    assert template_args.inputs.messages == [
        {"role": "system", "content": "You are Claude, a helpful AI."},
        {"role": "user", "content": "Hello, my name is Alice"},
        {"role": "user", "content": "What's your name?"},
    ]

    mock_client.server.completions_create.return_value = _completion_res(
        "Response with overridden config"
    )
    override_model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4",
        default_params=LLMStructuredCompletionModelDefaultParams(
            temperature=0.5, max_tokens=100, response_format="text"
        ),
    )
    override_model.predict(
        user_input="Test message",
        config=LLMStructuredCompletionModelDefaultParams(temperature=0.9, max_tokens=200),
    )
    override_args = mock_client.server.completions_create.call_args[1]["req"]
    assert override_args.inputs.temperature == 0.9
    assert override_args.inputs.max_tokens == 200


@patch(
    "weave.trace_server.interface.builtin_object_classes.llm_structured_model.get_weave_client"
)
def test_llm_structured_completion_model_predict_error_handling(mock_get_client):
    """Test the predict function error handling."""
    # Setup mock client
    mock_client = Mock()
    mock_client.entity = "test_entity"
    mock_client.project = "test_project"

    # Test 1: API error response
    mock_error_response = tsi.CompletionsCreateRes(
        response={"error": "API rate limit exceeded"}
    )
    mock_client.server.completions_create.return_value = mock_error_response
    mock_get_client.return_value = mock_client

    model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4",
        default_params=LLMStructuredCompletionModelDefaultParams(
            response_format="text"
        ),
    )

    with pytest.raises(RuntimeError, match="LLM API returned an error"):
        model.predict(user_input="Test")

    # Test 2: API exception
    mock_client.server.completions_create.side_effect = Exception("Connection failed")

    with pytest.raises(RuntimeError, match="Failed to call LLM completions endpoint"):
        model.predict(user_input="Test")

    # Test 3: Invalid response format
    mock_client.server.completions_create.side_effect = None
    mock_invalid_response = tsi.CompletionsCreateRes(response={"invalid": "response"})
    mock_client.server.completions_create.return_value = mock_invalid_response

    with pytest.raises(
        RuntimeError, match="Failed to extract message from LLM response"
    ):
        model.predict(user_input="Test")


def test_parse_response_errors_and_happy_paths():
    """`parse_response` surfaces user-actionable errors and returns good content unchanged.

    Guards replace raw TypeError/JSONDecodeError noise from the scoring worker (WB-34500).
    """
    # API-level error: still RuntimeError (unchanged contract).
    with pytest.raises(RuntimeError, match="LLM API returned an error"):
        parse_response({"error": "rate limit exceeded"}, "text")

    # Missing choices -> clear ValueError instead of KeyError.
    with pytest.raises(ValueError, match="missing 'choices'"):
        parse_response({"some": "other"}, "json_object")

    # Choice without a message dict -> TypeError (wrong shape).
    with pytest.raises(TypeError, match="did not contain a message dict"):
        parse_response({"choices": [{"finish_reason": "stop"}]}, "text")

    # Text response with None content -> ValueError instead of returning None.
    with pytest.raises(ValueError, match="content is None"):
        parse_response({"choices": [{"message": {"content": None}}]}, "text")

    # json_object with None content -> ValueError instead of TypeError on json.loads(None).
    with pytest.raises(ValueError, match="empty when JSON output was requested"):
        parse_response({"choices": [{"message": {"content": None}}]}, "json_object")

    # json_object with empty string -> same ValueError (not JSONDecodeError).
    with pytest.raises(ValueError, match="empty when JSON output was requested"):
        parse_response({"choices": [{"message": {"content": "   "}}]}, "json_object")

    # json_object with non-JSON string -> ValueError with content snippet.
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_response(
            {"choices": [{"message": {"content": "I think the answer is 42"}}]},
            "json_object",
        )

    # Happy paths: content / parsed JSON returned unchanged on good input.
    assert (
        parse_response({"choices": [{"message": {"content": "hello"}}]}, "text")
        == "hello"
    )
    assert parse_response(
        {"choices": [{"message": {"content": '{"a": 1}'}}]}, "json_object"
    ) == {"a": 1}


def test_prepare_llm_messages():
    """Test the _prepare_llm_messages helper function."""
    # Test with template and user input
    template_messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Context: important info"),
    ]

    user_input = [
        Message(role="user", content="What is the weather?"),
    ]

    result = _prepare_llm_messages(template_messages, user_input)

    expected = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Context: important info"},
        {"role": "user", "content": "What is the weather?"},
    ]

    assert result == expected

    # Test with no template
    result = _prepare_llm_messages(None, user_input)
    assert result == [{"role": "user", "content": "What is the weather?"}]

    # Test with no user input
    result = _prepare_llm_messages(template_messages, [])
    assert result == [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Context: important info"},
    ]


def test_parse_params_to_litellm_params():
    """Test the parse_params_to_litellm_params helper function."""
    # Test comprehensive parameter conversion
    params = LLMStructuredCompletionModelDefaultParams(
        temperature=0.7,
        max_tokens=1000,
        top_p=0.9,
        presence_penalty=0.1,
        frequency_penalty=0.2,
        stop=["END", "STOP"],
        n_times=2,
        response_format="json_object",
        functions=[{"name": "test_func"}],
    )

    result = parse_params_to_litellm_params(params)

    expected = {
        "temperature": 0.7,
        "max_tokens": 1000,
        "top_p": 0.9,
        "presence_penalty": 0.1,
        "frequency_penalty": 0.2,
        "stop": ["END", "STOP"],
        "n": 2,  # n_times -> n
        "response_format": {"type": "json_object"},
        "functions": [{"name": "test_func"}],
    }

    assert result == expected

    # Test response_format handling
    params_text = LLMStructuredCompletionModelDefaultParams(response_format="text")
    result_text = parse_params_to_litellm_params(params_text)
    assert result_text["response_format"] == {"type": "text"}

    # Test empty lists are excluded
    params_empty = LLMStructuredCompletionModelDefaultParams(
        stop=[],
        functions=[],
    )
    result_empty = parse_params_to_litellm_params(params_empty)
    assert "stop" not in result_empty
    assert "functions" not in result_empty

    # Test None values are excluded
    params_none = LLMStructuredCompletionModelDefaultParams(
        temperature=None,
        max_tokens=100,
    )
    result_none = parse_params_to_litellm_params(params_none)
    assert "temperature" not in result_none
    assert result_none["max_tokens"] == 100

    # Test that messages_template is excluded but prompt is included
    params_with_prompt = LLMStructuredCompletionModelDefaultParams(
        temperature=0.5,
        prompt="weave:///entity/project/object/my_prompt:latest",
        messages_template=[Message(role="system", content="Test")],
    )
    result_with_prompt = parse_params_to_litellm_params(params_with_prompt)
    assert (
        result_with_prompt["prompt"]
        == "weave:///entity/project/object/my_prompt:latest"
    )
    assert "messages_template" not in result_with_prompt
    assert result_with_prompt["temperature"] == 0.5


def test_cast_to_message_and_message_list():
    """`cast_to_message` and `cast_to_message_list` coerce Message/str/dict, reject bad types."""
    # cast_to_message: passthrough, string, dict, and invalid type.
    msg = Message(role="user", content="Hello")
    assert cast_to_message(msg) == msg
    from_str = cast_to_message("Hello world")
    assert from_str.role == "user"
    assert from_str.content == "Hello world"
    from_dict = cast_to_message({"role": "system", "content": "System message"})
    assert from_dict.role == "system"
    assert from_dict.content == "System message"
    with pytest.raises(TypeError):
        cast_to_message(123)

    # cast_to_message_list: single Message, single string, single dict.
    single_msg = cast_to_message_list(msg)
    assert len(single_msg) == 1
    assert single_msg[0] == msg
    single_str = cast_to_message_list("Hello world")
    assert len(single_str) == 1
    assert single_str[0].role == "user"
    assert single_str[0].content == "Hello world"
    single_dict = cast_to_message_list({"role": "system", "content": "You are helpful"})
    assert len(single_dict) == 1
    assert single_dict[0].role == "system"
    assert single_dict[0].content == "You are helpful"

    # cast_to_message_list: mixed list and invalid type.
    mixed = cast_to_message_list(
        [
            "Hello",
            {"role": "assistant", "content": "Hi there"},
            Message(role="user", content="How are you?"),
        ]
    )
    assert len(mixed) == 3
    assert mixed[0].role == "user"
    assert mixed[0].content == "Hello"
    assert mixed[1].role == "assistant"
    assert mixed[1].content == "Hi there"
    assert mixed[2].role == "user"
    assert mixed[2].content == "How are you?"
    with pytest.raises(TypeError):
        cast_to_message_list(123)


@patch(
    "weave.trace_server.interface.builtin_object_classes.llm_structured_model.get_weave_client"
)
def test_predict_with_prompt_delegates_and_takes_precedence(
    mock_get_client, client: WeaveClient
):
    """A `prompt` ref + template_vars are delegated to completions_create.

    The model no longer resolves prompts itself; it passes the ref through and, when both
    prompt and messages_template are set, prompt wins (messages_template is dropped).
    """
    mock_client = _mock_client(mock_get_client, entity=client.entity, project=client.project)

    # Prompt-only model: delegates prompt + template_vars, keeps only user_input messages.
    prompt_ref = publish(
        MessagesPrompt(
            messages=[
                {"role": "system", "content": "You are {assistant_name}, a helpful AI."},
                {"role": "user", "content": "Hello, my name is {user_name}"},
            ]
        ),
        name="test_messages_prompt",
    )
    mock_client.server.completions_create.return_value = _completion_res(
        "Hello Alice! I'm Claude, nice to meet you."
    )
    prompt_model = LLMStructuredCompletionModel(
        llm_model_id="claude-3",
        default_params=LLMStructuredCompletionModelDefaultParams(
            prompt=prompt_ref.uri, response_format="text"
        ),
    )
    prompt_result = prompt_model.predict(
        user_input=[Message(role="user", content="What's your name?")],
        assistant_name="Claude",
        user_name="Alice",
    )
    assert prompt_result == "Hello Alice! I'm Claude, nice to meet you."
    prompt_args = mock_client.server.completions_create.call_args[1]["req"]
    assert prompt_args.inputs.prompt == prompt_ref.uri
    assert prompt_args.inputs.template_vars == {
        "assistant_name": "Claude",
        "user_name": "Alice",
    }
    assert prompt_args.inputs.messages == [
        {"role": "user", "content": "What's your name?"}
    ]

    # prompt + messages_template: prompt takes precedence, no user_input -> empty messages.
    precedence_ref = publish(
        MessagesPrompt(messages=[{"role": "system", "content": "Message from prompt: {var}"}]),
        name="test_precedence_prompt",
    )
    mock_client.server.completions_create.return_value = _completion_res("Response")
    precedence_model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4",
        default_params=LLMStructuredCompletionModelDefaultParams(
            prompt=precedence_ref.uri,
            messages_template=[
                Message(role="system", content="Message from template: {var}"),
            ],
            response_format="text",
        ),
    )
    precedence_model.predict(var="test_value")
    precedence_args = mock_client.server.completions_create.call_args[1]["req"]
    assert precedence_args.inputs.prompt == precedence_ref.uri
    assert precedence_args.inputs.template_vars == {"var": "test_value"}
    assert precedence_args.inputs.messages == []


def test_llm_structured_completion_model_schema_validation(client: WeaveClient):
    """Test schema validation for LLMStructuredCompletionModel."""
    # Test missing required field
    with pytest.raises(ValidationError):  # ValidationError or similar
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client.project_id,
                        "object_id": "invalid_model",
                        "val": {
                            # Missing required llm_model_id
                            "default_params": {"temperature": 0.5}
                        },
                        "builtin_object_class": "LLMStructuredCompletionModel",
                    }
                }
            )
        )

    # Test valid minimal model
    client.server.obj_create(
        tsi.ObjCreateReq.model_validate(
            {
                "obj": {
                    "project_id": client.project_id,
                    "object_id": "valid_minimal_model",
                    "val": {
                        "llm_model_id": "gpt-4",
                    },
                    "builtin_object_class": "LLMStructuredCompletionModel",
                }
            }
        )
    )


def test_cast_to_llm_structured_model_params_handles_weave_object():
    """Regression: default_params passed as a WeaveObject should be cast correctly."""
    record = object_record.ObjectRecord(
        {
            "_class_name": "LLMStructuredCompletionModelDefaultParams",
            "_bases": [],
            "response_format": "json_object",
            "temperature": 0.5,
            "top_p": None,
            "max_tokens": None,
            "presence_penalty": None,
            "frequency_penalty": None,
            "stop": None,
            "n_times": None,
            "functions": None,
            "messages_template": None,
            "prompt": None,
        }
    )
    weave_obj = vals.WeaveObject(record, ref=None, server=MagicMock(), root=None)

    result = cast_to_llm_structured_model_params(weave_obj)
    assert isinstance(result, LLMStructuredCompletionModelDefaultParams)
    assert result.response_format == "json_object"
    assert result.temperature == 0.5


def _mock_client(
    mock_get_client, entity: str = "test_entity", project: str = "test_project"
) -> Mock:
    """Wire a Mock weave client into the patched `get_weave_client` and return it."""
    mock_client = Mock()
    mock_client.entity = entity
    mock_client.project = project
    mock_get_client.return_value = mock_client
    return mock_client


def _completion_res(content: str) -> tsi.CompletionsCreateRes:
    """Build a single-choice assistant CompletionsCreateRes with `content`."""
    return tsi.CompletionsCreateRes(
        response={"choices": [{"message": {"role": "assistant", "content": content}}]}
    )
