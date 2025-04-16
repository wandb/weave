from pydantic import BaseModel

from weave.trace.serialization.serialize import (
    dictify,
    fallback_encode,
    is_pydantic_model_class,
    to_json,
)


def test_dictify_simple() -> None:
    class Point:
        x: int
        y: int

        # This should be ignored
        def sum() -> int:
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
    class Point:
        x: int
        y: int

        def __init__(self, x: int, y: int) -> None:
            self.x = x
            self.y = y

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
    class MyClass:
        api_key: str

        def __init__(self, secret: str) -> None:
            self.api_key = secret

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
    class MyClassA:
        api_key: str

        def __init__(self, secret: str) -> None:
            self.api_key = secret

    class MyClassB:
        a: MyClassA

        def __init__(self, a: MyClassA) -> None:
            self.a = a

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
    Notably it should return False for instances of Pydantic model classes."""
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


def test_serialize_of_query_object(client) -> None:
    import weave
    from weave.trace_server.interface.query import Query
    from weave.trace_server.trace_server_interface import RefsReadBatchReq

    query_raw = {
        "$expr": {
            "$gt": [
                {"$getField": "completion_token_cost"},
                {"$literal": 25},
            ],
        }
    }
    query = Query(**query_raw)
    ref = weave.publish(query)
    res = client.server.refs_read_batch(RefsReadBatchReq(refs=[ref.uri()]))
    query_2 = Query.model_validate(res.vals[0])
    assert query_2 == query


import weave
from weave.trace.objectify import register_object


def test_nested_pydantic_class(client) -> None:
    class Inner(BaseModel):
        name: str

    @register_object
    class Outer(BaseModel):
        inner: Inner

        @classmethod
        def from_obj(cls, obj):
            return cls.model_validate(obj.unwrap(), from_attributes=True)

    outer = Outer(inner=Inner(name="test"))
    outer_ref = weave.publish(outer)
    outer_gotten = outer_ref.get()
    assert isinstance(outer_gotten, Outer)
    assert isinstance(outer_gotten.inner, Inner)
    assert outer_gotten.inner.name == "test"
