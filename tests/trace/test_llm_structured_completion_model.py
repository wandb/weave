import json
from unittest.mock import Mock, patch

import pytest

from weave.trace.weave_client import WeaveClient
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
    LLMStructuredCompletionModelDefaultParams,
    Message,
    _prepare_llm_messages,
    _substitute_template_variables,
    cast_to_message,
    cast_to_message_list,
    parse_params_to_litellm_params,
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
                    "project_id": client._project_id(),
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
            project_id=client._project_id(),
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
                    "project_id": client._project_id(),
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
            project_id=client._project_id(),
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
                    "project_id": client._project_id(),
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
                    "project_id": client._project_id(),
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
                "project_id": client._project_id(),
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
                "project_id": client._project_id(),
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
                "project_id": client._project_id(),
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
def test_llm_structured_completion_model_predict_text_response(
    mock_get_client, client: WeaveClient
):
    """Test the predict function with mocked LLM API response for text format."""
    # Setup mock client
    mock_client = Mock()
    mock_client.entity = "test_entity"
    mock_client.project = "test_project"

    # Mock successful API response
    mock_response = tsi.CompletionsCreateRes(
        response={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help you today?",
                    }
                }
            ]
        }
    )
    mock_client.server.completions_create.return_value = mock_response
    mock_get_client.return_value = mock_client

    # Create model with text response format
    model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4",
        default_params=LLMStructuredCompletionModelDefaultParams(
            temperature=0.7,
            max_tokens=100,
            response_format="text",
        ),
    )

    # Test predict with simple string input
    result = model.predict(user_input="Hello")

    # Verify result
    assert result == "Hello! How can I help you today?"

    # Verify API call was made correctly
    mock_client.server.completions_create.assert_called_once()
    call_args = mock_client.server.completions_create.call_args[1]["req"]
    assert call_args.project_id == "test_entity/test_project"
    assert call_args.inputs.model == "gpt-4"
    assert call_args.inputs.temperature == 0.7
    assert call_args.inputs.max_tokens == 100
    assert call_args.inputs.messages == [{"role": "user", "content": "Hello"}]


@patch(
    "weave.trace_server.interface.builtin_object_classes.llm_structured_model.get_weave_client"
)
def test_llm_structured_completion_model_predict_json_response(
    mock_get_client, client: WeaveClient
):
    """Test the predict function with mocked LLM API response for JSON format."""
    # Setup mock client
    mock_client = Mock()
    mock_client.entity = "test_entity"
    mock_client.project = "test_project"

    # Mock successful API response with JSON content
    json_content = {"result": "success", "data": {"message": "Hello World"}}
    mock_response = tsi.CompletionsCreateRes(
        response={
            "choices": [
                {"message": {"role": "assistant", "content": json.dumps(json_content)}}
            ]
        }
    )
    mock_client.server.completions_create.return_value = mock_response
    mock_get_client.return_value = mock_client

    # Create model with JSON response format
    model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4",
        default_params=LLMStructuredCompletionModelDefaultParams(
            response_format="json_object",
        ),
    )

    # Test predict
    result = model.predict(user_input="Generate JSON")

    # Verify result is parsed JSON
    assert result == json_content
    assert isinstance(result, dict)
    assert result["result"] == "success"


@patch(
    "weave.trace_server.interface.builtin_object_classes.llm_structured_model.get_weave_client"
)
def test_llm_structured_completion_model_predict_with_template(
    mock_get_client, client: WeaveClient
):
    """Test the predict function with message templates and template variables."""
    # Setup mock client
    mock_client = Mock()
    mock_client.entity = "test_entity"
    mock_client.project = "test_project"

    mock_response = tsi.CompletionsCreateRes(
        response={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello Alice! I'm Claude, nice to meet you.",
                    }
                }
            ]
        }
    )
    mock_client.server.completions_create.return_value = mock_response
    mock_get_client.return_value = mock_client

    # Create model with message template
    model = LLMStructuredCompletionModel(
        llm_model_id="claude-3",
        default_params=LLMStructuredCompletionModelDefaultParams(
            messages_template=[
                Message(
                    role="system", content="You are {assistant_name}, a helpful AI."
                ),
                Message(role="user", content="Hello, my name is {user_name}"),
            ],
            response_format="text",
        ),
    )

    # Test predict with template variables
    result = model.predict(
        user_input=[Message(role="user", content="What's your name?")],
        assistant_name="Claude",
        user_name="Alice",
    )

    # Verify result
    assert result == "Hello Alice! I'm Claude, nice to meet you."

    # Verify the messages were properly prepared with template substitution
    call_args = mock_client.server.completions_create.call_args[1]["req"]
    expected_messages = [
        {"role": "system", "content": "You are Claude, a helpful AI."},
        {"role": "user", "content": "Hello, my name is Alice"},
        {"role": "user", "content": "What's your name?"},
    ]
    assert call_args.inputs.messages == expected_messages


