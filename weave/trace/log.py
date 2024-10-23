import inspect
import time
from typing import Any, Optional

from weave.trace.context import call_context
from weave.trace.context.weave_client_context import get_weave_client


def make_log_entry(inputs: dict[str, Any], output: Any) -> dict:
    """Create a log entry for a call."""
    # Get information about where this code was called from
    caller_frame = inspect.currentframe().f_back.f_back
    caller_info = inspect.getframeinfo(caller_frame)

    # Extract relevant information
    filename = caller_info.filename
    line_number = caller_info.lineno
    function_name = caller_info.function


    log_entry = {
        "@": int(time.time() * 1000),  # Unix epoch time in milliseconds
        "inputs": inputs,
        "output": output,
        "caller_filename": filename,
        "caller_line_number": line_number,
        "caller_function_name": function_name,
    }

    return log_entry



# TODO: Add level
# TODO: Add print options like end='\n', file=None
def log(output: Any,
        *,
        inputs: Optional[dict[str, Any]] = None) -> None:
    """One-line helper for making a call."""
    client = get_weave_client()
    if not client:
        # TODO: Prettier output
        print("no client")
        print(output)
        return
    if inputs is None:
        inputs = {}

    entry = make_log_entry(inputs, output)
    call = call_context.get_current_call()
    # TODO: Summary feels like a better place than attributes but
    # there are issues with aggregation and when it is calculated.
    if call is None:
        call = client.create_call(op="log", inputs={})
        attrs = call.attributes
        weave = attrs.setdefault("weave", {})
        log = weave.setdefault("log", [])
        log.append(entry)
        # attrs = call.attributes
        # attrs.setdefault("weave", {})
        # attrs._set_weave_item('caller_filename', filename)
        # attrs._set_weave_item('caller_line_number', line_number)
        # attrs._set_weave_item('caller_function_name', function_name)
        client.finish_call(call, output=output)
    else:
        attrs = call.attributes
        weave = attrs.setdefault("weave", {})
        log = weave.setdefault("log", [])
        log.append(entry)
