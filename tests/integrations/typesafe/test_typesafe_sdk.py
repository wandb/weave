"""TypeSafe system_one spans. HTTP is mocked; nothing here needs a trace server."""

from __future__ import annotations

import array
import asyncio
import dataclasses
import enum
import json
from collections import UserList, deque
from collections.abc import (
    Awaitable,
    Callable,
    Generator,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from datetime import datetime
from decimal import Decimal
from functools import cached_property
from importlib.metadata import version
from types import MappingProxyType
from typing import Any, NamedTuple
from unittest.mock import MagicMock
from uuid import UUID

import httpx2
import pytest
from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SerializerFunctionWrapHandler,
    computed_field,
    field_serializer,
    model_serializer,
)
from pydantic.dataclasses import dataclass as pydantic_dataclass
from typesafe_sdk import (
    AsyncTypeSafeClient,
    Image,
    Noul,
    RetryPolicy,
    TypeSafeAPIError,
    TypeSafeClient,
    TypeSafeError,
)

import weave.integrations.patch as patch_module
import weave.integrations.typesafe.typesafe_sdk as typesafe_integration
from weave.conversation import LLM, Conversation, Turn
from weave.integrations.patch import implicit_patch
from weave.integrations.typesafe.typesafe_sdk import (
    get_typesafe_patcher,
    set_capture_content,
)
from weave.trace.settings import override_settings
from weave.trace.vals import WeaveDict, WeaveList

_SECRET = "SECRET_BODY_xyz"
_EMAIL = "alice@example.com"


class OnlyModel(BaseModel):
    model: str


class _Rows(Sequence[str]):
    def __init__(self, rows: tuple[str, ...]) -> None:
        self._rows = rows

    def __getitem__(self, index: int) -> str:
        return self._rows[index]

    def __len__(self) -> int:
        return len(self._rows)


def _ok_body(**overrides: Any) -> dict[str, Any]:
    body = {
        "model": "jev-1.13.0",
        "usage": {"input_tokens": 11, "output_tokens": 4},
        "answers": {"billing": {"type": "noul", "noul": 0.91}},
    }
    body.update(overrides)
    return body


def _response(
    status: int = 200,
    body: dict[str, Any] | None = None,
    *,
    request_id: str | None = "req_123",
) -> httpx2.Response:
    headers = {}
    if request_id is not None:
        headers["x-typesafe-request-id"] = request_id
    return httpx2.Response(
        status, json=body if body is not None else _ok_body(), headers=headers
    )


def _questions() -> dict[str, Any]:
    return {"billing": Noul(instructions="Is this about billing?")}


