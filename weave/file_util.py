import os
import pathlib
import typing

from . import context_state
from . import environment
from . import errors
from . import path_util


def get_allowed_dir() -> pathlib.Path:
    if not environment.is_public():
        return pathlib.Path("/")
    cache_namespace = context_state._cache_namespace_token.get()
    if cache_namespace is None:
        raise ValueError("cache_namespace is None but is_public() is True")
    return pathlib.Path(environment.weave_data_dir()) / cache_namespace


def path_ext(path: str) -> str:
    return os.path.splitext(path)[1].strip(".")


def check_path(path: str) -> None:
    allowed_dir = get_allowed_dir()
    path_util.safe_join(allowed_dir, path)


def safe_open(path: str, mode: str = "r") -> typing.IO:
    check_path(path)
    return open(path, mode)
