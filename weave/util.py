import os
import random
import socket
import string
import gc, inspect
import ipynbname
import typing
from .errors import WeaveFingerprintErrorMixin

sentry_inited = False


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
    sentry_sdk.init(integrations=[LoggingIntegration(level=None, event_level=None)])


def raise_exception_with_sentry_if_available(
    err: Exception, fingerprint: typing.Any
) -> typing.NoReturn:
    # init_sentry()
    if isinstance(err, WeaveFingerprintErrorMixin):
        err.fingerprint = fingerprint
    raise err


def capture_exception_with_sentry_if_available(
    err: Exception, fingerprint: typing.Any
) -> typing.Union[None, str]:
    # init_sentry()
    try:
        import sentry_sdk
    except ImportError:
        pass
    else:
        with sentry_sdk.push_scope() as scope:
            if fingerprint:
                scope.fingerprint = fingerprint
            elif isinstance(err, WeaveFingerprintErrorMixin):
                scope.fingerprint = err.fingerprint
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
