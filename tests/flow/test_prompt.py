from weave.prompt.prompt import (
    MessagesPrompt,
    StringPrompt,
    EasyPrompt,
    PROVIDER_OPENAI,
    PROVIDER_BEDROCK,
    convert_openai_to_bedrock,
    convert_bedrock_to_openai,
    validate_bedrock_format,
    infer_provider_from_model,
    infer_provider_from_content,
)


def test_stringprompt_format():
    prompt = StringPrompt("You are a pirate. Tell us your thoughts on {topic}.")
    assert (
        prompt.format(topic="airplanes")
        == "You are a pirate. Tell us your thoughts on airplanes."
    )


def test_messagesprompt_format():
    prompt = MessagesPrompt(
        [
            {"role": "system", "content": "You are a pirate."},
            {"role": "user", "content": "Tell us your thoughts on {topic}."},
        ]
    )
    assert prompt.format(topic="airplanes") == [
        {"role": "system", "content": "You are a pirate."},
        {"role": "user", "content": "Tell us your thoughts on airplanes."},
    ]


def test_messagesprompt_nesteddict_format():
    prompt = MessagesPrompt(
        [
            {"role": "system", "content": "You are a pirate."},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Tell us your thoughts on {topic}.",
                    }
                ],
            },
        ]
    )
    assert prompt.format(topic="airplanes") == [
        {"role": "system", "content": "You are a pirate."},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Tell us your thoughts on airplanes.",
                }
            ],
        },
    ]


def test_provider_detection_from_model():
    """Test that we can infer provider from model name."""
    assert infer_provider_from_model("gpt-4") == PROVIDER_OPENAI
    assert infer_provider_from_model("gpt-3.5-turbo") == PROVIDER_OPENAI
    assert infer_provider_from_model("claude-3-sonnet") == "anthropic"
    assert infer_provider_from_model("Claude-3-5-Sonnet") == "anthropic"
    assert infer_provider_from_model("gemini-pro") == "google"
    assert infer_provider_from_model("amazon.titan-text-express-v1") == PROVIDER_BEDROCK
    assert infer_provider_from_model("amazon.nova-lite-v1:0") == PROVIDER_BEDROCK
    assert infer_provider_from_model("unknown-model") == PROVIDER_OPENAI  # default


def test_provider_detection_from_content():
    """Test that we can infer provider from content structure."""
    # OpenAI format (string content)
    assert infer_provider_from_content("hello") == PROVIDER_OPENAI
    
    # Bedrock format (list with text dict)
    assert infer_provider_from_content([{"text": "hello"}]) == PROVIDER_BEDROCK
    
    # OpenAI multimodal format
    assert infer_provider_from_content([{"type": "text", "text": "hello"}]) == PROVIDER_OPENAI
    
    # Empty or None
    assert infer_provider_from_content([]) == PROVIDER_OPENAI
    assert infer_provider_from_content(None) == PROVIDER_OPENAI


def test_messagesprompt_format_for_bedrock():
    """Test explicit Bedrock formatting."""
    prompt = MessagesPrompt(
        [
            {"role": "system", "content": "You are a pirate."},
            {"role": "user", "content": "Tell me about {topic}."},
        ]
    )
    
    result = prompt.format_for_provider(PROVIDER_BEDROCK, topic="ships")
    assert result == [
        {"role": "system", "content": [{"text": "You are a pirate."}]},
        {"role": "user", "content": [{"text": "Tell me about ships."}]},
    ]


def test_messagesprompt_format_autodetect_openai():
    """Test that format() auto-detects OpenAI format correctly."""
    prompt = MessagesPrompt(
        [
            {"role": "user", "content": "hello"},
        ]
    )
    
    # Should default to OpenAI format
    result = prompt.format()
    assert result == [{"role": "user", "content": "hello"}]


def test_messagesprompt_format_autodetect_bedrock():
    """Test that format() auto-detects Bedrock format correctly."""
    prompt = MessagesPrompt(
        [
            {"role": "user", "content": [{"text": "hello"}]},
        ]
    )
    
    # Should detect Bedrock format from content structure
    result = prompt.format()
    assert result == [{"role": "user", "content": [{"text": "hello"}]}]


