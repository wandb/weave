"""Tests for the encoder ladder in ``weave.trace.serialization.serialize``.

Each ``_encode_*`` helper is tested in isolation for two behaviors:
  1. Match: returns the correctly-shaped JSON payload for an input it owns.
  2. Miss: returns the ``_MISS`` sentinel for an input it does not own.

Separately, ``to_json`` is tested end-to-end to verify the dispatch order —
higher-priority encoders win when multiple could match — and that the terminal
``stringify`` fallback catches anything that falls through.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, NamedTuple

import pytest
from pydantic import BaseModel

from weave.flow.scorer import WeaveScorerResult
from weave.trace.object_record import ObjectRecord
from weave.trace.refs import ObjectRef, TableRef
from weave.trace.serialization.serialize import (
    _MISS,
    _encode_container,
    _encode_custom_obj,
    _encode_dictify,
    _encode_object_record,
    _encode_primitive,
    _encode_pydantic_schema,
    _encode_ref,
    _encode_try_to_dict,
    _encode_weave_scorer_result,
    to_json,
)

PROJECT_ID = "entity/project"


class _ExampleModel(BaseModel):
    """Concrete pydantic subclass. Only used to get an INSTANCE for miss
    tests — the class itself needs to live at module scope so ``_ExampleModel(x=1)``
    can appear inside a parametrize decorator (evaluated at import time).
    """

    x: int


# ---------- _encode_ref ----------


@pytest.mark.parametrize(
    "ref",
    [
        TableRef(entity="e", project="p", _digest="abc123"),
        ObjectRef(entity="e", project="p", name="obj", _digest="abc123"),
    ],
    ids=["TableRef", "ObjectRef"],
)
def test_encode_ref_returns_uri(ref: Any) -> None:
    assert _encode_ref(ref, PROJECT_ID, None, False) == ref.uri


@pytest.mark.parametrize(
    "value",
    [1, 1.5, "s", True, False, None, [1], {"a": 1}, (1, 2), object()],
)
def test_encode_ref_non_ref_returns_miss(value: Any) -> None:
    assert _encode_ref(value, PROJECT_ID, None, False) is _MISS


# ---------- _encode_object_record ----------


def test_encode_object_record_basic() -> None:
    # The encoder adds "_type" at the top then copies every attribute from
    # __dict__, which includes the raw "_class_name" as well. Both keys end
    # up in the payload; downstream code treats "_type" as authoritative.
    rec = ObjectRecord({"_class_name": "Foo", "x": 1, "y": "hi"})
    result = _encode_object_record(rec, PROJECT_ID, None, False)
    assert result == {"_type": "Foo", "_class_name": "Foo", "x": 1, "y": "hi"}


def test_encode_object_record_recurses_into_nested_values() -> None:
    rec = ObjectRecord(
        {
            "_class_name": "Foo",
            "nested_list": [1, 2, 3],
            "nested_dict": {"k": "v"},
        }
    )
    result = _encode_object_record(rec, PROJECT_ID, None, False)
    assert result == {
        "_type": "Foo",
        "_class_name": "Foo",
        "nested_list": [1, 2, 3],
        "nested_dict": {"k": "v"},
    }


def test_encode_object_record_drops_null_ref() -> None:
    rec = ObjectRecord({"_class_name": "Foo", "ref": None, "x": 1})
    result = _encode_object_record(rec, PROJECT_ID, None, False)
    assert "ref" not in result
    assert result == {"_type": "Foo", "_class_name": "Foo", "x": 1}


def test_encode_object_record_logs_on_non_null_ref(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rec = ObjectRecord(
        {
            "_class_name": "Foo",
            "ref": "weave:///e/p/object/x:abc",
            "x": 1,
        }
    )
    with caplog.at_level(logging.ERROR):
        result = _encode_object_record(rec, PROJECT_ID, None, False)
    assert "Unexpected ref" in caplog.text
    # The ref field is preserved (the current behavior is to log + keep),
    # so downstream code doesn't silently drop data.
    assert result["_type"] == "Foo"
    assert result["x"] == 1


@pytest.mark.parametrize("value", [1, "hi", None, [1], {"a": 1}, object()])
def test_encode_object_record_non_record_returns_miss(value: Any) -> None:
    assert _encode_object_record(value, PROJECT_ID, None, False) is _MISS


# ---------- _encode_container ----------


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        ([1, 2, 3], [1, 2, 3]),
        # Tuples encode as JSON arrays (lists) — JSON has no tuple concept.
        ((1, 2, 3), [1, 2, 3]),
        ({"a": 1, "b": 2}, {"a": 1, "b": 2}),
        ([], []),
        ({}, {}),
        ([{"a": [1, 2]}, {"b": (3, 4)}], [{"a": [1, 2]}, {"b": [3, 4]}]),
    ],
    ids=["list", "tuple", "dict", "empty-list", "empty-dict", "nested"],
)
def test_encode_container_match(obj: Any, expected: Any) -> None:
    assert _encode_container(obj, PROJECT_ID, None, False) == expected


def test_encode_container_namedtuple_returns_dict() -> None:
    # Namedtuples dispatch BEFORE the plain-tuple branch — result is a dict,
    # not a list. This also pins the dispatch priority.
    class Point(NamedTuple):
        x: int
        y: int

    assert _encode_container(Point(1, 2), PROJECT_ID, None, False) == {"x": 1, "y": 2}


@pytest.mark.parametrize("value", [1, 1.5, "hi", None, True, object()])
def test_encode_container_non_container_returns_miss(value: Any) -> None:
    assert _encode_container(value, PROJECT_ID, None, False) is _MISS


# ---------- _encode_pydantic_schema ----------


def test_encode_pydantic_class_returns_schema() -> None:
    class Foo(BaseModel):
        x: int
        y: str

    schema = _encode_pydantic_schema(Foo, PROJECT_ID, None, False)
    assert schema is not _MISS
    assert schema["title"] == "Foo"
    assert schema["type"] == "object"
    assert "x" in schema["properties"]
    assert "y" in schema["properties"]


@pytest.mark.parametrize(
    "value",
    [
        # Pydantic INSTANCES miss — only concrete subclasses (types) match.
        _ExampleModel(x=1),
        # BaseModel itself misses — it's the abstract base.
        BaseModel,
        # Non-pydantic types and values.
        int,
        str,
        list,
        dict,
        type(None),
        1,
        "hi",
        None,
        [1],
        {"a": 1},
    ],
)
def test_encode_pydantic_schema_returns_miss(value: Any) -> None:
    assert _encode_pydantic_schema(value, PROJECT_ID, None, False) is _MISS


# ---------- _encode_primitive ----------


@pytest.mark.parametrize(
    "value",
    [0, 1, -1, 2**31, -(2**31), 1.5, -1.5, 0.0, True, False, None, "", "hi"],
)
def test_encode_primitive_identity(value: Any) -> None:
    assert _encode_primitive(value, PROJECT_ID, None, False) == value


@pytest.mark.parametrize(
    "value",
    [[1], (1, 2), {"a": 1}, {1, 2}, object(), b"bytes"],
)
def test_encode_primitive_non_primitive_returns_miss(value: Any) -> None:
    assert _encode_primitive(value, PROJECT_ID, None, False) is _MISS


# ---------- _encode_weave_scorer_result ----------


def test_encode_weave_scorer_result_basic() -> None:
    result = WeaveScorerResult(passed=True, metadata={"score": 0.9})
    encoded = _encode_weave_scorer_result(result, PROJECT_ID, None, False)
    assert encoded == {"passed": True, "metadata": {"score": 0.9}}


def test_encode_weave_scorer_result_recurses_into_metadata() -> None:
    # Metadata values are recursively encoded via to_json — nested containers
    # should flatten through the ladder.
    result = WeaveScorerResult(
        passed=False,
        metadata={"list": [1, 2], "dict": {"a": 1}},
    )
    encoded = _encode_weave_scorer_result(result, PROJECT_ID, None, False)
    assert encoded == {
        "passed": False,
        "metadata": {"list": [1, 2], "dict": {"a": 1}},
    }


@pytest.mark.parametrize(
    "value",
    [{"passed": True, "metadata": {}}, 42, "scorer", None, object()],
)
def test_encode_weave_scorer_result_non_scorer_returns_miss(value: Any) -> None:
    assert _encode_weave_scorer_result(value, PROJECT_ID, None, False) is _MISS


# ---------- _encode_custom_obj ----------


def test_encode_custom_obj_registered_type(client: Any) -> None:
    # datetime has a built-in registered serializer; encoding produces a
    # CustomWeaveType payload with the inline value format.
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    encoded = _encode_custom_obj(dt, client.project_id, client, False)
    assert encoded is not _MISS
    assert encoded["_type"] == "CustomWeaveType"
    assert encoded["weave_type"]["type"] == "datetime.datetime"


def test_encode_custom_obj_unregistered_returns_miss() -> None:
    class Bespoke:
        pass

    # Client not needed on the miss path — no registered serializer means we
    # never reach client-touching code.
    assert _encode_custom_obj(Bespoke(), PROJECT_ID, None, False) is _MISS


# ---------- _encode_dictify ----------


def test_encode_dictify_with_flag_scans_attributes() -> None:
    # Dataclasses generate __repr__ which trips has_custom_repr — must use
    # a plain class so dictify actually runs.
    class Foo:  # noqa: B903 — plain class intentional (see comment above)
        def __init__(self, x: int, y: str) -> None:
            self.x = x
            self.y = y

    result = _encode_dictify(Foo(1, "hi"), PROJECT_ID, None, True)
    assert result is not _MISS
    assert result["x"] == 1
    assert result["y"] == "hi"
    assert "__class__" in result


def test_encode_dictify_without_flag_returns_miss() -> None:
    class Foo:  # noqa: B903 — plain class intentional
        def __init__(self, x: int) -> None:
            self.x = x

    assert _encode_dictify(Foo(1), PROJECT_ID, None, False) is _MISS


def test_encode_dictify_dataclass_returns_miss_due_to_custom_repr() -> None:
    # Dataclasses auto-generate __repr__, which opts them out of the dictify
    # fallback (assumption: the repr is the intended human form).
    @dataclass
    class Foo:
        x: int

    assert _encode_dictify(Foo(1), PROJECT_ID, None, True) is _MISS


def test_encode_dictify_logger_returns_miss() -> None:
    # Loggers are in ALWAYS_STRINGIFY — recursing attributes causes problems.
    logger = logging.getLogger("test_encoder")
    assert _encode_dictify(logger, PROJECT_ID, None, True) is _MISS


def test_encode_dictify_coroutine_returns_miss() -> None:
    async def coro() -> None:
        pass

    c = coro()
    try:
        assert _encode_dictify(c, PROJECT_ID, None, True) is _MISS
    finally:
        c.close()


def test_encode_dictify_custom_repr_returns_miss() -> None:
    # Objects with a custom __repr__ are assumed to have a sensible string
    # form; dictify would be redundant or lossy.
    class Foo:
        def __repr__(self) -> str:
            return "CustomFoo"

    assert _encode_dictify(Foo(), PROJECT_ID, None, True) is _MISS


# ---------- _encode_try_to_dict ----------


@pytest.mark.parametrize(
    "payload",
    [
        {"x": 1, "y": 2},
        # Nested values recurse back through to_json.
        {"nested": [1, 2, 3]},
    ],
)
def test_encode_try_to_dict_match(payload: dict[str, Any]) -> None:
    class Foo:
        def to_dict(self) -> dict:
            return payload

    assert _encode_try_to_dict(Foo(), PROJECT_ID, None, False) == payload


def test_encode_try_to_dict_empty_dict_returns_miss() -> None:
    # An empty dict is falsy, so the walrus assignment yields miss. This
    # matches the pre-refactor behavior and lets stringify take over.
    class Foo:
        def to_dict(self) -> dict:
            return {}

    assert _encode_try_to_dict(Foo(), PROJECT_ID, None, False) is _MISS


def test_encode_try_to_dict_no_method_returns_miss() -> None:
    class Foo:
        pass

    assert _encode_try_to_dict(Foo(), PROJECT_ID, None, False) is _MISS


# ---------- to_json dispatch order ----------


def test_to_json_ref_wins_over_generic_encoding(client: Any) -> None:
    ref = TableRef(entity="e", project="p", _digest="abc123")
    assert to_json(ref, PROJECT_ID, client) == ref.uri


def test_to_json_pydantic_class_emits_schema_not_stringified(
    client: Any,
) -> None:
    class Foo(BaseModel):
        x: int

    result = to_json(Foo, PROJECT_ID, client)
    assert isinstance(result, dict)
    assert result["title"] == "Foo"
    assert "properties" in result


def test_to_json_primitive_passes_through() -> None:
    # Primitives skip the custom-obj registry entirely — no client required.
    assert to_json(42, PROJECT_ID, None) == 42
    assert to_json(3.14, PROJECT_ID, None) == 3.14
    assert to_json("hi", PROJECT_ID, None) == "hi"
    assert to_json(True, PROJECT_ID, None) is True
    assert to_json(None, PROJECT_ID, None) is None


def test_to_json_container_recurses(client: Any) -> None:
    assert to_json([1, [2, 3]], PROJECT_ID, client) == [1, [2, 3]]
    assert to_json({"a": {"b": 1}}, PROJECT_ID, client) == {"a": {"b": 1}}
    assert to_json((1, 2, 3), PROJECT_ID, client) == [1, 2, 3]


def test_to_json_object_record_recurses_values(client: Any) -> None:
    rec = ObjectRecord(
        {
            "_class_name": "Foo",
            "nested": [1, 2, 3],
            "obj": {"a": 1},
        }
    )
    assert to_json(rec, PROJECT_ID, client) == {
        "_type": "Foo",
        "_class_name": "Foo",
        "nested": [1, 2, 3],
        "obj": {"a": 1},
    }


def test_to_json_weave_scorer_result_emits_plain_dict() -> None:
    # WeaveScorerResult round-trips as a plain dict (no CustomWeaveType
    # wrapper) — this is the wire contract the encoder preserves.
    result = WeaveScorerResult(passed=True, metadata={"score": 1.0})
    encoded = to_json(result, PROJECT_ID, None)
    assert encoded == {"passed": True, "metadata": {"score": 1.0}}


def test_to_json_custom_obj_datetime_roundtrips_via_registry(client: Any) -> None:
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    encoded = to_json(dt, client.project_id, client)
    assert isinstance(encoded, dict)
    assert encoded["_type"] == "CustomWeaveType"
    assert encoded["weave_type"]["type"] == "datetime.datetime"


def test_to_json_dictify_used_when_flag_set(client: Any) -> None:
    # Plain class (no custom __repr__) — dictify should run and return a dict.
    class Foo:  # noqa: B903 — plain class intentional
        def __init__(self, x: int) -> None:
            self.x = x

    result = to_json(Foo(1), PROJECT_ID, client, use_dictify=True)
    assert isinstance(result, dict)
    assert result["x"] == 1


def test_to_json_falls_to_stringify_without_dictify(client: Any) -> None:
    class NoHelpers:
        def __init__(self) -> None:
            self.x = 1

        def __repr__(self) -> str:
            return "NoHelpers(x=1)"

    inst = NoHelpers()
    # No to_dict, no registry match, use_dictify=False → terminal stringify.
    assert to_json(inst, PROJECT_ID, client) == "NoHelpers(x=1)"


def test_to_json_try_to_dict_used_when_to_dict_present(client: Any) -> None:
    class WithToDict:
        def to_dict(self) -> dict:
            return {"snapshot": "value"}

    assert to_json(WithToDict(), PROJECT_ID, client) == {"snapshot": "value"}


def test_to_json_deeply_nested_mixed(client: Any) -> None:
    # Sanity check that the ladder composes under recursion — each encoder's
    # recursive to_json calls must keep routing through the same priority.
    payload = {
        "primitives": [1, "s", None, True],
        "nested_dict": {"a": {"b": [1, 2, {"c": 3}]}},
        "scorer": WeaveScorerResult(passed=True, metadata={"n": 1}),
    }
    expected = {
        "primitives": [1, "s", None, True],
        "nested_dict": {"a": {"b": [1, 2, {"c": 3}]}},
        "scorer": {"passed": True, "metadata": {"n": 1}},
    }
    assert to_json(payload, PROJECT_ID, client) == expected
