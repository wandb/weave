from enum import Enum
import json
import logging
import typing
import dataclasses

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
    inputs: typing.Optional[typing.Dict[str, typing.Any]]
    outputs: typing.Optional[typing.Dict[str, typing.Any]]


@weave.type()
class Span:
    span_id: typing.Optional[str]
    # TODO: had to change this, what does it break?
    _name: typing.Optional[str]
    start_time_ms: typing.Optional[int]
    end_time_ms: typing.Optional[int]
    status_code: typing.Optional[str]
    status_message: typing.Optional[str]
    attributes: typing.Optional[typing.Dict[str, typing.Any]]
    results: typing.Optional[typing.List[Result]] = dataclasses.field(
        default_factory=lambda: None
    )
    child_spans: typing.Optional[typing.List[dict]] = dataclasses.field(
        default_factory=lambda: None
    )
    span_kind: typing.Optional[str] = dataclasses.field(default_factory=lambda: None)


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
    if span.get("status_code") == "ERROR":
        return span.get("status_message") or ""
    for child in span.get("child_spans") or []:
        error = get_first_error(child)  # type: ignore
        if error is not None:
            return error
    return None


def get_trace_input_str(span: Span) -> str:
    return "\n\n".join(
        [
            "\n\n".join(
                [
                    f"**{ndx}.{eKey}:** {eValue}"
                    for eKey, eValue in (result.get("inputs") or {}).items()
                ]
            )
            for ndx, result in enumerate(span.get("results") or [])
        ]
    )


def get_trace_output_str(span: Span) -> str:
    return "\n\n".join(
        [
            "\n\n".join(
                [
                    f"**{ndx}.{eKey}:** {eValue}"
                    for eKey, eValue in (result.get("outputs") or {}).items()
                ]
            )
            for ndx, result in enumerate(span.get("results") or [])
        ]
    )


def get_chain_repr(span: Span) -> str:
    basic_name: str = span.get("name") or span.get("span_kind") or "Unknown"
    inner_calls = []
    for child in span.get("child_spans") or []:
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
            return root_span.get("start_time_ms")
        except Exception:
            logging.warning("Failed to parse root span")
            return None

    @weave.op()
    def traceSummaryDict(self) -> dict:
        root_span: Span = {
            "span_id": None,
            "name": None,
            "start_time_ms": None,
            "end_time_ms": None,
            "status_code": None,
            "status_message": None,
            "attributes": None,
            "results": None,
            "child_spans": None,
            "span_kind": None,
        }
        try:
            root_span = json.loads(self.root_span_dumps)
        except Exception:
            logging.warning("Failed to parse root span")
        return {
            "isSuccess": root_span.get("status_code") in [None, "SUCCESS"],
            "startTime": root_span.get("start_time_ms"),
            "formattedInput": get_trace_input_str(root_span),
            "formattedOutput": get_trace_output_str(root_span),
            "formattedChain": get_chain_repr(root_span),
            "error": get_first_error(root_span),
            "modelHash": self.model_hash,
        }
