from weave.flow.prompt.message import Message, MessageParts
from weave.flow.prompt.placeholder import Placeholder


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


def test_message_constructor_string():
    message = Message("Hello, world!")
    assert message.role == "user"
    assert message.content == MessageParts(["Hello, world!"])
    message = Message("Hello, world!", role="system")
    assert message.role == "system"
    assert message.content == MessageParts(["Hello, world!"])


def test_message_constructor_dict():
    message = Message({"role": "system", "content": "You are a helpful assistant."})
    assert message.role == "system"
    assert message.content == MessageParts(["You are a helpful assistant."])
