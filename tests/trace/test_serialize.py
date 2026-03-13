from __future__ import annotations

from dataclasses import dataclass

import openai
import pytest
from pydantic import BaseModel

import weave
from weave.shared.digest import bytes_digest
from weave.trace.object_record import pydantic_object_record
from weave.trace.refs import ObjectRef, TableRef
from weave.trace.serialization.op_type import _replace_memory_address
from weave.trace.serialization.serialize import (
    _convert_ext_ref_string,
    _to_json_fast,
    _to_json_slow,
    dictify,
    fallback_encode,
    is_pydantic_model_class,
    to_json,
)
from weave.trace_server.trace_server_interface import FileCreateReq


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


# ---------------------------------------------------------------------------
# _convert_ext_ref_string
# ---------------------------------------------------------------------------


class TestConvertExtRefString:
    """Unit tests for _convert_ext_ref_string."""

    def test_same_project_converted(self) -> None:
        result = _convert_ext_ref_string(
            "weave:///entity/project/obj/foo:abc123",
            project_id="entity/project",
            internal_project_id="int-uuid-1",
        )
        assert result == "weave-trace-internal:///int-uuid-1/obj/foo:abc123"

    def test_cross_project_no_client_falls_back(self) -> None:
        result = _convert_ext_ref_string(
            "weave:///other-entity/other-project/obj/bar:def456",
            project_id="entity/project",
            internal_project_id="int-uuid-1",
            client=None,
        )
        assert result == "weave:///other-entity/other-project/obj/bar:def456"

    def test_cross_project_with_resolver(self) -> None:
        class FakeClient:
            def _resolve_ext_to_int_project_id(self, ext_pid: str) -> str | None:
                return {"other/proj": "int-uuid-2"}.get(ext_pid)

        result = _convert_ext_ref_string(
            "weave:///other/proj/obj/x:111",
            project_id="entity/project",
            internal_project_id="int-uuid-1",
            client=FakeClient(),  # type: ignore[arg-type]
        )
        assert result == "weave-trace-internal:///int-uuid-2/obj/x:111"

    def test_cross_project_unresolvable_falls_back(self) -> None:
        class FakeClient:
            def _resolve_ext_to_int_project_id(self, ext_pid: str) -> str | None:
                return None

        result = _convert_ext_ref_string(
            "weave:///unknown/proj/obj/x:111",
            project_id="entity/project",
            internal_project_id="int-uuid-1",
            client=FakeClient(),  # type: ignore[arg-type]
        )
        assert result == "weave:///unknown/proj/obj/x:111"

    def test_non_weave_uri_unchanged(self) -> None:
        result = _convert_ext_ref_string(
            "https://example.com/foo",
            project_id="entity/project",
            internal_project_id="int-uuid-1",
        )
        assert result == "https://example.com/foo"

    def test_malformed_uri_raises(self) -> None:
        with pytest.raises(ValueError, match="Malformed ref URI"):
            _convert_ext_ref_string(
                "weave:///only-one-segment",
                project_id="entity/project",
                internal_project_id="int-uuid-1",
            )


# ---------------------------------------------------------------------------
# _to_json_slow vs _to_json_fast ref handling
# ---------------------------------------------------------------------------


class _StubClient:
    """Minimal stub satisfying the client interface used by to_json."""

    def __init__(self) -> None:
        self.file_create_reqs: list[FileCreateReq] = []

    def _send_file_create(self, req: FileCreateReq) -> None:
        self.file_create_reqs.append(req)

    def _resolve_ext_to_int_project_id(self, ext_pid: str) -> str | None:
        return None


class TestSlowPathRefs:
    """Slow path should emit external weave:/// URIs unchanged."""

    def test_object_ref(self) -> None:
        ref = ObjectRef("myentity", "myproject", "thing", "abc123")
        client = _StubClient()
        result = _to_json_slow(ref, "myentity/myproject", client)  # type: ignore[arg-type]
        assert result == "weave:///myentity/myproject/object/thing:abc123"

    def test_table_ref(self) -> None:
        ref = TableRef("myentity", "myproject", "tab999")
        client = _StubClient()
        result = _to_json_slow(ref, "myentity/myproject", client)  # type: ignore[arg-type]
        assert result == "weave:///myentity/myproject/table/tab999"

    def test_embedded_ref_string_unchanged(self) -> None:
        obj = {"key": "weave:///myentity/myproject/object/x:abc"}
        client = _StubClient()
        result = _to_json_slow(obj, "myentity/myproject", client)  # type: ignore[arg-type]
        assert result["key"] == "weave:///myentity/myproject/object/x:abc"


