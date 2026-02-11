import datetime
from dataclasses import dataclass

import openai
from pydantic import BaseModel

import weave
from weave.trace.object_record import pydantic_object_record
from weave.trace.serialization.op_type import _replace_memory_address
from weave.trace.serialization.serialize import (
    dictify,
    fallback_encode,
    from_json,
    is_pydantic_model_class,
    to_json,
)
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)


def test_dictify_simple() -> None:
    class Point:
        x: int
        y: int

        # This should be ignored
        def sum(self) -> int:
            return self.x + self.y

    pt = Point()
    pt.x = 1
    pt.y = 2
    assert dictify(pt) == {
        "__class__": {
            "module": "test_serialize",
            "qualname": "test_dictify_simple.<locals>.Point",
            "name": "Point",
        },
        "x": 1,
        "y": 2,
    }


def test_dictify_complex() -> None:
    @dataclass
    class Point:
        x: int
        y: int

    class Points:
        def __init__(self) -> None:
            self.points = [Point(1, 2), Point(3, 4)]

    pts = Points()
    assert dictify(pts) == {
        "__class__": {
            "module": "test_serialize",
            "qualname": "test_dictify_complex.<locals>.Points",
            "name": "Points",
        },
        "points": [
            {
                "__class__": {
                    "module": "test_serialize",
                    "qualname": "test_dictify_complex.<locals>.Point",
                    "name": "Point",
                },
                "x": 1,
                "y": 2,
            },
            {
                "__class__": {
                    "module": "test_serialize",
                    "qualname": "test_dictify_complex.<locals>.Point",
                    "name": "Point",
                },
                "x": 3,
                "y": 4,
            },
        ],
    }


def test_dictify_maxdepth() -> None:
    obj = {
        "a": {
            "b": {
                "c": {
                    "d": 1,
                },
            },
        },
    }
    assert dictify(obj, maxdepth=0) == obj
    assert dictify(obj, maxdepth=1) == {
        "a": "{'b': {'c': {'d': 1}}}",
    }
    assert dictify(obj, maxdepth=2) == {
        "a": {
            "b": "{'c': {'d': 1}}",
        },
    }
    assert dictify(obj, maxdepth=3) == {
        "a": {
            "b": {
                "c": "{'d': 1}",
            },
        },
    }
    assert dictify(obj, maxdepth=4) == {
        "a": {
            "b": {
                "c": {
                    "d": "1",
                }
            },
        },
    }
    assert dictify(obj, maxdepth=5) == {
        "a": {
            "b": {
                "c": {
                    "d": 1,
                }
            },
        },
    }


def test_dictify_to_dict() -> None:
    class Point:
        x: int
        y: int

        def __init__(self, x: int, y: int) -> None:
            self.x = x
            self.y = y

        def to_dict(self) -> dict:
            return {
                "foo": "bar",
                "baz": 42,
            }

    pt = Point(1, 2)
    assert dictify(pt) == {
        "foo": "bar",
        "baz": 42,
    }


def test_fallback_encode_dictify_fails() -> None:
    class Point:
        x: int
        y: int

        def __init__(self, x: int, y: int) -> None:
            self.x = x
            self.y = y

        def to_dict(self) -> dict:
            # Intentionally make dictify fail
            raise ValueError("a bug in user code")

    pt = Point(1, 2)
    assert fallback_encode(pt) == repr(pt)


def test_dictify_sanitizes() -> None:
    @dataclass
    class MyClass:
        api_key: str

    instance = MyClass("sk-1234567890qwertyuiop")
    assert dictify(instance) == {
        "__class__": {
            "module": "test_serialize",
            "qualname": "test_dictify_sanitizes.<locals>.MyClass",
            "name": "MyClass",
        },
        "api_key": "REDACTED",
    }


def test_dictify_sanitizes_nested() -> None:
    @dataclass
    class MyClassA:
        api_key: str

    @dataclass
    class MyClassB:
        a: MyClassA

    instance = MyClassB(MyClassA("sk-1234567890qwertyuiop"))
    assert dictify(instance) == {
        "__class__": {
            "module": "test_serialize",
            "qualname": "test_dictify_sanitizes_nested.<locals>.MyClassB",
            "name": "MyClassB",
        },
        "a": {
            "__class__": {
                "module": "test_serialize",
                "qualname": "test_dictify_sanitizes_nested.<locals>.MyClassA",
                "name": "MyClassA",
            },
            "api_key": "REDACTED",
        },
    }


