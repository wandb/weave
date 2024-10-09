"""Utility methods for converting exceptions to JSON."""

import json
import traceback
from typing import Optional, TypedDict


class StackFrameDict(TypedDict):
    filename: str
    line_number: Optional[int]
    function_name: str
    text: Optional[str]


class ExceptionDict(TypedDict, total=False):
    type: str
    message: str
    traceback: Optional[list[StackFrameDict]]


def frame_summary_to_dict(frame: traceback.FrameSummary) -> StackFrameDict:
    return {
        "filename": frame.filename,
        "line_number": frame.lineno,
        "function_name": frame.name,
        "text": frame.line,
    }


def exception_to_dict(exception: BaseException) -> ExceptionDict:
    result: ExceptionDict = {
        "type": type(exception).__name__,
        "message": str(exception),
    }
    if exception.__traceback__:
        stack = traceback.extract_stack(exception.__traceback__.tb_frame)[:-1]
        stack.extend(traceback.extract_tb(exception.__traceback__))
        result["traceback"] = [frame_summary_to_dict(fs) for fs in stack]
    return result


def exception_to_json_str(exception: BaseException) -> str:
    return json.dumps(exception_to_dict(exception))
