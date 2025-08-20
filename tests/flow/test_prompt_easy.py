import itertools

import pytest

from weave import EasyPrompt


def iter_equal(items1, items2):
    """`True` if iterators `items1` and `items2` contain equal items."""
    return (items1 is items2) or all(
        a == b for a, b in itertools.zip_longest(items1, items2, fillvalue=object())
    )


def test_prompt_message_constructor_str():
    prompt = EasyPrompt("What's 23 * 42")
    assert prompt() == [{"role": "user", "content": "What's 23 * 42"}]


def test_prompt_message_constructor_prefix_str():
    prompt = EasyPrompt("system: you are a pirate")
    assert prompt() == [{"role": "system", "content": "you are a pirate"}]


def test_prompt_message_constructor_role_arg():
    prompt = EasyPrompt("You're a calculator.", role="system")
    assert prompt() == [{"role": "system", "content": "You're a calculator."}]


def test_prompt_message_constructor_array():
    prompt = EasyPrompt(
        [
            {"role": "system", "content": "You're a calculator."},
            {"role": "user", "content": "What's 23 * 42"},
        ]
    )
    assert prompt() == [
        {"role": "system", "content": "You're a calculator."},
        {"role": "user", "content": "What's 23 * 42"},
    ]


def test_prompt_message_constructor_obj():
    prompt = EasyPrompt(
        name="myprompt",
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only.",
            },
            {
                "role": "user",
                "content": "Artificial intelligence is a technology with great promise.",
            },
        ],
        temperature=0.8,
        max_tokens=64,
        top_p=1,
    )
    assert prompt() == [
        {
            "role": "system",
            "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only.",
        },
        {
            "role": "user",
            "content": "Artificial intelligence is a technology with great promise.",
        },
    ]
    assert prompt.config == {
        "model": "gpt-4o",
        "temperature": 0.8,
        "max_tokens": 64,
        "top_p": 1,
    }


def test_prompt_append() -> None:
    prompt = EasyPrompt()
    prompt.append("You are a helpful assistant.", role="system")
    prompt.append("system: who knows a lot about geography")
    prompt.append(
        """
        What's the capital of Brazil?
    """,
        dedent=True,
    )
    assert prompt() == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "system", "content": "who knows a lot about geography"},
        {"role": "user", "content": "What's the capital of Brazil?"},
    ]


def test_prompt_append_with_role() -> None:
    prompt = EasyPrompt()
    prompt.append("system: who knows a lot about geography", role="asdf")
    assert prompt() == [
        {"role": "asdf", "content": "system: who knows a lot about geography"},
    ]


def test_prompt_unbound_iteration() -> None:
    """We don't error - is that the right behavior?"""
    prompt = EasyPrompt("Tell me about {x}, {y}, and {z}. Especially {z}.")
    prompt.bind(y="strawberry")
    assert prompt.placeholders == ["x", "y", "z"]
    assert not prompt.is_bound
    assert prompt.unbound_placeholders == ["x", "z"]
    assert list(prompt()) == [
        {
            "role": "user",
            "content": "Tell me about {x}, strawberry, and {z}. Especially {z}.",
        }
    ]
    prompt.bind(x="vanilla", z="chocolate")
    assert prompt.is_bound
    assert prompt.unbound_placeholders == []
    assert list(prompt()) == [
        {
            "role": "user",
            "content": "Tell me about vanilla, strawberry, and chocolate. Especially chocolate.",
        }
    ]


def test_prompt_format_specifiers() -> None:
    prompt = EasyPrompt("{x:.5}")
    assert prompt.placeholders == ["x"]
    assert prompt(x=3.14159)[0]["content"] == "3.1416"


def test_prompt_parameter_default() -> None:
    prompt = EasyPrompt("{A} * {B}")
    prompt.require("A", default=23)
    prompt.require("B", default=42)
    assert list(prompt()) == [{"role": "user", "content": "23 * 42"}]


def test_prompt_parameter_validation_int() -> None:
    prompt = EasyPrompt("{A} + {B}")
    prompt.require("A", min=10, max=100)
    with pytest.raises(ValueError) as e:
        prompt.bind(A=0)
    assert str(e.value) == "A (0) is less than min (10)"


def test_prompt_parameter_validation_oneof() -> None:
    prompt = EasyPrompt("{flavor}")
    prompt.require("flavor", oneof=("vanilla", "strawberry", "chocolate"))
    with pytest.raises(ValueError) as e:
        prompt.bind(flavor="mint chip")
    assert (
        str(e.value)
        == "flavor (mint chip) must be one of vanilla, strawberry, chocolate"
    )


def test_prompt_bind_iteration() -> None:
    """Iterating over a prompt should return messages with placeholders filled in."""
    prompt = EasyPrompt(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only.",
            },
            {"role": "user", "content": "{sentence}"},
        ],
        temperature=0.8,
        max_tokens=64,
        top_p=1,
    ).bind(sentence="Artificial intelligence is a technology with great promise.")
    desired = [
        {
            "role": "system",
            "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only.",
        },
        {
            "role": "user",
            "content": "Artificial intelligence is a technology with great promise.",
        },
    ]
    assert iter_equal(prompt, iter(desired))


def test_prompt_as_dict():
    prompt = EasyPrompt(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only.",
            },
            {
                "role": "user",
                "content": "Artificial intelligence is a technology with great promise.",
            },
        ],
        temperature=0.8,
        max_tokens=64,
        top_p=1,
    )
    assert prompt.as_dict() == {
        "model": "gpt-4o",
        "temperature": 0.8,
        "max_tokens": 64,
        "top_p": 1,
        "messages": [
            {
                "role": "system",
                "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only.",
            },
            {
                "role": "user",
                "content": "Artificial intelligence is a technology with great promise.",
            },
        ],
    }


def test_prompt_as_pydantic_dict():
    prompt = EasyPrompt(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only.",
            },
            {
                "role": "user",
                "content": "Artificial intelligence is a technology with great promise.",
            },
        ],
        temperature=0.8,
        max_tokens=64,
        top_p=1,
    )
    assert prompt.as_pydantic_dict() == {
        "name": None,
        "description": None,
        "ref": None,
        "config": {
            "model": "gpt-4o",
            "temperature": 0.8,
            "max_tokens": 64,
            "top_p": 1,
        },
        "data": [
            {
                "role": "system",
                "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only.",
            },
            {
                "role": "user",
                "content": "Artificial intelligence is a technology with great promise.",
            },
        ],
        "requirements": {},
    }
