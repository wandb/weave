import io
import itertools
from typing import Any, Iterable, Literal, Optional, Union

import pytest

from weave import Prompt


def iter_equal(items1, items2):
  '''`True` if iterators `items1` and `items2` contain equal items.'''
  return (items1 is items2) or \
          all(a == b for a, b in itertools.zip_longest(items1, items2, fillvalue=object()))



def test_prompt_message_constructor_str():
    prompt = Prompt("What's 23 * 42")
    assert prompt() == [{"role": "user", "content": "What's 23 * 42"}]

def test_prompt_message_constructor_prefix_str():
    prompt = Prompt("system: you are a pirate")
    assert prompt() == [{"role": "system", "content": "you are a pirate"}]

def test_prompt_message_constructor_role_arg():
    prompt = Prompt("You're a calculator.", role="system")
    assert prompt() == [{"role": "system", "content": "You're a calculator."}]

def test_prompt_message_constructor_array():
    prompt = Prompt([
        {"role": "system", "content": "You're a calculator."},
        {"role": "user", "content": "What's 23 * 42"}
    ])
    assert prompt() == [
        {"role": "system", "content": "You're a calculator."},
        {"role": "user", "content": "What's 23 * 42"},
    ]

def test_prompt_message_constructor_obj():
    prompt = Prompt(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only."
            },
            {
                "role": "user",
                "content": "Artificial intelligence is a technology with great promise."
            }
        ],
        temperature=0.8,
        max_tokens=64,
        top_p=1
    )
    assert prompt() == [
        {
            "role": "system",
            "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only."
        },
        {
            "role": "user",
            "content": "Artificial intelligence is a technology with great promise."
        }
    ]
    assert prompt.config == {
        "model": "gpt-4o",
        "temperature": 0.8,
        "max_tokens": 64,
        "top_p": 1,
    }

def test_prompt_append() -> None:
    prompt = Prompt()
    prompt.append("You are a helpful assistant.", role="system")
    prompt.append("system: who knows a lot about geography")
    prompt.append("""
        What's the capital of Brazil?
    """, dedent=True)
    assert prompt() == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "system", "content": "who knows a lot about geography"},
        {"role": "user", "content": "What's the capital of Brazil?"},
    ]

def test_prompt_append_with_role() -> None:
    prompt = Prompt()
    prompt.append("system: who knows a lot about geography", role="asdf")
    assert prompt() == [
        {"role": "asdf", "content": "system: who knows a lot about geography"},
    ]

def test_prompt_unbound_iteration() -> None:
    """We don't error - is that the right behavior?"""
    prompt = Prompt("Tell me about {x}, {y}, and {z}. Especially {z}.")
    prompt.bind(y="strawberry")
    assert prompt.placeholders == ["x", "y", "z"]
    assert not prompt.is_bound
    assert prompt.unbound_placeholders == ["x", "z"]
    assert list(prompt()) == [{"role": "user", "content": "Tell me about {x}, strawberry, and {z}. Especially {z}."}]
    prompt.bind(x="vanilla", z="chocolate")
    assert prompt.is_bound
    assert prompt.unbound_placeholders == []
    assert list(prompt()) == [{"role": "user", "content": "Tell me about vanilla, strawberry, and chocolate. Especially chocolate."}]


def test_prompt_format_specifiers() -> None:
    prompt = Prompt("{x:.5}")
    assert prompt.placeholders == ["x"]
    assert prompt(x=3.14159)[0]["content"] == "3.1416"



def test_prompt_parameter_default() -> None:
    prompt = Prompt("{A} * {B}")
    prompt.require("A", default=23)
    prompt.require("B", default=42)
    assert list(prompt()) == [{"role": "user", "content": "23 * 42"}]

def test_prompt_parameter_validation_int() -> None:
    prompt = Prompt("{A} + {B}")
    prompt.require("A", min=10, max=100)
    with pytest.raises(ValueError) as e:
        prompt.bind(A=0)
    assert str(e.value) == "A (0) is less than min (10)"


