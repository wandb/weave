from enum import Enum
import json
import logging
import typing
import dataclasses
import datetime
import hashlib
import uuid

import typeguard

from .. import stream_data_interfaces
from wandb.sdk.data_types.trace_tree import Span as WBSpan
from wandb.sdk.data_types.trace_tree import Result as WBSpanResult
from .. import weave_types as types
from ..decorator_op import op
from .. import op_def

from .. import api as weave


class StatusCode:
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class SpanKind:
    LLM = "LLM"
    CHAIN = "CHAIN"
    AGENT = "AGENT"
    TOOL = "TOOL"


@weave.type()
class Result:
    # NOTE: In principle this type should be typing.Optional[typing.Dict[str, typing.Any]],
    # but due to a bug in our langchain integration, we have some cases where
    # inputs was logged as a list[str] instead of a dict[str, Any]. The more flexible type
    # below allows our PanelTraceViewer to work in both cases, but were it not for that bug,
    # this extra flexible type wouldn't be needed.
    inputs: typing.Optional[typing.Union[typing.Dict[str, typing.Any], list[str]]]
    outputs: typing.Optional[typing.Dict[str, typing.Any]]


def _setattr_with_typeguard(obj: typing.Any, key: str, value: typing.Any) -> None:
    """
    Set an attribute on an instance of a class with annotated class attributes, but first check that
    the value is of the correct type. If not, log a warning and set the attribute to None.
    """

    hints = typing.get_type_hints(obj.__class__)
    if key not in hints:
        raise ValueError(f"Object {obj} has no attribute {key}")

    try:
        typeguard.check_type(value, hints[key])
    except typeguard.TypeCheckError as e:
        # warn
        logging.warning(
            f"Setting attribute {key} of {obj} to {value} failed typeguard check: {e}. Replacing with None."
        )
        value = None

    setattr(obj, key, value)


@weave.type()
class Span:
    span_id: typing.Optional[str] = None
    # TODO: had to change this, what does it break?
    _name: typing.Optional[str] = None
    start_time_ms: typing.Optional[int] = None
    end_time_ms: typing.Optional[int] = None
    status_code: typing.Optional[str] = None
    status_message: typing.Optional[str] = None
    attributes: typing.Optional[typing.Dict[str, typing.Any]] = None
    # results is not standard and not representation by OpenTelemetry
    results: typing.Optional[typing.List[typing.Optional[Result]]] = dataclasses.field(
        default_factory=lambda: None
    )
    child_spans: typing.Optional[typing.List[dict]] = dataclasses.field(
        default_factory=lambda: None
    )
    span_kind: typing.Optional[str] = dataclasses.field(default_factory=lambda: None)

    def get_child_spans(self) -> typing.List["Span"]:
        return [Span.from_dump(s) for s in self.child_spans or []]

    @classmethod
    def from_dump(cls, dump_dict: dict) -> "Span":
        root_span = cls()
        for key in dump_dict:
            if key == "name":
                _setattr_with_typeguard(root_span, "_name", dump_dict[key])
            elif key == "results":
                results = dump_dict[key]
                _setattr_with_typeguard(
                    root_span,
                    key,
                    [Result(**r) if r is not None else None for r in results]
                    if results is not None
                    else None,
                )
            else:
                _setattr_with_typeguard(root_span, key, dump_dict[key])

        return root_span


# Type used when logging normalized (flat) span data instead of a tree.
# we can add status_code etc...
class FlatSpanType(typing.TypedDict):
    trace_id: typing.Optional[str]
    span_id: typing.Optional[str]
    parent_id: typing.Optional[str]
    name: typing.Optional[str]
    start_time_ms: typing.Optional[int]
    end_time_ms: typing.Optional[int]
    attributes: typing.Optional[typing.Dict[str, typing.Any]]


def stringified_output(obj: typing.Any) -> str:
    if isinstance(obj, str):
        return obj
    elif isinstance(obj, (int, float)):
        return str(obj)
    elif isinstance(obj, dict):
        return json.dumps(obj, indent=2)
    elif isinstance(obj, list):
        return json.dumps(obj, indent=2)
    else:
        return str(obj)


def get_first_error(span: Span) -> typing.Optional[str]:
    if span.status_code == "ERROR":
        return span.status_message or ""
    for child in span.get_child_spans() or []:
        error = get_first_error(child)  # type: ignore
        if error is not None:
            return error
    return None


def standarize_result_inputs(result: typing.Optional[Result]) -> typing.Dict[str, str]:
    if result is None:
        return {}
    if isinstance(result.inputs, dict):
        return result.inputs
    if result.inputs is None:
        return {}
    if isinstance(result.inputs, list):
        # NOTE: In principle this block should not be needed, but due to a bug in our
        # langchain integration, we have some cases where inputs was logged as a list[str]
        # instead of a dict[str, Any]. This block allows PanelTraceViewer to work in both cases,
        # but were it not for that bug, this block wouldn't be needed.
        return {str(i): v for i, v in enumerate(result.inputs)}
    raise ValueError(f"Unexpected result inputs type: {type(result.inputs)}")


def get_trace_input_str(span: Span) -> str:
    return "\n\n".join(
        [
            "\n\n".join(
                [
                    f"**{ndx}.{eKey}:** {eValue}"
                    for eKey, eValue in standarize_result_inputs(result).items()
                ]
            )
            for ndx, result in enumerate(span.results or [])
        ]
    )


