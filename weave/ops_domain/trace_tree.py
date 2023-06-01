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
    span_id: typing.Optional[str] = None
    # TODO: had to change this, what does it break?
    _name: typing.Optional[str] = None
    start_time_ms: typing.Optional[int] = None
    end_time_ms: typing.Optional[int] = None
    status_code: typing.Optional[str] = None
    status_message: typing.Optional[str] = None
    attributes: typing.Optional[typing.Dict[str, typing.Any]] = None
    results: typing.Optional[typing.List[Result]] = dataclasses.field(
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
                setattr(root_span, "_name", dump_dict[key])
            elif key == "results":
                setattr(root_span, key, [Result(**r) for r in dump_dict[key]])
            else:
                setattr(root_span, key, dump_dict[key])

        return root_span


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


def get_trace_input_str(span: Span) -> str:
    return "\n\n".join(
        [
            "\n\n".join(
                [
                    f"**{ndx}.{eKey}:** {eValue}"
                    for eKey, eValue in (result.inputs or {}).items()
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
                    for eKey, eValue in (result.outputs or {}).items()
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