def test_easyprompt_format_for_provider():
    """Test EasyPrompt provider formatting."""
    prompt = EasyPrompt(
        [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "What is {question}?"},
        ]
    )
    
    # Test OpenAI format
    openai_result = prompt.format_for_provider(PROVIDER_OPENAI, question="2+2")
    assert openai_result == [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "What is 2+2?"},
    ]
    
    # Test Bedrock format
    bedrock_result = prompt.format_for_provider(PROVIDER_BEDROCK, question="2+2")
    assert bedrock_result == [
        {"role": "system", "content": [{"text": "You are helpful"}]},
        {"role": "user", "content": [{"text": "What is 2+2?"}]},
    ]


def test_easyprompt_format_with_config():
    """Test that EasyPrompt uses config for provider detection."""
    prompt = EasyPrompt(
        [{"role": "user", "content": "hello"}],
        config={"provider": PROVIDER_BEDROCK}
    )
    
    result = prompt.format()
    assert result == [{"role": "user", "content": [{"text": "hello"}]}]
    
    # Test with model-based detection
    prompt2 = EasyPrompt(
        [{"role": "user", "content": "hello"}],
        config={"model": "claude-3-sonnet"}
    )
    
    # Should detect Anthropic, which uses OpenAI format
    result2 = prompt2.format()
    assert result2 == [{"role": "user", "content": "hello"}]


def test_convert_openai_to_bedrock():
    """Test conversion from OpenAI to Bedrock format."""
    openai_messages = [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    
    bedrock_messages = convert_openai_to_bedrock(openai_messages)
    assert bedrock_messages == [
        {"role": "system", "content": [{"text": "You are helpful"}]},
        {"role": "user", "content": [{"text": "Hello"}]},
        {"role": "assistant", "content": [{"text": "Hi there!"}]},
    ]


def test_convert_bedrock_to_openai():
    """Test conversion from Bedrock to OpenAI format."""
    bedrock_messages = [
        {"role": "system", "content": [{"text": "You are helpful"}]},
        {"role": "user", "content": [{"text": "Hello"}]},
        {"role": "assistant", "content": [{"text": "Hi there!"}]},
    ]
    
    openai_messages = convert_bedrock_to_openai(bedrock_messages)
    assert openai_messages == [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]


def test_convert_preserves_multimodal():
    """Test that conversion preserves multimodal content."""
    # OpenAI multimodal format
    openai_multimodal = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
            ]
        }
    ]
    
    # Converting to bedrock should preserve complex content
    bedrock = convert_openai_to_bedrock(openai_multimodal)
    assert bedrock[0]["content"] == openai_multimodal[0]["content"]
    
    # Converting back should also preserve it
    back_to_openai = convert_bedrock_to_openai(bedrock)
    assert back_to_openai == openai_multimodal


def test_validate_bedrock_format():
    """Test Bedrock format validation."""
    # Valid Bedrock format
    valid = [
        {"role": "user", "content": [{"text": "hello"}]},
        {"role": "assistant", "content": [{"text": "hi"}]},
    ]
    assert validate_bedrock_format(valid) == True
    
    # Invalid - content is string not list
    invalid1 = [
        {"role": "user", "content": "hello"},
    ]
    assert validate_bedrock_format(invalid1) == False
    
    # Invalid - content list items don't have required keys
    invalid2 = [
        {"role": "user", "content": [{"foo": "bar"}]},
    ]
    assert validate_bedrock_format(invalid2) == False
    
    # Invalid - missing role
    invalid3 = [
        {"content": [{"text": "hello"}]},
    ]
    assert validate_bedrock_format(invalid3) == False
    
    # Valid - with toolUse
    valid_tool = [
        {"role": "assistant", "content": [{"toolUse": {"name": "tool", "input": {}}}]},
    ]
    assert validate_bedrock_format(valid_tool) == True