def get_trace_output_str(span: Span) -> str:
    return "\n\n".join(
        [
            "\n\n".join(
                [
                    f"**{ndx}.{eKey}:** {eValue}"
                    for eKey, eValue in (
                        (result.outputs or {}) if result is not None else {}
                    ).items()
                ]
            )
            for ndx, result in enumerate(span.results or [])
        ]
    )


def get_chain_repr(span: Span) -> str:
    basic_name: str = span._name or span.span_kind or "Unknown"
    inner_calls = []
    for child in span.get_child_spans():
        inner_calls.append(get_chain_repr(child))  # type: ignore
    if len(inner_calls) == 0:
        return basic_name
    return f"{basic_name}({', '.join(inner_calls)})"


@weave.type(__override_name="wb_trace_tree")  # type: ignore
class WBTraceTree:
    root_span_dumps: str  # Span
    model_dict_dumps: typing.Optional[
        str
    ] = None  # typing.Optional[typing.Dict[str, typing.Any]]
    model_hash: typing.Optional[str] = None

    @weave.op()
    def startTime(self) -> typing.Optional[int]:
        try:
            root_span: Span = json.loads(self.root_span_dumps)
            return root_span.start_time_ms
        except Exception:
            logging.warning("Failed to parse root span")
            return None

    @weave.op()
    def traceSummaryDict(self) -> dict:
        root_span = Span()
        try:
            loaded_dump = json.loads(self.root_span_dumps)
        except Exception:
            logging.warning("Failed to parse root span")
        else:
            root_span = Span.from_dump(loaded_dump)

        return {
            "isSuccess": root_span.status_code in [None, "SUCCESS"],
            "startTime": root_span.start_time_ms,
            "formattedInput": get_trace_input_str(root_span),
            "formattedOutput": get_trace_output_str(root_span),
            "formattedChain": get_chain_repr(root_span),
            "error": get_first_error(root_span),
            "modelHash": self.model_hash,
        }


def span_dict_to_wb_span(span_dict: dict) -> WBSpan:
    child_spans = [
        span_dict_to_wb_span(child_dict)
        for child_dict in (span_dict.get("child_spans") or [])
    ]
    return WBSpan(
        span_id=span_dict.get("span_id"),
        name=span_dict.get("name"),
        start_time_ms=span_dict.get("start_time_ms"),
        end_time_ms=span_dict.get("end_time_ms"),
        status_code=span_dict.get("status_code"),
        status_message=span_dict.get("status_message"),
        attributes=span_dict.get("attributes"),
        results=[
            WBSpanResult(
                inputs=r.get("inputs"),
                outputs=r.get("outputs"),
            )
            for r in span_dict.get("results", [])
        ],
        span_kind=span_dict.get("span_kind"),
        child_spans=child_spans,
    )


class TraceSpanDictWithTimestamp(stream_data_interfaces.TraceSpanDict):
    timestamp: datetime.datetime


@op(
    hidden=True,
)
def refine_convert_output_type(
    tree: WBTraceTree,
) -> types.Type:
    with op_def.no_refine():
        node = convert_to_spans(tree)
    res = weave.use(node)
    if len(res) == 0:
        return types.List(
            types.TypedDict(
                {
                    "span_id": types.String(),
                    "name": types.String(),
                    "trace_id": types.String(),
                    "status_code": types.String(),
                    "start_time_s": types.Number(),
                    "end_time_s": types.Number(),
                    "parent_id": types.optional(types.String()),
                    "attributes": types.optional(types.TypedDict({})),
                    "inputs": types.optional(types.TypedDict({})),
                    "output": types.optional(types.TypedDict({})),
                    "summary": types.optional(types.TypedDict({})),
                    "exception": types.optional(types.String()),
                    "timestamp": types.Timestamp(),
                }
            )
        )
    final = types.TypeRegistry.type_of(res)
    return final


def create_id_from_seed(seed: str) -> str:
    m = hashlib.md5()
    m.update(seed.encode("utf-8"))
    return str(uuid.UUID(m.hexdigest()))


@weave.op(
    name="wb_trace_tree-convertToSpans", refine_output_type=refine_convert_output_type
)
def convert_to_spans(
    tree: WBTraceTree,
) -> typing.List[TraceSpanDictWithTimestamp]:
    loaded_dump = json.loads(tree.root_span_dumps)
    wb_span = span_dict_to_wb_span(loaded_dump)

    # Ensure stable span id (since some old traces don't have them)
    if wb_span.span_id is None:
        wb_span.span_id = create_id_from_seed(tree.root_span_dumps)

    spans: typing.List[
        TraceSpanDictWithTimestamp
    ] = stream_data_interfaces.wb_span_to_weave_spans(
        wb_span, None, None
    )  # type: ignore
    if len(spans) > 0:
        spans[0]["attributes"] = spans[0]["attributes"] or {}
        spans[0]["attributes"]["model"] = {  # type: ignore
            "id": tree.model_hash,
            "obj": tree.model_dict_dumps,
        }

    for span in spans:
        span["timestamp"] = datetime.datetime.fromtimestamp(span["start_time_s"])
    return spans
