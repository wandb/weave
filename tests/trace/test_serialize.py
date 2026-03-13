from dataclasses import dataclass

import openai
import pytest
from pydantic import BaseModel

import weave
from weave.shared.digest import bytes_digest
from weave.trace.object_record import pydantic_object_record
from weave.trace.refs import ObjectRef, OpRef, TableRef
from weave.trace.serialization.op_type import _replace_memory_address
from weave.trace.serialization.serialize import (
    _convert_ext_ref_string,
    dictify,
    fallback_encode,
    is_pydantic_model_class,
    to_json,
)
from weave.trace.settings import UserSettings, parse_and_apply_settings


class DummyClient:
    def __init__(self, resolved_project_ids: dict[str, str] | None = None) -> None:
        import threading

        self.resolved_project_ids = resolved_project_ids or {}
        # Mirrors WeaveClient._client_side_digests_disabled_event so that
        # _build_result_from_encoded can check the session-level disable flag.
        self._client_side_digests_disabled_event = threading.Event()

    def _resolve_ext_to_int_project_id(self, project_id: str) -> str | None:
        return self.resolved_project_ids.get(project_id)

    def _send_file_create(self, req) -> None:
        raise AssertionError(f"unexpected file upload: {req}")


class RecordingFileClient(DummyClient):
    def __init__(self) -> None:
        super().__init__()
        self.file_create_reqs = []

    def _send_file_create(self, req) -> None:
        self.file_create_reqs.append(req)


def _make_ref(kind: str) -> ObjectRef | OpRef | TableRef:
    if kind == "object":
        return ObjectRef("entity", "other", "thing", "abc123")
    if kind == "op":
        return OpRef("entity", "other", "my_op", "def456")
    if kind == "table":
        return TableRef("entity", "other", "tab123")
    raise ValueError(f"Unknown ref kind: {kind}")


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


@pytest.mark.trace_server
@pytest.mark.parametrize(
    ("enable_client_side_digests", "expected_digest_present"),
    [
        pytest.param(False, False, id="client_side_digests_off"),
        pytest.param(True, True, id="client_side_digests_on"),
    ],
)
def test_to_json_custom_obj_file_upload_expected_digest_flag(
    monkeypatch,
    enable_client_side_digests: bool,
    expected_digest_present: bool,
) -> None:
    client = RecordingFileClient()
    expected_digest = bytes_digest(b"hello")

    monkeypatch.setattr(
        "weave.trace.serialization.custom_objs.encode_custom_obj",
        lambda obj: {
            "_type": "CustomWeaveType",
            "weave_type": {"type": "dummy"},
            "files": {"blob.bin": b"hello"},
        },
    )

    parse_and_apply_settings(
        UserSettings(enable_client_side_digests=enable_client_side_digests)
    )
    try:
        serialized = to_json(object(), "entity/project", client)
    finally:
        parse_and_apply_settings(UserSettings())

    assert serialized["files"] == {"blob.bin": expected_digest}
    assert len(client.file_create_reqs) == 1

    req = client.file_create_reqs[0]
    if expected_digest_present:
        assert req.expected_digest == expected_digest
    else:
        assert req.expected_digest is None


def test_to_json_object_excludes_ref(client) -> None:
    class MyObj(weave.Object):
        @weave.op
        def predict(self, x: int) -> int:
            return x

    obj = MyObj()
    obj_rec = pydantic_object_record(obj)
    serialized = to_json(obj_rec, client._project_id(), client)
    assert "ref" not in serialized


@pytest.mark.trace_server
@pytest.mark.parametrize("kind", ["object", "op", "table"])
def test_to_json_keeps_unresolved_cross_project_refs_external(kind: str) -> None:
    client = DummyClient({"entity/current": "internal-current"})
    project_id = "entity/current"
    internal_project_id = "internal-current"
    ref = _make_ref(kind)

    # When the client cannot resolve a cross-project ref's internal ID, the
    # ref must stay in external format so the server can still convert it.
    # This keeps the fast path (digests-on) compatible with the legacy path
    # (digests-off), which sends external refs and lets the server handle them.
    assert (
        to_json(ref, project_id, client, internal_project_id=internal_project_id)
        == ref.uri()
    )
    assert (
        to_json(ref.uri(), project_id, client, internal_project_id=internal_project_id)
        == ref.uri()
    )


@pytest.mark.trace_server
def test_to_json_keeps_unresolved_nested_cross_project_refs_external() -> None:
    client = DummyClient({"entity/current": "internal-current"})
    project_id = "entity/current"
    internal_project_id = "internal-current"
    obj_ref = _make_ref("object")
    op_ref = _make_ref("op")
    table_ref = _make_ref("table")

    # The same fallback must hold recursively inside dict/list/tuple payloads.
    assert to_json(
        {
            "refs": [obj_ref, op_ref.uri()],
            "nested": {
                "op": op_ref,
                "table": table_ref,
            },
            "tuple_like": (obj_ref.uri(), table_ref, op_ref.uri()),
        },
        project_id,
        client,
        internal_project_id=internal_project_id,
    ) == {
        "refs": [obj_ref.uri(), op_ref.uri()],
        "nested": {
            "op": op_ref.uri(),
            "table": table_ref.uri(),
        },
        "tuple_like": [obj_ref.uri(), table_ref.uri(), op_ref.uri()],
    }


@pytest.mark.trace_server
@pytest.mark.parametrize(
    "bad_uri",
    [
        "weave:///only-one-segment",
        "weave:///entity",
    ],
)
def test_convert_ext_ref_string_raises_on_malformed_uri(bad_uri: str) -> None:
    """Malformed ref URIs (wrong number of path segments) must raise ValueError."""
    with pytest.raises(ValueError, match="Malformed ref URI"):
        _convert_ext_ref_string(bad_uri, "entity/project", "internal-id")


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
