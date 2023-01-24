import contextlib
import os
import typing

from . import file_base
from . import file_util
from . import weave_types as types


class LocalFileType(file_base.FileBaseType):
    name = "local_file"

    def instance_to_dict(self, obj: "LocalFile") -> dict:
        return {
            "path": obj.path,
            "mtime": obj.mtime,
        }

    def instance_from_dict(self, d: dict) -> "LocalFile":
        return LocalFile(d["path"], d["mtime"])


class LocalFile(file_base.File):
    def __init__(
        self,
        path: str,
        mtime: typing.Optional[float] = None,
        extension: typing.Optional[str] = None,
    ) -> None:
        self.extension = extension
        if self.extension is None:
            self.extension = file_util.path_ext(path)
        self.path = path
        # Include mtime so that pure ops can consume us and hit cache
        # if the file has not been updated.
        self.mtime = mtime
        if self.mtime is None:
            self.mtime = os.path.getmtime(path)

    @contextlib.contextmanager
    def open(self, mode: str = "r") -> typing.Generator[typing.IO, None, None]:
        f = file_util.safe_open(self.path, mode)
        try:
            yield f
        finally:
            f.close()

    def size(self) -> int:
        return os.path.getsize(self.path)

    def get_local_path(self) -> str:
        return self.path

    def _file_contents_set(self, val: str) -> "LocalFile":
        with open(self.path, "w") as f:
            f.write(val)
        return self

    def _contents(self) -> str:
        with (open(self.path, encoding="ISO-8859-1")) as f:
            return f.read()


LocalFileType.instance_classes = LocalFile


class LocalDirType(types.ObjectType):
    _base_type = file_base.BaseDirType
    name = "localdir"

    def property_types(self) -> dict[str, types.Type]:
        return {
            "fullPath": types.String(),
            "size": types.Int(),
            "dirs": types.Dict(types.String(), file_base.SubDirType(LocalFileType())),
            "files": types.Dict(types.String(), LocalFileType()),
        }


class LocalDir(file_base.Dir):
    def path_info(
        self, path: str
    ) -> typing.Optional[typing.Union["LocalDir", LocalFile]]:
        return get_path_info(os.path.join(self.fullPath, path))


LocalDirType.instance_classes = LocalDir


def get_path_type(path: str) -> typing.Union[LocalDirType, LocalFileType]:
    file_util.check_path(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Specified file or directory does not exist: '{path}'")
    elif os.path.isdir(path):
        return LocalDirType()
    else:
        ext = file_util.path_ext(path)
        return LocalFileType(extension=types.Const(types.String(), ext))


def get_path_info(path: str) -> typing.Optional[typing.Union["LocalDir", LocalFile]]:
    file_util.check_path(path)
    if not os.path.exists(path):
        return None
    elif os.path.isdir(path):
        sub_dirs = {}
        sub_files = {}
        for fname in os.listdir(path):
            full_path = os.path.join(path, fname)
            if os.path.isdir(full_path):
                subdir_dirs = {}
                subdir_files = {}
                for sub_fname in os.listdir(full_path):
                    sub_full_path = os.path.join(full_path, sub_fname)
                    if os.path.isdir(sub_full_path):
                        subdir_dirs[sub_fname] = 1
                    else:
                        subdir_files[sub_fname] = LocalFile(full_path)
                sub_dir = file_base.SubDir(
                    full_path, 10, subdir_dirs, subdir_files
                )  # TODO: size
                sub_dirs[fname] = sub_dir
            else:
                # sub_file = LocalFile(full_path, os.path.getsize(full_path), {}, {})
                sub_file = LocalFile(full_path)
                sub_files[fname] = sub_file
        return LocalDir(path, 111, sub_dirs, sub_files)
    else:
        return LocalFile(path)
