import pytest

from weave import Prompt
from weave.flow.prompt import MessageParts, Placeholder


def test_prompt_one_message_no_placeholders():
    prompt = Prompt(name="test")
    prompt.append("Hello, world!")
    assert prompt() == [{"role": "user", "content": "Hello, world!"}]


def test_prompt_two_messages_no_placeholders():
    prompt = Prompt(name="test")
    prompt.append("You are a helpful assistant.", role="system")
    prompt.append("What's the capital of Brazil?")
    assert len(prompt) == 2
    assert prompt() == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the capital of Brazil?"},
    ]


def test_prompt_two_messages_placeholder_missing():
    prompt = Prompt(name="test")
    prompt.append("You are a helpful assistant.", role="system")
    prompt.append("What's the capital of {country}?")
    with pytest.raises(ValueError):  # Missing params
        messages = prompt()


def test_prompt_two_messages_placeholder_default():
    prompt = Prompt(name="test")
    prompt.append("You are a helpful assistant.", role="system")
    prompt.append("What's the capital of {country default:Brazil}?")
    assert prompt() == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the capital of Brazil?"},
    ]


def test_prompt_two_messages_placeholder():
    prompt = Prompt(name="test")
    prompt.append("You are a helpful assistant.", role="system")
    prompt.append("What's the capital of {country}?")
    assert prompt(country="Brazil") == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the capital of Brazil?"},
    ]
    assert prompt({"country": "Brazil"}) == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the capital of Brazil?"},
    ]


def test_prompt_image_content():
    prompt = Prompt(name="image_content")
    (
        prompt.append_message()
        .add_text("What's in this image?")
        .add_image_url(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
        )
    )
    assert prompt() == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
                    },
                },
            ],
        },
    ]


def test_message_parts_from_empty_str():
    s = ""
    parts = MessageParts.from_str(s)
    assert len(parts.parts) == 0


def test_message_parts_from_str_no_placeholders():
    s = "Hello, world!"
    parts = MessageParts.from_str(s)
    assert len(parts.parts) == 1
    assert parts.parts[0] == "Hello, world!"


def test_message_parts_from_str_with_placeholders():
    s = "Hello, {name}! You are {age} years old."
    parts = MessageParts.from_str(s)
    assert len(parts.parts) == 5
    assert parts.parts[0] == "Hello, "
    assert isinstance(parts.parts[1], Placeholder)
    assert parts.parts[1].name == "name"
    assert parts.parts[2] == "! You are "
    assert isinstance(parts.parts[3], Placeholder)
    assert parts.parts[3].name == "age"
    assert parts.parts[4] == " years old."


def test_message_parts_from_str_with_typed_placeholders():
    s = "Hello, {name type:string}! You are {age type:integer min:0 max:150} years old."
    parts = MessageParts.from_str(s)
    assert len(parts.parts) == 5
    assert parts.parts[0] == "Hello, "
    assert isinstance(parts.parts[1], Placeholder)
    assert parts.parts[1].name == "name"
    assert parts.parts[1].type == "string"
    assert parts.parts[2] == "! You are "
    assert isinstance(parts.parts[3], Placeholder)
    assert parts.parts[3].name == "age"
    assert parts.parts[3].type == "integer"
    assert parts.parts[4] == " years old."


def test_message_parts_from_str_with_default_values():
    s = "Hello, {name default:World}! The answer is {answer default:42}."
    parts = MessageParts.from_str(s)
    assert len(parts.parts) == 5
    assert parts.parts[0] == "Hello, "
    assert isinstance(parts.parts[1], Placeholder)
    assert parts.parts[1].name == "name"
    assert parts.parts[1].default == "World"
    assert parts.parts[2] == "! The answer is "
    assert isinstance(parts.parts[3], Placeholder)
    assert parts.parts[3].name == "answer"
    assert parts.parts[3].default == "42"
    assert parts.parts[4] == "."


def test_message_parts_from_str_with_escaped_placeholders():
    s = r"Hello, \{name\}! This is not a \{placeholder\}."
    parts = MessageParts.from_str(s)
    assert len(parts.parts) == 1
    assert parts.parts[0] == r"Hello, {name}! This is not a {placeholder}."


def test_message_parts_placeholders():
    s = "Hello, {name}! You are {age} years old. Your favorite color is {color default:blue}."
    parts = MessageParts.from_str(s)

    placeholders = parts.placeholders()

    assert len(placeholders) == 3
    assert all(isinstance(p, Placeholder) for p in placeholders)

    assert placeholders[0].name == "name"
    assert placeholders[0].type == "string"
    assert placeholders[0].default is None

    assert placeholders[1].name == "age"
    assert placeholders[1].type == "string"
    assert placeholders[1].default is None

    assert placeholders[2].name == "color"
    assert placeholders[2].type == "string"
    assert placeholders[2].default == "blue"


def test_placeholder_equality():
    p1 = Placeholder(name="test", type="string", default="default")
    p2 = Placeholder(name="test", type="string", default="default")
    p3 = Placeholder(name="test", type="string", default="different")
    p4 = Placeholder(name="different", type="string", default="default")

    assert p1 == p2
    assert p1 != p3
    assert p1 != p4
    assert p1 != "not a placeholder"

    # Test that placeholders can be used as dictionary keys
    d = {p1: "value"}
    assert d[p2] == "value"
    assert p3 not in d
    assert p4 not in d
