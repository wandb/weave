import os
import random
import socket
import string
import gc, inspect
import ipynbname
import typing


def raise_exception_with_sentry_if_available(
    err: Exception, fingerprint: typing.Any
) -> typing.NoReturn:
    try:
        import sentry_sdk
    except ImportError:
        raise err
    else:
        with sentry_sdk.push_scope() as scope:
            scope.fingerprint = fingerprint
            sentry_sdk.capture_exception(err)
            raise err


def get_notebook_name():
    return ipynbname.name()


def get_hostname():
    return socket.gethostname()


def get_pid():
    return os.getpid()


def rand_string_n(n):
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(n)
    )


def parse_boolean_env_var(name: str) -> bool:
    return os.getenv(name, "False").lower() in ("true", "1", "t")


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


def is_notebook():
    try:
        import google.colab
    except ImportError:
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