@pytest.fixture
def otel_spans(monkeypatch: pytest.MonkeyPatch) -> Generator[InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = SDKTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(otel_trace, "_TRACER_PROVIDER", provider)
    yield exporter
    provider.shutdown()


@pytest.fixture(autouse=True)
def patch_typesafe() -> Generator[None]:
    typesafe_integration._typesafe_patcher = None
    set_capture_content(None)
    patcher = get_typesafe_patcher()
    patcher.attempt_patch()
    yield
    patcher.undo_patch()
    typesafe_integration._typesafe_patcher = None
    set_capture_content(None)
    patch_module._PATCHED_INTEGRATIONS.discard("typesafe_sdk")


@pytest.fixture(autouse=True)
def disable_capture_info() -> Generator[None]:
    with override_settings(capture_client_info=False, capture_system_info=False):
        yield


def _client(handler: Callable[[httpx2.Request], httpx2.Response]) -> TypeSafeClient:
    return TypeSafeClient(
        api_key="test-key",
        transport=httpx2.MockTransport(handler),
        retry=RetryPolicy(max_retries=0),
    )


def _async_client(
    handler: Callable[[httpx2.Request], httpx2.Response | Awaitable[httpx2.Response]],
) -> AsyncTypeSafeClient:
    return AsyncTypeSafeClient(
        api_key="test-key",
        transport=httpx2.MockTransport(handler),
        retry=RetryPolicy(max_retries=0),
    )


def _attrs(span: Any) -> dict[str, Any]:
    return dict(span.attributes) if span.attributes is not None else {}


def _by_op(spans: list[Any], op: str) -> list[Any]:
    return [span for span in spans if _attrs(span).get("gen_ai.operation.name") == op]


def _messages(span: Any, key: str) -> list[dict[str, Any]]:
    raw = _attrs(span).get(key)
    return json.loads(raw) if raw else []


def _text(span: Any) -> str:
    payload = {
        "attributes": _attrs(span),
        "events": [
            {"name": event.name, "attributes": dict(event.attributes or {})}
            for event in span.events
        ],
        "status": span.status.description,
    }
    return json.dumps(payload)


def _chat(exporter: InMemorySpanExporter) -> Any:
    chats = _by_op(exporter.get_finished_spans(), "chat")
    assert len(chats) == 1
    return chats[0]


def _letters() -> Iterator[str]:
    yield "a"
    yield "b"


def _sent(state: Any, questions: Any = None, **kwargs: Any) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.update(json.loads(request.content))
        return _response()

    _client(handler).system_one(state, questions or _questions(), **kwargs)
    return seen


class _AnyValue(BaseModel):
    value: Any


class _IterableRows(BaseModel):
    rows: Iterable[str]


class _ExtraRows(BaseModel):
    model_config = ConfigDict(extra="allow")


@dataclasses.dataclass
class _DataclassRows:
    rows: Any


@dataclasses.dataclass
class _DataclassDict(dict):
    rows: Any


@dataclasses.dataclass
class _DataclassList(list):
    rows: Any


@dataclasses.dataclass
class _DataclassSet(set):
    rows: Any


def _enum_with_an_iterator_value() -> dict[str, Any]:
    letters = enum.Enum("_Letters", {"ROWS": _letters()})
    return {"rows": letters.ROWS}


class _ComputedFromPrivate(BaseModel):
    _source: Any = PrivateAttr(default=None)

    @computed_field
    @property
    def rows(self) -> list[str]:
        return list(self._source)


def _computed_from_private() -> _ComputedFromPrivate:
    value = _ComputedFromPrivate()
    value._source = _letters()
    return value


class _FieldSerializerFromExcluded(BaseModel):
    source: Iterable[str] = Field(exclude=True)
    label: str = "rows:"

    @field_serializer("label")
    def _label(self, label: str) -> str:
        return label + ",".join(self.source)


class _ModelSerializerFromExcluded(BaseModel):
    source: Iterable[str] = Field(exclude=True)

    @model_serializer(mode="wrap")
    def _rows(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        return {**handler(self), "rows": list(self.source)}


class _CachedRows(BaseModel):
    data: list[str]

    @computed_field
    @cached_property
    def rows(self) -> Any:
        return iter(self.data)


def _cached_rows() -> _CachedRows:
    value = _CachedRows(data=["a", "b"])
    _ = value.rows
    return value


class _RowsKey(BaseModel):
    model_config = ConfigDict(frozen=True)
    source: Iterable[str] = Field(exclude=True, repr=False)

    @computed_field
    @property
    def rows(self) -> list[str]:
        return list(self.source)


class _ComputedFromExcludedKeys(BaseModel):
    source: dict[Any, int] = Field(exclude=True)

    @computed_field
    @property
    def rows(self) -> list[str]:
        return [row for key in self.source for row in key]


class _InnerSource(BaseModel):
    source: Iterable[str] = Field(exclude=True)


class _ComputedFromInnerExcluded(BaseModel):
    inner: _InnerSource

    @computed_field
    @property
    def rows(self) -> list[str]:
        return list(self.inner.source)


class _SharedSource(BaseModel):
    wrapped: _ComputedFromInnerExcluded
    plain: _InnerSource


def _shared_source() -> _SharedSource:
    inner = _InnerSource(source=["a", "b"])
    return _SharedSource(wrapped=_ComputedFromInnerExcluded(inner=inner), plain=inner)


class _CountingField:
    def __get__(self, instance: Any, owner: Any = None) -> int:
        if instance is None:
            return 0
        instance.reads += 1
        return instance.reads

    def __set__(self, instance: Any, value: int) -> None:
        instance.reads = value


@dataclasses.dataclass
class _CountedRead:
    count: int = _CountingField()


class _CountingSet(frozenset):
    def __iter__(self) -> Iterator[int]:
        self.reads = getattr(self, "reads", 0) + 1
        return iter([self.reads])


class _Cursor(Sequence[Any], Iterator[Any]):
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self._cursor = iter(rows)

    def __getitem__(self, index: int) -> Any:
        return self._rows[index]

    def __len__(self) -> int:
        return len(self._rows)

    def __iter__(self) -> _Cursor:
        return self

    def __next__(self) -> Any:
        return next(self._cursor)


class _ExcludedRows(BaseModel):
    rows: Any = Field(default=None, exclude=True)
    x: int = 1


class _PlainCachedRows(BaseModel):
    x: int = 1

    @cached_property
    def rows(self) -> Iterator[str]:
        return _letters()


def _plain_cached_rows() -> _PlainCachedRows:
    value = _PlainCachedRows()
    _ = value.rows
    return value


class _RaisingDict(dict):
    def __getitem__(self, key: Any) -> Any:
        raise AssertionError

    def __iter__(self) -> Iterator[Any]:
        raise AssertionError

    def keys(self) -> Any:
        raise AssertionError

    def values(self) -> Any:
        raise AssertionError

    def items(self) -> Any:
        raise AssertionError


class _RaisingList(list):
    def __getitem__(self, index: Any) -> Any:
        raise AssertionError

    def __iter__(self) -> Iterator[Any]:
        raise AssertionError


class _RaisingLenFrozenset(frozenset):
    def __len__(self) -> int:
        raise AssertionError


@pydantic_dataclass
class _PydanticDataclassExcluded:
    rows: Iterable[str] = Field(exclude=True)
    x: int = 1


class _PrivateValue(BaseModel):
    x: int = 1
    _value: Any = PrivateAttr(default=None)


class _PrivateValueWithComputedField(_PrivateValue):
    @computed_field
    @property
    def double(self) -> int:
        return self.x * 2


class _Pair(BaseModel):
    a: int
    b: int


class _Point(NamedTuple):
    x: int
    y: int


class _StandardContainers(BaseModel):
    rows: list[int]
    pair: tuple[int, int]
    tags: set[int]
    frozen: frozenset[int]
    queue: deque[int]
    names: dict[str, int]


@dataclasses.dataclass(slots=True)
class _SlottedRows:
    rows: list[str]


@pydantic_dataclass(slots=True)
class _SlottedComputed:
    x: int

    @computed_field
    @property
    def double(self) -> int:
        return self.x * 2


class _MappingModel(BaseModel, Mapping[str, int]):
    x: int = 1

    def __getitem__(self, key: str) -> int:
        return {"x": self.x}[key]

    def __iter__(self) -> Iterator[str]:
        return iter(["x"])

    def __len__(self) -> int:
        return 1


def _with_private(model: _PrivateValue, value: Any) -> _PrivateValue:
    model._value = value
    return model


def _self_referencing() -> _PrivateValue:
    model = _PrivateValueWithComputedField()
    model._value = model
    return model


class _LabelsAnswer(BaseModel):
    labels: Iterable[str]


class _LabelsResponse(BaseModel):
    model: str
    usage: dict[str, int]
    answers: dict[str, _LabelsAnswer]


def test_system_one_records_one_chat_span_under_a_synthetic_turn(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    result = client.system_one("I was charged twice.", _questions())

    assert result.model == "jev-1.13.0"
    spans = otel_spans.get_finished_spans()
    turns = [span for span in spans if span.name == "invoke_agent typesafe SDK"]
    assert len(turns) == 1
    chat = _chat(otel_spans)
    assert chat.name == "chat jev-latest"
    assert chat.parent is not None
    assert chat.parent.span_id == turns[0].context.span_id
    assert turns[0].parent is None

    attrs = _attrs(chat)
    assert attrs["gen_ai.provider.name"] == "typesafe"
    assert attrs["gen_ai.request.model"] == "jev-latest"
    assert attrs["gen_ai.response.model"] == "jev-1.13.0"
    assert attrs["gen_ai.response.id"] == "req_123"
    assert attrs["gen_ai.output.type"] == "json"
    assert attrs["gen_ai.usage.input_tokens"] == 11
    assert attrs["gen_ai.usage.output_tokens"] == 4
    assert "gen_ai.usage.total_tokens" not in attrs
    assert attrs["integration.name"] == "typesafe"
    assert attrs["integration.meta.package_name"] == "typesafe-sdk"
    assert attrs["integration.meta.package_version"] == version("typesafe-sdk")
    assert attrs["weave.integration.operation"] == "typesafe.system_one"
    assert "gen_ai.provider.name" not in _attrs(turns[0])

    assert _messages(chat, "gen_ai.input.messages") == [
        {
            "role": "user",
            "parts": [{"type": "text", "content": "I was charged twice."}],
        }
    ]
    output = _messages(chat, "gen_ai.output.messages")
    assert json.loads(output[0]["parts"][0]["content"]) == {
        "billing": {"noul": 0.91, "type": "noul"}
    }
    questions = json.loads(attrs["typesafe.questions"])
    assert questions == [
        {
            "id": "billing",
            "instructions": "Is this about billing?",
            "type": "noul",
        }
    ]


def test_explicit_model_and_extra_body_describe_the_effective_request(
    otel_spans: InMemorySpanExporter,
) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        return _response()

    client = _client(handler)
    client.system_one(
        {"ticket": 7},
        _questions(),
        model="jev-latest",
        extra_body={"model": "jev-preview", "state": ["replaced"]},
    )

    assert seen["body"]["model"] == "jev-preview"
    assert seen["body"]["state"] == ["replaced"]
    chat = _chat(otel_spans)
    assert _attrs(chat)["gen_ai.request.model"] == "jev-preview"
    assert chat.name == "chat jev-preview"
    content = _messages(chat, "gen_ai.input.messages")[0]["parts"][0]["content"]
    assert json.loads(content) == ["replaced"]


def test_object_state_is_a_text_part_not_a_bare_json_array(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    client.system_one(["a", "b"], _questions())
    message = _messages(_chat(otel_spans), "gen_ai.input.messages")[0]
    assert message["parts"][0] == {"type": "text", "content": '["a", "b"]'}
    assert "content" not in message


def test_sequence_state_is_recorded_on_the_chat_span(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    client.system_one(_Rows(("a", "b")), _questions())
    message = _messages(_chat(otel_spans), "gen_ai.input.messages")[0]
    assert message["parts"][0] == {"type": "text", "content": '["a", "b"]'}


def test_image_is_recorded_as_its_reference(otel_spans: InMemorySpanExporter) -> None:
    image = Image(b"\x89PNG\r\n\x1a\nimage-bytes")
    client = _client(lambda request: _response())

    client.system_one({"photo": image}, _questions())
    client.system_one(image, {"billing": Noul(instructions=image)})

    first, second = _by_op(otel_spans.get_finished_spans(), "chat")
    assert _messages(first, "gen_ai.input.messages") == [
        {
            "role": "user",
            "parts": [{"type": "text", "content": json.dumps({"photo": str(image)})}],
        }
    ]
    assert _messages(second, "gen_ai.input.messages") == [
        {"role": "user", "parts": [{"type": "text", "content": str(image)}]}
    ]
    assert json.loads(_attrs(second)["typesafe.questions"]) == [
        {"id": "billing", "instructions": str(image), "type": "noul"}
    ]


@pytest.mark.parametrize(
    "make_buffer",
    [
        pytest.param(lambda data: array.array("B", data), id="array"),
        pytest.param(bytearray, id="bytearray"),
    ],
)
def test_image_from_a_buffer_is_recorded_as_its_reference(
    otel_spans: InMemorySpanExporter, make_buffer: Callable[[bytes], Any]
) -> None:
    image = Image(make_buffer(b"\x89PNG\r\n\x1a\nimage-bytes"))
    _client(lambda request: _response()).system_one({"photo": image}, _questions())
    assert _messages(_chat(otel_spans), "gen_ai.input.messages") == [
        {
            "role": "user",
            "parts": [{"type": "text", "content": json.dumps({"photo": str(image)})}],
        }
    ]


def test_generator_state_reaches_the_sdk_unconsumed(
    otel_spans: InMemorySpanExporter,
) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["state"] = json.loads(request.content)["state"]
        return _response()

    _client(handler).system_one((row for row in ("a", "b")), _questions())

    assert seen["state"] == ["a", "b"]
    assert "gen_ai.input.messages" not in _attrs(_chat(otel_spans))


@pytest.mark.parametrize(
    ("make_state", "sent"),
    [
        pytest.param(
            lambda: _IterableRows(rows=["a", "b"]),
            {"rows": ["a", "b"]},
            id="pydantic-iterable-field",
        ),
        pytest.param(
            lambda: _ExtraRows(rows=_letters()), {"rows": ["a", "b"]}, id="extra-field"
        ),
        pytest.param(
            lambda: _DataclassRows(rows=iter(["a", "b"])),
            {"rows": ["a", "b"]},
            id="dataclass-field",
        ),
        pytest.param(
            lambda: _AnyValue(value=_DataclassDict(rows=_letters())),
            {"value": {"rows": ["a", "b"]}},
            id="dataclass-that-is-also-a-dict",
        ),
        pytest.param(
            lambda: _AnyValue(value=_DataclassList(rows=_letters())),
            {"value": {"rows": ["a", "b"]}},
            id="dataclass-that-is-also-a-list",
        ),
        pytest.param(
            lambda: _AnyValue(value=_DataclassSet(rows=_letters())),
            {"value": {"rows": ["a", "b"]}},
            id="dataclass-that-is-also-a-set",
        ),
        pytest.param(
            _enum_with_an_iterator_value, {"rows": ["a", "b"]}, id="enum-value"
        ),
        pytest.param(
            _computed_from_private,
            {"rows": ["a", "b"]},
            id="computed-field-over-private-attribute",
        ),
        pytest.param(
            lambda: _FieldSerializerFromExcluded(source=["a", "b"]),
            {"label": "rows:a,b"},
            id="field-serializer-over-excluded-field",
        ),
        pytest.param(
            lambda: _ModelSerializerFromExcluded(source=["a", "b"]),
            {"rows": ["a", "b"]},
            id="model-serializer-over-excluded-field",
        ),
        pytest.param(
            _cached_rows,
            {"data": ["a", "b"], "rows": ["a", "b"]},
            id="cached-computed-field",
        ),
        pytest.param(
            lambda: _ComputedFromExcludedKeys(source={iter(["a", "b"]): 1}),
            {"rows": ["a", "b"]},
            id="computed-field-over-excluded-dict-keys",
        ),
        pytest.param(
            lambda: _AnyValue(value={_RowsKey(source=["a", "b"]): 1}),
            {"value": {"rows=['a', 'b']": 1}},
            id="model-key-with-a-computed-field",
        ),
        pytest.param(
            _shared_source,
            {"wrapped": {"inner": {}, "rows": ["a", "b"]}, "plain": {}},
            id="inner-model-shared-with-a-computed-field",
        ),
        pytest.param(
            lambda: _AnyValue(value={"rows": _letters()}),
            {"value": {"rows": ["a", "b"]}},
            id="dict-in-a-model",
        ),
        pytest.param(
            lambda: _Cursor(["a", "b"]), ["a", "b"], id="sequence-and-iterator"
        ),
        pytest.param(_CountedRead, {"count": 1}, id="dataclass-descriptor-field"),
        pytest.param(
            lambda: _AnyValue(value=_CountingSet({0})),
            {"value": [1]},
            id="set-subclass-with-its-own-iter",
        ),
        pytest.param(
            lambda: _AnyValue(value=UserList(["a", "b"])),
            {"value": ["a", "b"]},
            id="user-container-in-a-model",
        ),
        pytest.param(
            lambda: _AnyValue(value=MappingProxyType({"rows": "a"})),
            {"value": {"rows": "a"}},
            id="user-mapping-in-a-model",
        ),
    ],
)
def test_state_that_encoding_could_change_is_sent_as_is_and_not_recorded(
    otel_spans: InMemorySpanExporter,
    make_state: Callable[[], Any],
    sent: Any,
) -> None:
    assert _sent(make_state())["state"] == sent
    attrs = _attrs(_chat(otel_spans))
    assert "gen_ai.input.messages" not in attrs
    assert json.loads(attrs["typesafe.questions"]) == [
        {"id": "billing", "instructions": "Is this about billing?", "type": "noul"}
    ]


@pytest.mark.parametrize(
    ("make_state", "sent"),
    [
        pytest.param(
            lambda: _ExcludedRows(rows=_letters()), {"x": 1}, id="excluded-iterator"
        ),
        pytest.param(_plain_cached_rows, {"x": 1}, id="plain-cached-property-iterator"),
        pytest.param(
            lambda: _PydanticDataclassExcluded(rows=["a"]),
            {"x": 1},
            id="pydantic-dataclass-excluded-iterator",
        ),
        pytest.param(
            lambda: _with_private(_PrivateValueWithComputedField(), _DataclassRows),
            {"x": 1, "double": 2},
            id="private-class",
        ),
        pytest.param(
            _self_referencing, {"x": 1, "double": 2}, id="private-self-reference"
        ),
        pytest.param(
            lambda: _with_private(_PrivateValue(), _letters()),
            {"x": 1},
            id="private-iterator-nothing-reads",
        ),
        pytest.param(
            lambda: _SlottedRows(rows=["a"]), {"rows": ["a"]}, id="slots-dataclass"
        ),
        pytest.param(
            lambda: _SlottedComputed(x=1),
            {"x": 1, "double": 2},
            id="slots-dataclass-with-a-computed-field",
        ),
        pytest.param(_MappingModel, {"x": 1}, id="model-that-is-also-a-mapping"),
        pytest.param(
            lambda: _AnyValue(value=_Point(1, 2)), {"value": [1, 2]}, id="namedtuple"
        ),
        pytest.param(
            lambda: _AnyValue(
                value={
                    "row": WeaveDict({"k": 1}, server=MagicMock()),
                    "rows": WeaveList(["a"], server=MagicMock()),
                }
            ),
            {"value": {"row": {"k": 1}, "rows": ["a"]}},
            id="weave-values-in-a-model",
        ),
        pytest.param(
            lambda: _AnyValue(
                value={
                    "row": _RaisingDict(k=1),
                    "rows": _RaisingList(["a"]),
                    "tags": _RaisingLenFrozenset({"b"}),
                }
            ),
            {"value": {"row": {"k": 1}, "rows": ["a"], "tags": ["b"]}},
            id="container-subclasses-whose-methods-raise",
        ),
        pytest.param(
            lambda: _StandardContainers(
                rows=[1],
                pair=(2, 3),
                tags={4},
                frozen=frozenset({5}),
                queue=deque([6]),
                names={"k": 7},
            ),
            {
                "rows": [1],
                "pair": [2, 3],
                "tags": [4],
                "frozen": [5],
                "queue": [6],
                "names": {"k": 7},
            },
            id="standard-containers-in-a-model",
        ),
        pytest.param(
            lambda: _Pair.model_construct(a=1), {"a": 1}, id="model-construct-unset"
        ),
    ],
)
def test_iterator_free_state_is_recorded_as_sent(
    otel_spans: InMemorySpanExporter,
    make_state: Callable[[], Any],
    sent: Any,
) -> None:
    assert _sent(make_state())["state"] == sent
    content = json.dumps(sent, sort_keys=True)
    assert _messages(_chat(otel_spans), "gen_ai.input.messages") == [
        {"role": "user", "parts": [{"type": "text", "content": content}]}
    ]


@pytest.mark.parametrize(
    ("make_request", "sent"),
    [
        pytest.param(
            lambda: {
                "questions": {
                    "billing": {
                        "type": "noul",
                        "instructions": _IterableRows(rows=["a", "b"]),
                    }
                }
            },
            {"billing": {"type": "noul", "instructions": {"rows": ["a", "b"]}}},
            id="model-in-a-question",
        ),
        pytest.param(
            lambda: {
                "extra_body": {
                    "questions": _Cursor([{"type": "noul", "instructions": "Yes?"}])
                }
            },
            [{"type": "noul", "instructions": "Yes?"}],
            id="sequence-and-iterator",
        ),
    ],
)
def test_questions_that_encoding_could_change_are_sent_as_is_and_not_recorded(
    otel_spans: InMemorySpanExporter,
    make_request: Callable[[], dict[str, Any]],
    sent: Any,
) -> None:
    assert _sent("hello", **make_request())["questions"] == sent
    chat = _chat(otel_spans)
    assert "typesafe.questions" not in _attrs(chat)
    assert _messages(chat, "gen_ai.input.messages") == [
        {"role": "user", "parts": [{"type": "text", "content": "hello"}]}
    ]


def test_response_model_iterator_stays_with_the_caller(
    otel_spans: InMemorySpanExporter,
) -> None:
    body = _ok_body(answers={"billing": {"labels": ["x", "y"]}})
    client = _client(lambda request: _response(body=body))

    result = client.system_one("hello", _questions(), response_model=_LabelsResponse)

    assert list(result.answers["billing"].labels) == ["x", "y"]
    attrs = _attrs(_chat(otel_spans))
    assert "gen_ai.output.messages" not in attrs
    assert attrs["gen_ai.usage.input_tokens"] == 11
    assert attrs["gen_ai.response.model"] == "jev-1.13.0"


def test_datetime_uuid_and_decimal_state_is_recorded_as_sent(
    otel_spans: InMemorySpanExporter,
) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["state"] = json.loads(request.content)["state"]
        return _response()

    state = {
        "amount": Decimal("1.50"),
        "id": UUID(int=1),
        "when": datetime(2026, 10, 21),
    }
    _client(handler).system_one(state, _questions())

    sent = {
        "amount": "1.50",
        "id": "00000000-0000-0000-0000-000000000001",
        "when": "2026-10-21T00:00:00",
    }
    assert seen["state"] == sent
    assert _messages(_chat(otel_spans), "gen_ai.input.messages") == [
        {"role": "user", "parts": [{"type": "text", "content": json.dumps(sent)}]}
    ]


def test_unencodable_state_does_not_open_a_turn(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    with pytest.raises(TypeSafeError) as caught:
        client.system_one(object(), _questions())
    assert str(caught.value) == "The request body could not be encoded as JSON"
    assert otel_spans.get_finished_spans() == ()


def test_content_off_omits_state_questions_and_answers(
    otel_spans: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false")
    client = _client(lambda request: _response())
    client.system_one(f"mail {_EMAIL}", _questions())
    attrs = _attrs(_chat(otel_spans))
    assert "gen_ai.input.messages" not in attrs
    assert "gen_ai.output.messages" not in attrs
    assert "typesafe.questions" not in attrs
    assert attrs["gen_ai.request.model"] == "jev-latest"
    assert attrs["gen_ai.usage.input_tokens"] == 11


def test_patch_capture_content_false_overrides_the_environment(
    otel_spans: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", raising=False
    )
    set_capture_content(False)
    client = _client(lambda request: _response())
    client.system_one("hello", _questions())
    attrs = _attrs(_chat(otel_spans))
    assert "gen_ai.input.messages" not in attrs
    assert "typesafe.questions" not in attrs


def test_conversation_include_content_false_wins(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    with Conversation(include_content=False), Turn(agent_name="app"):
        client.system_one("hello", _questions())
    attrs = _attrs(_chat(otel_spans))
    assert "gen_ai.input.messages" not in attrs
    assert "gen_ai.output.messages" not in attrs
    assert "typesafe.questions" not in attrs


def test_user_turn_is_the_parent_even_when_another_llm_is_active(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    with Turn(agent_name="app") as turn:
        with turn.start_llm(model="other", provider_name="openai"):
            client.system_one("hello", _questions())

    spans = otel_spans.get_finished_spans()
    turn_span = next(span for span in spans if span.name == "invoke_agent app")
    typesafe_chat = next(
        span for span in spans if _attrs(span).get("gen_ai.provider.name") == "typesafe"
    )
    other_chat = next(span for span in spans if span.name == "chat other")
    assert typesafe_chat.parent is not None
    assert typesafe_chat.parent.span_id == turn_span.context.span_id
    assert typesafe_chat.parent.span_id != other_chat.context.span_id
    assert not any(span.name == "invoke_agent typesafe SDK" for span in spans)


def test_ambient_recording_span_is_the_parent_without_a_turn(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response())
    tracer = otel_trace.get_tracer("test")
    with tracer.start_as_current_span("outer"):
        client.system_one("hello", _questions())

    spans = otel_spans.get_finished_spans()
    outer = next(span for span in spans if span.name == "outer")
    chat = _chat(otel_spans)
    assert chat.parent is not None
    assert chat.parent.span_id == outer.context.span_id
    assert not any(span.name == "invoke_agent typesafe SDK" for span in spans)


def test_standalone_llm_is_an_ambient_parent(otel_spans: InMemorySpanExporter) -> None:
    client = _client(lambda request: _response())
    with LLM(model="other", provider_name="openai"):
        client.system_one("hello", _questions())

    spans = otel_spans.get_finished_spans()
    other = next(span for span in spans if span.name == "chat other")
    chat = next(
        span for span in _by_op(spans, "chat") if span.name == "chat jev-latest"
    )
    assert chat.parent is not None
    assert chat.parent.span_id == other.context.span_id


def test_remote_sampled_parent_is_accepted(otel_spans: InMemorySpanExporter) -> None:
    remote = SpanContext(
        trace_id=int("1" * 32, 16),
        span_id=int("2" * 16, 16),
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    token = otel_context.attach(
        otel_trace.set_span_in_context(NonRecordingSpan(remote))
    )
    try:
        client = _client(lambda request: _response())
        client.system_one("hello", _questions())
    finally:
        otel_context.detach(token)

    chat = _chat(otel_spans)
    assert chat.parent is not None
    assert chat.parent.span_id == remote.span_id
    assert not any(
        span.name == "invoke_agent typesafe SDK"
        for span in otel_spans.get_finished_spans()
    )


def test_unsampled_and_ended_local_parents_get_a_root_turn(
    otel_spans: InMemorySpanExporter,
) -> None:
    unsampled = SpanContext(
        trace_id=int("3" * 32, 16),
        span_id=int("4" * 16, 16),
        is_remote=True,
        trace_flags=TraceFlags(0),
    )
    token = otel_context.attach(
        otel_trace.set_span_in_context(NonRecordingSpan(unsampled))
    )
    try:
        client = _client(lambda request: _response())
        client.system_one("hello", _questions())
    finally:
        otel_context.detach(token)

    spans = otel_spans.get_finished_spans()
    turn = next(span for span in spans if span.name == "invoke_agent typesafe SDK")
    assert turn.parent is None
    chat = _chat(otel_spans)
    assert chat.parent is not None
    assert chat.parent.span_id == turn.context.span_id

    otel_spans.clear()
    tracer = otel_trace.get_tracer("test")
    with tracer.start_as_current_span("done") as done:
        ended = done
    token = otel_context.attach(otel_trace.set_span_in_context(ended))
    try:
        client.system_one("hello", _questions())
    finally:
        otel_context.detach(token)
    spans = otel_spans.get_finished_spans()
    turn = next(span for span in spans if span.name == "invoke_agent typesafe SDK")
    chat = next(span for span in spans if span.name == "chat jev-latest")
    assert chat.parent is not None
    assert chat.parent.span_id == turn.context.span_id
    assert chat.parent.span_id != ended.context.span_id


def test_error_span_keeps_status_and_drops_the_body(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(
        lambda request: _response(400, {"error": _SECRET}, request_id="req_err")
    )
    with pytest.raises(TypeSafeAPIError) as caught:
        client.system_one("hello", _questions())
    assert caught.value.status == 400
    assert _SECRET in str(caught.value)

    spans = otel_spans.get_finished_spans()
    for span in spans:
        assert _SECRET not in _text(span)
        assert span.status.status_code.name == "ERROR"
        assert not span.status.description
        assert span.events == ()
    chat = _chat(otel_spans)
    attrs = _attrs(chat)
    assert attrs["http.response.status_code"] == 400
    assert attrs["gen_ai.response.id"] == "req_err"
    assert attrs["error.type"] == "typesafe_sdk._core.errors.TypeSafeBadRequestError"
    assert "gen_ai.output.messages" not in attrs


def test_user_turn_exit_records_the_original_error_and_the_llm_span_does_not(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response(400, {"error": _SECRET}))
    with pytest.raises(TypeSafeAPIError) as caught, Turn(agent_name="app"):
        client.system_one("hello", _questions())

    spans = otel_spans.get_finished_spans()
    chat = next(
        span for span in spans if _attrs(span).get("gen_ai.provider.name") == "typesafe"
    )
    turn = next(span for span in spans if span.name == "invoke_agent app")
    assert _SECRET not in _text(chat)
    assert turn.status.description == str(caught.value)


def test_missing_request_id_and_custom_model_record_only_available_fields(
    otel_spans: InMemorySpanExporter,
) -> None:
    client = _client(lambda request: _response(request_id=None))
    client.system_one("hello", _questions())
    assert "gen_ai.response.id" not in _attrs(_chat(otel_spans))

    otel_spans.clear()

    def handler(request: httpx2.Request) -> httpx2.Response:
        return _response(body={"model": "jev-preview"}, request_id=None)

    client = _client(handler)
    result = client.system_one("hello", _questions(), response_model=OnlyModel)
    assert result.model == "jev-preview"
    attrs = _attrs(_chat(otel_spans))
    assert attrs["gen_ai.response.model"] == "jev-preview"
    assert "gen_ai.usage.input_tokens" not in attrs
    assert "gen_ai.usage.output_tokens" not in attrs
    assert "gen_ai.response.id" not in attrs
    assert "gen_ai.output.messages" not in attrs


def test_pii_redaction_applies_to_messages_and_questions(
    otel_spans: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
) -> None:
    def redact(value: str) -> str:
        return value.replace(_EMAIL, "<EMAIL>")

    def redact_tree(value: Any) -> Any:
        if isinstance(value, str):
            return redact(value)
        if isinstance(value, dict):
            return {key: redact_tree(item) for key, item in value.items()}
        if isinstance(value, list):
            return [redact_tree(item) for item in value]
        return value

    monkeypatch.setattr(
        "weave.conversation.conversation.should_redact_pii", lambda: True
    )
    # Message redaction goes through redact_pii, which calls Presidio itself.
    # Questions are one string and go through redact_pii_string.
    monkeypatch.setattr("weave.utils.pii_redaction.redact_pii", redact_tree)
    monkeypatch.setattr(typesafe_integration, "should_redact_pii", lambda: True)
    monkeypatch.setattr(typesafe_integration, "redact_pii_string", redact)

    client = _client(lambda request: _response())
    client.system_one(
        f"contact {_EMAIL}",
        {"billing": Noul(instructions=f"Email {_EMAIL}?")},
    )
    chat = _chat(otel_spans)
    attrs = _attrs(chat)
    assert _EMAIL not in _text(chat)
    assert _messages(chat, "gen_ai.input.messages") == [
        {
            "role": "user",
            "parts": [{"type": "text", "content": "contact <EMAIL>"}],
        }
    ]
    assert json.loads(attrs["typesafe.questions"]) == [
        {
            "id": "billing",
            "type": "noul",
            "instructions": "Email <EMAIL>?",
        }
    ]


def test_models_list_is_not_instrumented(otel_spans: InMemorySpanExporter) -> None:
    client = _client(lambda request: _response())
    with pytest.raises(TypeSafeError):
        client.models.list()
    assert _by_op(otel_spans.get_finished_spans(), "chat") == []


def test_retries_stay_inside_one_span(otel_spans: InMemorySpanExporter) -> None:
    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return _response(500, {"error": _SECRET})
        return _response()

    client = TypeSafeClient(
        api_key="test-key",
        transport=httpx2.MockTransport(handler),
        retry=RetryPolicy(max_retries=1),
    )
    client.system_one("hello", _questions())
    assert calls["n"] == 2
    assert len(_by_op(otel_spans.get_finished_spans(), "chat")) == 1
    assert _SECRET not in _text(_chat(otel_spans))


def test_second_patch_does_not_double_span(otel_spans: InMemorySpanExporter) -> None:
    get_typesafe_patcher().attempt_patch()
    client = _client(lambda request: _response())
    client.system_one("hello", _questions())
    assert len(_by_op(otel_spans.get_finished_spans(), "chat")) == 1


def test_import_mapping_patches_an_already_imported_sdk() -> None:
    assert (
        patch_module.INTEGRATION_MODULE_MAPPING["typesafe_sdk"]
        is patch_module.patch_typesafe
    )
    patch_module._PATCHED_INTEGRATIONS.discard("typesafe_sdk")
    patch_module._patch_if_needed("typesafe_sdk")
    assert "typesafe_sdk" in patch_module._PATCHED_INTEGRATIONS

    patch_module._PATCHED_INTEGRATIONS.discard("typesafe_sdk")
    implicit_patch()
    assert "typesafe_sdk" in patch_module._PATCHED_INTEGRATIONS


@pytest.mark.asyncio
async def test_async_parallel_calls_do_not_share_a_turn(
    otel_spans: InMemorySpanExporter,
) -> None:
    started = 0
    release = asyncio.Event()

    async def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal started
        started += 1
        if started < 2:
            await release.wait()
        else:
            release.set()
        return _response()

    client = _async_client(handler)

    async def one(state: str) -> None:
        await client.system_one(state, _questions())

    await asyncio.gather(one("left"), one("right"))
    assert started == 2
    spans = otel_spans.get_finished_spans()
    chats = _by_op(spans, "chat")
    turns = [span for span in spans if span.name == "invoke_agent typesafe SDK"]
    assert len(chats) == 2
    assert len(turns) == 2
    parents = {chat.parent.span_id for chat in chats if chat.parent is not None}
    assert parents == {turn.context.span_id for turn in turns}
    recorded = {
        _messages(chat, "gen_ai.input.messages")[0]["parts"][0]["content"]
        for chat in chats
    }
    assert recorded == {"left", "right"}
