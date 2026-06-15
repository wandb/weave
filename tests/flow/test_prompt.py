import pytest

from weave.prompt.prompt import IncorrectPromptVarError, MessagesPrompt, StringPrompt


def test_stringprompt_format():
    prompt = StringPrompt("You are a pirate. Tell us your thoughts on {topic}.")
    assert (
        prompt.format(topic="airplanes")
        == "You are a pirate. Tell us your thoughts on airplanes."
    )


@pytest.mark.parametrize(
    ("messages", "expected"),
    [
        (
            [
                {"role": "system", "content": "You are a pirate."},
                {"role": "user", "content": "Tell us your thoughts on {topic}."},
            ],
            [
                {"role": "system", "content": "You are a pirate."},
                {"role": "user", "content": "Tell us your thoughts on airplanes."},
            ],
        ),
        (
            [
                {"role": "system", "content": "You are a pirate."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Tell us your thoughts on {topic}."}
                    ],
                },
            ],
            [
                {"role": "system", "content": "You are a pirate."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Tell us your thoughts on airplanes."}
                    ],
                },
            ],
        ),
    ],
)
def test_messagesprompt_format(messages, expected):
    assert MessagesPrompt(messages).format(topic="airplanes") == expected


@pytest.mark.parametrize(
    ("messages", "format_kwargs", "any_of", "all_of"),
    [
        (
            [
                {"role": "system", "content": "You are a {role_type} assistant."},
                {"role": "user", "content": "Evaluate {output} against {expected}."},
            ],
            {"output": "test"},
            ("role_type", "expected"),
            ("output",),
        ),
        (
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Hello {name}, please evaluate {item}.",
                        }
                    ],
                },
            ],
            {"name": "Alice"},
            (),
            ("item", "name"),
        ),
    ],
)
def test_messagesprompt_format_missing_var_raises_error(
    messages, format_kwargs, any_of, all_of
):
    """Missing template variables raise IncorrectPromptVarError listing missing + available vars."""
    prompt = MessagesPrompt(messages)
    with pytest.raises(IncorrectPromptVarError) as exc_info:
        prompt.format(**format_kwargs)
    error_msg = str(exc_info.value)
    if any_of:
        assert any(substring in error_msg for substring in any_of)
    for substring in all_of:
        assert substring in error_msg