class TestFastPathRefs:
    """Fast path should convert weave:/// URIs to weave-trace-internal:///."""

    def test_object_ref(self) -> None:
        ref = ObjectRef("myentity", "myproject", "thing", "abc123")
        client = _StubClient()
        result = _to_json_fast(
            ref, "myentity/myproject", client,  # type: ignore[arg-type]
            internal_project_id="int-uuid",
        )
        assert result == "weave-trace-internal:///int-uuid/object/thing:abc123"

    def test_table_ref(self) -> None:
        ref = TableRef("myentity", "myproject", "tab999")
        client = _StubClient()
        result = _to_json_fast(
            ref, "myentity/myproject", client,  # type: ignore[arg-type]
            internal_project_id="int-uuid",
        )
        assert result == "weave-trace-internal:///int-uuid/table/tab999"

    def test_embedded_ref_string_converted(self) -> None:
        obj = {"key": "weave:///myentity/myproject/object/x:abc"}
        client = _StubClient()
        result = _to_json_fast(
            obj, "myentity/myproject", client,  # type: ignore[arg-type]
            internal_project_id="int-uuid",
        )
        assert result["key"] == "weave-trace-internal:///int-uuid/object/x:abc"

    def test_nested_refs_converted(self) -> None:
        ref_inner = ObjectRef("myentity", "myproject", "inner", "aaa")
        ref_outer = ObjectRef("myentity", "myproject", "outer", "bbb")
        obj = [ref_inner, {"nested": ref_outer}]
        client = _StubClient()
        result = _to_json_fast(
            obj, "myentity/myproject", client,  # type: ignore[arg-type]
            internal_project_id="int-uuid",
        )
        assert result[0] == "weave-trace-internal:///int-uuid/object/inner:aaa"
        assert result[1]["nested"] == "weave-trace-internal:///int-uuid/object/outer:bbb"

    def test_cross_project_ref_falls_back(self) -> None:
        ref = ObjectRef("other", "proj", "thing", "abc123")
        client = _StubClient()
        result = _to_json_fast(
            ref, "myentity/myproject", client,  # type: ignore[arg-type]
            internal_project_id="int-uuid",
        )
        # Can't resolve cross-project, should fall back to external URI
        assert result == "weave:///other/proj/object/thing:abc123"

    def test_non_ref_strings_unchanged(self) -> None:
        obj = {"name": "hello", "count": 42, "flag": True}
        client = _StubClient()
        result = _to_json_fast(
            obj, "myentity/myproject", client,  # type: ignore[arg-type]
            internal_project_id="int-uuid",
        )
        assert result == {"name": "hello", "count": 42, "flag": True}


# ---------------------------------------------------------------------------
# _build_result_from_encoded: expected_digest on file uploads
# ---------------------------------------------------------------------------


class TestFileUploadExpectedDigest:
    """Slow path should NOT set expected_digest; fast path should."""

    def _make_custom_obj_with_file(self) -> object:
        """Return an object whose encode_custom_obj produces a file entry."""

        class _HasFile:
            pass

        return _HasFile()

    def test_slow_path_no_expected_digest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _StubClient()
        monkeypatch.setattr(
            "weave.trace.serialization.custom_objs.encode_custom_obj",
            lambda obj: {
                "_type": "CustomWeaveType",
                "weave_type": {"type": "dummy"},
                "files": {"blob.bin": b"hello"},
            },
        )
        _to_json_slow(object(), "entity/project", client)  # type: ignore[arg-type]

        assert len(client.file_create_reqs) == 1
        assert client.file_create_reqs[0].expected_digest is None

    def test_fast_path_includes_expected_digest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _StubClient()
        expected = bytes_digest(b"hello")
        monkeypatch.setattr(
            "weave.trace.serialization.custom_objs.encode_custom_obj",
            lambda obj: {
                "_type": "CustomWeaveType",
                "weave_type": {"type": "dummy"},
                "files": {"blob.bin": b"hello"},
            },
        )
        _to_json_fast(
            object(), "entity/project", client,  # type: ignore[arg-type]
            internal_project_id="int-uuid",
        )

        assert len(client.file_create_reqs) == 1
        assert client.file_create_reqs[0].expected_digest == expected
