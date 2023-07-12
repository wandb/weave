import os
import pathlib
import typing

from . import environment
from . import path_util
from . import cache


def get_allowed_dir() -> pathlib.Path:
    if not environment.is_public():
        return pathlib.Path("/")
    cache_namespace = cache.get_user_cache_key()
    if cache_namespace is None:
        raise ValueError("cache_namespace is None but is_public() is True")
    return pathlib.Path(environment.weave_filesystem_dir()) / cache_namespace


def path_ext(path: str) -> str:
    return os.path.splitext(path)[1].strip(".")


def check_path(path: str) -> None:
    allowed_dir = get_allowed_dir()
    path_util.safe_join(allowed_dir, path)


def safe_open(path: str, mode: str = "r") -> typing.IO:
    check_path(path)
    # ensure that the directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return open(path, mode)