@patch(
    "weave.trace_server.interface.builtin_object_classes.llm_structured_model.get_weave_client"
)
def test_llm_structured_completion_model_predict_with_config_override(
    mock_get_client, client: WeaveClient
):
    """Test the predict function with config parameter overriding defaults."""
    # Setup mock client
    mock_client = Mock()
    mock_client.entity = "test_entity"
    mock_client.project = "test_project"

    mock_response = tsi.CompletionsCreateRes(
        response={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Response with overridden config",
                    }
                }
            ]
        }
    )
    mock_client.server.completions_create.return_value = mock_response
    mock_get_client.return_value = mock_client

    # Create model with default parameters
    model = LLMStructuredCompletionModel(
        llm_model_id="gpt-4",
        default_params=LLMStructuredCompletionModelDefaultParams(
            temperature=0.5,
            max_tokens=100,
            response_format="text",
        ),
    )

    # Test predict with config override
    override_config = LLMStructuredCompletionModelDefaultParams(
        temperature=0.9,
        max_tokens=200,
    )

    result = model.predict(
        user_input="Test message",
        config=override_config,
    )

    # Verify override was applied
    call_args = mock_client.server.completions_create.call_args[1]["req"]
    assert call_args.inputs.temperature == 0.9  # Overridden
    assert call_args.inputs.max_tokens == 200  # Overridden


@patch(
    "weave.trace_server.interface.builtin_object_classes.llm_structured_model.get_weave_client"
)
def test_llm_structured_completion_model_predict_error_handling(
    mock_get_client, client: WeaveClient
):
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


def test_substitute_template_variables():
    """Test the _substitute_template_variables helper function."""
    # Test basic substitution
    messages = [
        Message(role="system", content="You are {assistant_name}"),
        Message(role="user", content="Hello {user_name}, how are you?"),
    ]

    template_vars = {"assistant_name": "Claude", "user_name": "Alice"}
    result = _substitute_template_variables(messages, template_vars)

    assert len(result) == 2
    assert result[0].content == "You are Claude"
    assert result[1].content == "Hello Alice, how are you?"
    assert result[0].role == "system"
    assert result[1].role == "user"

    # Test missing template variable
    with pytest.raises(ValueError, match="Template variable"):
        _substitute_template_variables(
            [Message(role="user", content="Hello {missing_var}")],
            {"other_var": "value"},
        )

    # Test message without content
    messages_no_content = [
        Message(role="system", content=None),
        Message(role="user", content="Hello {name}"),
    ]
    result = _substitute_template_variables(messages_no_content, {"name": "World"})
    assert result[0].content is None
    assert result[1].content == "Hello World"


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


def test_cast_to_message_list():
    """Test the cast_to_message_list function."""
    # Test single Message object
    msg = Message(role="user", content="Hello")
    result = cast_to_message_list(msg)
    assert len(result) == 1
    assert result[0] == msg

    # Test single string
    result = cast_to_message_list("Hello world")
    assert len(result) == 1
    assert result[0].role == "user"
    assert result[0].content == "Hello world"

    # Test single dict
    msg_dict = {"role": "system", "content": "You are helpful"}
    result = cast_to_message_list(msg_dict)
    assert len(result) == 1
    assert result[0].role == "system"
    assert result[0].content == "You are helpful"

    # Test list of mixed types
    mixed_list = [
        "Hello",
        {"role": "assistant", "content": "Hi there"},
        Message(role="user", content="How are you?"),
    ]
    result = cast_to_message_list(mixed_list)
    assert len(result) == 3
    assert result[0].role == "user"
    assert result[0].content == "Hello"
    assert result[1].role == "assistant"
    assert result[1].content == "Hi there"
    assert result[2].role == "user"
    assert result[2].content == "How are you?"

    # Test invalid type
    with pytest.raises(TypeError):
        cast_to_message_list(123)


def test_cast_to_message():
    """Test the cast_to_message function."""
    # Test Message object (passthrough)
    msg = Message(role="user", content="Hello")
    result = cast_to_message(msg)
    assert result == msg

    # Test string conversion
    result = cast_to_message("Hello world")
    assert result.role == "user"
    assert result.content == "Hello world"

    # Test dict conversion
    msg_dict = {"role": "system", "content": "System message"}
    result = cast_to_message(msg_dict)
    assert result.role == "system"
    assert result.content == "System message"

    # Test invalid type
    with pytest.raises(TypeError):
        cast_to_message(123)


def test_llm_structured_completion_model_schema_validation(client: WeaveClient):
    """Test schema validation for LLMStructuredCompletionModel."""
    # Test missing required field
    with pytest.raises(Exception):  # ValidationError or similar
        client.server.obj_create(
            tsi.ObjCreateReq.model_validate(
                {
                    "obj": {
                        "project_id": client._project_id(),
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
                    "project_id": client._project_id(),
                    "object_id": "valid_minimal_model",
                    "val": {
                        "llm_model_id": "gpt-4",
                    },
                    "builtin_object_class": "LLMStructuredCompletionModel",
                }
            }
        )
    )
