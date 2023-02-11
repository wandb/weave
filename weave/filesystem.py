# Official sync/async interface for filesystem operations. All
# weave interactions with the filesystem should go through this
# interface.
#
# Important features:
# - Threadsafe atomic read/write operations
# - Root directory controlled via context for access control
#
# Note: The above is not the case yet! We're in the middle of migrating
# to this interface.

import asyncio
import time
import typing
import contextlib
import os
import aiofiles
import aiofiles.os as aiofiles_os
from aiofiles.threadpool import text as aiofiles_text
from aiofiles.threadpool import binary as aiofiles_binary

from . import engine_trace
from . import errors
from . import util
from . import environment
from . import cache


tracer = engine_trace.tracer()  # type: ignore
async_utime = aiofiles_os.wrap(os.utime)  # type: ignore

# collection for storing strong refs to background tasks to ensure
# they are completely executed (see https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task)
background_tasks: set[asyncio.Task] = set()


def is_subdir(path: str, root: str) -> bool:
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    return os.path.commonpath([path, root]) == root


def safe_path(path: str) -> str:
    root = get_filesystem_dir()
    result = os.path.join(root, path)
    if not is_subdir(result, root):
        raise errors.WeaveAccessDeniedError(f"Path {path} is not allowed")
    return result


class Filesystem:
    def path(self, path: str) -> str:
        return safe_path(path)

    def exists(self, path: str) -> bool:
        return os.path.exists(self.path(path))

    def getsize(self, path: str) -> int:
        return os.path.getsize(self.path(path))

    def makedirs(self, path: str, exist_ok: bool) -> None:
        os.makedirs(self.path(path), exist_ok=exist_ok)

    def touch(self, path: str, newtime: typing.Optional[float] = None) -> None:
        if newtime is None:
            newtime = time.time()
        os.utime(self.path(path), (newtime, newtime))

    def stat(self, path: str) -> os.stat_result:
        return os.stat(self.path(path))

    @contextlib.contextmanager
    def open_write(
        self, path: str, mode: str = "wb"
    ) -> typing.Generator[typing.IO, None, None]:
        path = self.path(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_name = f"{path}.tmp-{util.rand_string_n(16)}"
        with open(tmp_name, mode) as f:
            yield f
        with tracer.trace("rename"):
            os.rename(tmp_name, path)

    @contextlib.contextmanager
    def open_read(
        self, path: str, mode: str = "rb"
    ) -> typing.Generator[typing.IO, None, None]:
        safe_path = self.path(path)
        with open(safe_path, mode) as f:
            if environment.enable_touch_on_read():
                self.touch(path)
            yield f


class FilesystemAsync:
    def path(self, path: str) -> str:
        return safe_path(path)

    async def exists(self, path: str) -> bool:
        return await aiofiles_os.path.exists(self.path(path))

    async def getsize(self, path: str) -> int:
        return await aiofiles_os.path.getsize(self.path(path))

    async def makedirs(self, path: str, exist_ok: bool) -> None:
        await aiofiles_os.makedirs(self.path(path), exist_ok=exist_ok)

    async def touch(self, path: str, newtime: typing.Optional[float] = None) -> None:
        if newtime is None:
            newtime = time.time()
        await async_utime(self.path(path), (newtime, newtime))

    async def stat(self, path: str) -> os.stat_result:
        return await aiofiles_os.stat(self.path(path))

    # Whew! These type shenaningans were tough to figure out!

    @typing.overload
    def open_write(
        self,
        path: str,
        mode: typing.Literal["w"],
    ) -> typing.AsyncContextManager[aiofiles_text.AsyncTextIOWrapper]:
        ...

    @typing.overload
    def open_write(
        self,
        path: str,
        mode: typing.Literal["wb"] = "wb",
    ) -> typing.AsyncContextManager[aiofiles_binary.AsyncBufferedIOBase]:
        ...

    @contextlib.asynccontextmanager
    async def open_write(
        self,
        path: str,
        mode: typing.Union[typing.Literal["w"], typing.Literal["wb"]] = "wb",
    ) -> typing.Any:
        path = self.path(path)
        await aiofiles_os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_name = f"{path}.tmp-{util.rand_string_n(16)}"
        async with aiofiles.open(tmp_name, mode) as f:
            yield f
        with tracer.trace("rename"):
            await aiofiles_os.rename(tmp_name, path)

    @typing.overload
    def open_read(
        self,
        path: str,
        mode: typing.Literal["r"],
    ) -> typing.AsyncContextManager[aiofiles_text.AsyncTextIOWrapper]:
        ...

    @typing.overload
    def open_read(
        self,
        path: str,
        mode: typing.Literal["rb"] = "rb",
    ) -> typing.AsyncContextManager[aiofiles_binary.AsyncBufferedIOBase]:
        ...

    @contextlib.asynccontextmanager
    async def open_read(
        self,
        path: str,
        mode: typing.Union[typing.Literal["r"], typing.Literal["rb"]] = "rb",
    ) -> typing.Any:
        safe_path = self.path(path)
        async with aiofiles.open(safe_path, mode) as f:
            if environment.enable_touch_on_read():
                now = time.time()  # ensure the new atime is from before the yield
                # fire and forget, dont block yield of f
                task = asyncio.create_task(self.touch(path, newtime=now))
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
            yield f


def get_filesystem() -> Filesystem:
    return Filesystem()


def get_filesystem_async() -> FilesystemAsync:
    return FilesystemAsync()


def get_filesystem_dir() -> str:
    root = environment.weave_filesystem_dir()
    cache_key = cache.get_user_cache_key()
    if cache_key is None:
        return root
    return os.path.join(root, cache_key)
