import pytest

from weave.prompt.prompt import IncorrectPromptVarError, MessagesPrompt, StringPrompt


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


def test_messagesprompt_format_missing_var_raises_error():
    """Test that missing template variables raise IncorrectPromptVarError with helpful message."""
    prompt = MessagesPrompt(
        [
            {"role": "system", "content": "You are a {role_type} assistant."},
            {"role": "user", "content": "Evaluate {output} against {expected}."},
        ]
    )

    # Only provide 'output', missing 'role_type' and 'expected'
    with pytest.raises(IncorrectPromptVarError) as exc_info:
        prompt.format(output="test")

    error_msg = str(exc_info.value)
    # Should mention one of the missing vars
    assert "role_type" in error_msg or "expected" in error_msg
    # Should show available vars
    assert "output" in error_msg


def test_messagesprompt_nesteddict_format_missing_var_raises_error():
    """Test that missing template variables in nested content raise IncorrectPromptVarError."""
    prompt = MessagesPrompt(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello {name}, please evaluate {item}."}
                ],
            },
        ]
    )

    # Only provide 'name', missing 'item'
    with pytest.raises(IncorrectPromptVarError) as exc_info:
        prompt.format(name="Alice")

    error_msg = str(exc_info.value)
    assert "item" in error_msg
    assert "name" in error_msg