def test_prompt_parameter_validation_oneof() -> None:
    prompt = Prompt("{flavor}")
    prompt.require("flavor", oneof=('vanilla', 'strawberry', 'chocolate'))
    with pytest.raises(ValueError) as e:
        prompt.bind(flavor='mint chip')
    assert str(e.value) == "flavor (mint chip) must be one of vanilla, strawberry, chocolate"


def test_prompt_bind_iteration() -> None:
    """Iterating over a prompt should return messages with placeholders filled in."""
    prompt = Prompt(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only."
            },
            {
                "role": "user",
                "content": "{sentence}"
            }
        ],
        temperature=0.8,
        max_tokens=64,
        top_p=1
    ).bind(sentence="Artificial intelligence is a technology with great promise.")
    desired = [
        {
            "role": "system",
            "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only."
        },
        {
            "role": "user",
            "content": "Artificial intelligence is a technology with great promise."
        }
    ]
    assert iter_equal(prompt, iter(desired))


def test_prompt_dict_unpacking() -> None:
    params = dict(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You will be provided with text, and your task is to translate it into emojis. Do not use any regular text. Do your best with emojis only."
            },
            {
                "role": "user",
                "content": "{sentence}"
            }
        ],
        temperature=0.8,
        max_tokens=64,
        top_p=1,
    )
    prompt = Prompt(**params)
    def check(**kwargs):
        assert kwargs == params
    check(**prompt)


    # def test_prompt_requirements() -> None:
    #     prompt = Prompt()
    #     prompt.add_requirement("x", type="string")


# def test_prompt_one_message_no_placeholders():
#     prompt = Prompt(name="test")
#     prompt.append("Hello, world!")
#     assert prompt() == [{"role": "user", "content": "Hello, world!"}]


# def test_prompt_two_messages_no_placeholders():
#     prompt = Prompt(name="test")
#     prompt.append("You are a helpful assistant.", role="system")
#     prompt.append("What's the capital of Brazil?")
#     assert len(prompt) == 2
#     assert prompt() == [
#         {"role": "system", "content": "You are a helpful assistant."},
#         {"role": "user", "content": "What's the capital of Brazil?"},
#     ]


# def test_prompt_two_messages_placeholder_missing():
#     prompt = Prompt(name="test")
#     prompt.append("You are a helpful assistant.", role="system")
#     prompt.append("What's the capital of {country}?")
#     with pytest.raises(ValueError):  # Missing params
#         messages = prompt()


# def test_prompt_two_messages_placeholder_default():
#     prompt = Prompt(name="test")
#     prompt.append("You are a helpful assistant.", role="system")
#     prompt.append("What's the capital of {country default:Brazil}?")
#     assert prompt() == [
#         {"role": "system", "content": "You are a helpful assistant."},
#         {"role": "user", "content": "What's the capital of Brazil?"},
#     ]


# def test_prompt_two_messages_placeholder():
#     prompt = Prompt(name="test")
#     prompt.append("You are a helpful assistant.", role="system")
#     prompt.append("What's the capital of {country}?")
#     assert prompt(country="Brazil") == [
#         {"role": "system", "content": "You are a helpful assistant."},
#         {"role": "user", "content": "What's the capital of Brazil?"},
#     ]
#     assert prompt({"country": "Brazil"}) == [
#         {"role": "system", "content": "You are a helpful assistant."},
#         {"role": "user", "content": "What's the capital of Brazil?"},
#     ]


# def test_prompt_append_list():
#     prompt = Prompt(name="marv")
#     prompt.append(
#         "You are Marv, a chatbot that reluctantly answers questions with sarcastic responses.",
#         role="system",
#     )
#     prompt.append("How many pounds are in a kilogram")
#     prompt.append(
#         "This again? There are 2.2 pounds in a kilogram. Please make a note of this.",
#         role="assistant",
#     )
#     prompt.append(
#         [
#             {"role": "user", "content": "What does HTML stand for?"},
#             {
#                 "role": "assistant",
#                 "content": "Was Google too busy? Hypertext Markup Language. The T is for try to ask better questions in the future.",
#             },
#             {"role": "user", "content": "When did the first airplane fly?"},
#             {
#                 "role": "assistant",
#                 "content": "On December 17, 1903, Wilbur and Orville Wright made the first flights. I wish they'd come and take me away.",
#             },
#             {"role": "user", "content": "What time is it?"},
#         ]
#     )
#     assert len(prompt()) == 8
#     assert len(prompt.messages.with_role("assistant")) == 3