def test_is_pydantic_model_class() -> None:
    """We expect is_pydantic_model_class to return True for Pydantic model classes, and False otherwise.
    Notably it should return False for instances of Pydantic model classes.
    """
    assert not is_pydantic_model_class(int)
    assert not is_pydantic_model_class(str)
    assert not is_pydantic_model_class(list)
    assert not is_pydantic_model_class(dict)
    assert not is_pydantic_model_class(tuple)
    assert not is_pydantic_model_class(set)
    assert not is_pydantic_model_class(None)
    assert not is_pydantic_model_class(42)
    assert not is_pydantic_model_class("foo")
    assert not is_pydantic_model_class({})
    assert not is_pydantic_model_class([])

    class CalendarEvent(BaseModel):
        name: str
        date: str
        participants: list[str]

    event = CalendarEvent(name="Test", date="2024-01-01", participants=["Alice", "Bob"])
    assert not is_pydantic_model_class(event)
    assert is_pydantic_model_class(CalendarEvent)


def test_to_json_pydantic_class(client) -> None:
    """We expect to_json to return the Pydantic schema for the class."""

    class CalendarEvent(BaseModel):
        name: str
        date: str
        participants: list[str]

    project_id = "entity/project"
    serialized = to_json(CalendarEvent, project_id, client, use_dictify=False)
    assert serialized == {
        "properties": {
            "name": {"title": "Name", "type": "string"},
            "date": {"title": "Date", "type": "string"},
            "participants": {
                "items": {"type": "string"},
                "title": "Participants",
                "type": "array",
            },
        },
        "required": ["name", "date", "participants"],
        "title": "CalendarEvent",
        "type": "object",
    }


def test_to_json_object_excludes_ref(client) -> None:
    class MyObj(weave.Object):
        @weave.op
        def predict(self, x: int) -> int:
            return x

    obj = MyObj()
    obj_rec = pydantic_object_record(obj)
    serialized = to_json(obj_rec, client._project_id(), client)
    assert "ref" not in serialized


def test_from_json_builtin_object_decodes_nested_structures(client) -> None:
    expected_dt = datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
    prompt_ref_uri = "weave:///entity/project/object/my-prompt:latest"
    # Transport payload for a nested custom object value. This is the same shape
    # a serialized datetime would have when embedded in a larger object payload.
    encoded_dt = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "datetime.datetime"},
        "val": expected_dt.isoformat(),
        "load_op": None,
    }
    # Top-level payload for a builtin object (`LLMStructuredCompletionModel`).
    # The important part is that `default_params.functions[*].deadline` is still
    # in transport form and must be decoded before model validation.
    payload = {
        "_type": "LLMStructuredCompletionModel",
        "llm_model_id": "openai/gpt-4o-mini",
        "default_params": {
            "_type": "LLMStructuredCompletionModelDefaultParams",
            "functions": [{"deadline": encoded_dt}],
            "prompt": prompt_ref_uri,
            "_class_name": "LLMStructuredCompletionModelDefaultParams",
            "_bases": ["BaseModel"],
        },
        "_class_name": "LLMStructuredCompletionModel",
        "_bases": ["Model", "Object", "BaseModel"],
    }

    deserialized = from_json(payload, client._project_id(), client.server)

    assert isinstance(deserialized, LLMStructuredCompletionModel)
    assert deserialized.default_params.functions is not None
    # Nested transport custom object is materialized into a runtime datetime.
    assert isinstance(
        deserialized.default_params.functions[0]["deadline"], datetime.datetime
    )
    assert deserialized.default_params.functions[0]["deadline"] == expected_dt
    # RefStr fields should still be strings (not coerced to Ref objects).
    assert deserialized.default_params.prompt == prompt_ref_uri


def test_to_json_function_with_memory_address_in_op(client) -> None:
    openai_client = openai.OpenAI(api_key="fake_key")

    @weave.op
    def log_me(x: int) -> int:
        myclient = openai_client
        return x

    log_me(1)
    log_me(1)

    assert len(log_me.calls()) == 2

    @weave.op
    def log_me(x: int) -> int:
        myclient = openai_client
        return x

    log_me(1)

    # same op!
    assert len(log_me.calls()) == 3

    # now make a new client
    openai_client = openai.OpenAI(api_key="fake_key")

    @weave.op
    def log_me(x: int) -> int:
        myclient = openai_client
        return x

    log_me(1)

    # this should still be the same op!
    assert len(log_me.calls()) == 4


def test__replace_memory_address() -> None:
    # Test with memory addresses of different lengths
    assert (
        _replace_memory_address("<Function object at 0x1234>")
        == "<Function object at 0x0000>"
    )
    assert _replace_memory_address("<Class at 0xdeadbeef>") == "<Class at 0x00000000>"

    # Test with multiple memory addresses
    assert (
        _replace_memory_address("<Object at 0x1234> and <Object at 0xabcd>")
        == "<Object at 0x0000> and <Object at 0x0000>"
    )
    # Test with no memory addresses
    assert _replace_memory_address("No memory address here") == "No memory address here"
