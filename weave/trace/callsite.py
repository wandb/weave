"""Utilities for capturing callsite information."""

import inspect
from typing import TypedDict


class CallsiteInfo(TypedDict, total=False):
    """Callsite information."""

    file: str | None
    line: int | None
    function: str | None


def get_callsite_info(skip_frames: int = 0) -> CallsiteInfo:
    """Get information about the callsite.

    Args:
        skip_frames: Number of additional frames to skip when walking the stack.
                     This is useful when the function is called from a wrapper.

    Returns:
        A dictionary containing:
        - file: The file path where the call was made
        - line: The line number where the call was made
        - function: The function name where the call was made
    """
    callsite_info: CallsiteInfo = {}

    try:
        # Get the current frame and walk up the stack
        # We need to skip:
        # - This function (get_callsite_info)
        # - The function that called us (typically in weave_client.py)
        # - Any additional frames specified by skip_frames
        frame = inspect.currentframe()
        if frame is not None:
            # Skip this function and the caller
            for _ in range(2 + skip_frames):
                if frame.f_back is not None:
                    frame = frame.f_back
                else:
                    break

            # Get the frame info
            frame_info = inspect.getframeinfo(frame)
            callsite_info["file"] = frame_info.filename
            callsite_info["line"] = frame_info.lineno
            callsite_info["function"] = frame_info.function

    except Exception:
        # If anything goes wrong, return empty callsite info
        pass

    return callsite_info
