import os
import random
import socket
import string
import gc, inspect
import ipynbname
import re
import typing

sentry_inited = False

def before_send(event, hint):
    if 'exception' in event:
        exceptions = event['exception'].get('values', [])
        if exceptions:
            # Grab the first exception and extract fingerprint if it exists
            exc_info = exceptions[0]
            message = exc_info.get('value', '')
            match = re.search(r'__fp:([\w]+)', message)
            if match:
                fingerprint = match.group(1)
                new_message = re.sub(r'__fp:[\w]+', '', message).strip()
                event['fingerprint'] = [fingerprint]
                exc_info['value'] = new_message
    return event


def init_sentry():
    global sentry_inited
    if sentry_inited:
        return
    sentry_inited = True

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        return
    # Disable logs going to Sentry. Its slow
    sentry_sdk.init(integrations=[LoggingIntegration(level=None, event_level=None)], before_send=before_send)


def raise_exception_with_sentry_if_available(
    err: Exception
) -> typing.NoReturn:
    init_sentry()
    try:
        import sentry_sdk
    except ImportError:
        raise err
    raise err

    # Note: It seems like you only get one or the other with Sentry: either the fingerprint
    # or the full stack trace. If you set the fingerprint and explicitly capture it, 
    # the stack trace gets dropped. This seems to happen even if you use the `fingerprint`
    # arg in `capture_exception` or raise the error & catch it before capturing it in Sentry.
    # I also tried raising outside of the with block with the same results. 
    # So instead, we attach the fingerprint in the before_send hook at sentry init. 
    # I'm leaving the code block below as a record of what was tried with Sentry's APIs,
    # since it's not intuitive that it doesn't work. 
    # else:
    #     with sentry_sdk.push_scope() as scope:
    #         scope.fingerprint = fingerprint
    #         scope.set_extra("manual_traceback", tb_str)
    #         # I (Tim) don't think we need to explicitly capture the exception
    #         # here, since we're raising it anyway. Explicitly capturing it
    #         # ends dropping the stack trace in Sentry.
    #         # sentry_sdk.capture_exception(err)
    #         raise err


def capture_exception_with_sentry_if_available(
    err: Exception, fingerprint: typing.Any
) -> typing.Union[None, str]:
    init_sentry()
    try:
        import sentry_sdk
    except ImportError:
        pass
    else:
        with sentry_sdk.push_scope() as scope:
            scope.fingerprint = fingerprint
            return sentry_sdk.capture_exception(err)
    return None


def get_notebook_name():
    return ipynbname.name()


def get_hostname():
    return socket.gethostname()


def get_pid():
    return os.getpid()


def rand_string_n(n: int) -> str:
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(n)
    )


def parse_boolean_env_var(name: str) -> bool:
    return os.getenv(name, "False").lower() in ("true", "1", "t")


def parse_number_env_var(name: str) -> typing.Optional[typing.Union[int, float]]:
    raw_val = os.getenv(name)
    if raw_val is None:
        return None
    try:
        return int(raw_val)
    except ValueError:
        return float(raw_val)


def find_names(obj):
    if hasattr(obj, "name"):
        return [obj.name]
    frame = inspect.currentframe()
    for frame in iter(lambda: frame.f_back, None):
        frame.f_locals
    obj_names = []
    for referrer in gc.get_referrers(obj):
        if isinstance(referrer, dict):
            for k, v in referrer.items():
                if v is obj:
                    obj_names.append(k)
    return obj_names


def is_colab():
    try:
        import google.colab
    except ImportError:
        return False
    return True


def is_notebook():
    if is_colab():
        return True
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    else:
        ip = get_ipython()
        if ip is None:
            return False
        if "IPKernelApp" not in ip.config:
            return False
        # if "VSCODE_PID" in os.environ:
        #     return False
    return True


def is_pandas_dataframe(obj):
    try:
        import pandas as pd
    except ImportError:
        return False
    return isinstance(obj, pd.DataFrame)


def _resolve_path(path: str, current_working_directory: str) -> list[str]:
    if not os.path.isabs(path):
        path = os.path.join(current_working_directory, path)
    path_parts: list[str] = []
    for part in path.split(os.path.sep):
        if part == "..":
            if path_parts:
                path_parts.pop()
        elif part != "." and part:
            path_parts.append(part)
    return path_parts


def relpath_no_syscalls(
    target_path: str, start_path: str, current_working_directory: str
) -> str:
    target_parts = _resolve_path(target_path, current_working_directory)
    start_parts = _resolve_path(start_path, current_working_directory)

    if target_parts == start_parts:
        return "."

    common_length = 0
    for target_part, start_part in zip(target_parts, start_parts):
        if target_part != start_part:
            break
        common_length += 1

    relative_parts = [".."] * (len(start_parts) - common_length) + target_parts[
        common_length:
    ]
    return os.path.sep.join(relative_parts)


def sample_rows(data: list, max_rows: int) -> list:
    data_len = len(data)

    if data_len <= max_rows:
        return data

    if max_rows <= 0:
        return []
    if max_rows == 1:
        return [data[0]]
    if max_rows == 2:
        return [data[0], data[-1]]

    split_size = max_rows // 3
    gap_size = (data_len - max_rows) // 2
    start_split = data[:split_size]
    middle_start = split_size + gap_size
    middle_split = data[middle_start : middle_start + split_size]
    end_split = data[-split_size:]
    return start_split + middle_split + end_split