# def test_prompt_image_content():
#     prompt = Prompt(name="image_content")
#     (
#         prompt.append_message()
#         .add_text("What's in this image?")
#         .add_image_url(
#             "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
#         )
#     )
#     assert prompt() == [
#         {
#             "role": "user",
#             "content": [
#                 {"type": "text", "text": "What's in this image?"},
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
#                     },
#                 },
#             ],
#         },
#     ]


# def test_prompt_dump_and_load():
#     # Create a prompt
#     prompt = Prompt(name="Test Prompt", description="A test prompt")
#     prompt.append("You are a helpful assistant.", role="system")
#     prompt.append("What's the capital of {country}?")
#     prompt.bind({"country", "Japan"})
# #    prompt.dump_file("~/test_prompt.json")

#     # Dump the prompt to a string
#     output = io.StringIO()
#     prompt.dump(output)
#     dumped_str = output.getvalue()

#     # Load the prompt from the dumped string
#     input_stream = io.StringIO(dumped_str)
#     loaded_prompt = Prompt.load(input_stream)

#     # Check if the loaded prompt matches the original
#     assert loaded_prompt.name == prompt.name
#     assert loaded_prompt.description == prompt.description
#     assert len(loaded_prompt.messages) == len(prompt.messages)

#     for original_msg, loaded_msg in zip(prompt.messages, loaded_prompt.messages):
#         assert original_msg.role == loaded_msg.role
#         assert original_msg.content.parts == loaded_msg.content.parts


# def test_prompt_role_methods():
#     from weave import Prompt as P
#     p = P().system("You're a calculator.").user("What's 23 * 42")
#     assert p() == [
#         {"role": "system", "content": "You're a calculator."},
#         {"role": "user", "content": "What's 23 * 42"},
#     ]

# def test_prompt_add():
#     from weave import Prompt as P
#     p = P("What's {A} + {B}") + "Foo {A}"
#     assert p(A=2, B=3) == [
#         {"role": "user", "content": "What's 2 + 3"},
#         {"role": "user", "content": "Foo {A}"},
#     ]
#     p = P("What's {A} + {B}") + P("Foo {A}")
#     assert p(A=2, B=3) == [
#         {"role": "user", "content": "What's 2 + 3"},
#         {"role": "user", "content": "Foo 2"},
#     ]


# def test_prompt_sys():
#     from weave import Prompt as P
#     p = P.sys("You're a calculator.")
#     p += "A TI-85 to be exact."
#     assert p() == [
#         {"role": "system", "content": "You're a calculator."},
#         {"role": "system", "content": "A TI-85 to be exact."},
#     ]

# def test_prompt_iadd():
#     from weave import Prompt as P
#     p = P("This is my system prompt.", role="system")
#     p += "This is also a system prompt."
#     assert p() == [
#         {"role": "system", "content": "This is my system prompt."},
#         {"role": "system", "content": "This is also a system prompt."},
#     ]


# def test_prompt_dedent():
#     prompt = Prompt("""
#         This
#          is
#         a
#         long
#         prompt.
#     """, dedent=True)
#     assert prompt() == [{"role": "user", "content": "This\n is\na\nlong\nprompt."}]


# def test_prompt_stringify():
#     prompt = Prompt.sys("You're a calculator.").system("A TI-85 to be exact.").user("What's 23 * 42")
#     assert prompt.as_str() == "You're a calculator. A TI-85 to be exact. What's 23 * 42"
#     assert prompt.as_str(role="system") == "You're a calculator. A TI-85 to be exact."
