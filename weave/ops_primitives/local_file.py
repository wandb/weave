import os

from ..api import op, mutation, weave_class
from .. import weave_types as types
from . import file


def path_ext(path):
    return os.path.splitext(path)[1].strip(".")


@weave_class(weave_type=types.LocalFileType)
class LocalFile:
    def __init__(self, path, mtime=None, extension=None):
        self.extension = extension
        if self.extension is None:
            self.extension = path_ext(path)
        self.path = path
        # Include mtime so that pure ops can consume us and hit cache
        # if the file has not been updated.
        self.mtime = mtime
        if self.mtime is None:
            self.mtime = os.path.getmtime(path)

    @property
    def changes_path(self):
        return f"{self.path}.weave_changes.json"

    def get_local_path(self):
        return self.path

    @op(
        name="file-directUrl",
        input_type={"file": types.FileType(types.String())},
        output_type=types.String(),
    )
    def direct_url(file):
        return "/__weave/file/%s" % os.path.abspath(file.path)

    @mutation
    def writecsv(self, csv):
        csv.save(self.path)

    # TODO: Move to File object, but does inheritance work?? Probably.
    @op(
        # TODO: I had to mark pure=False
        # But that's not true! We need to know if the file we're reading is
        # immutable (inside an artifact) or not (on a filesystem).
        setter=writecsv,
        name="file-readcsv",
        input_type={"self": types.FileType(types.String())},
        output_type=types.Table(types.Dict(types.String(), types.String())),
    )
    def readcsv(self):
        # TODO: shouldn't need to do this, we can know the type of the file
        # we're opening and just return that type directly.

        # file is an artifact manifest entry for now.
        from . import csv_

        local_path = self.get_local_path()
        obj = csv_.Csv([])  # TODO: weird
        obj.load(local_path)

        return obj


types.LocalFileType.instance_classes = LocalFile
types.LocalFileType.instance_class = LocalFile


def path_type(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Specified file or directory does not exist: '{path}'")
    elif os.path.isdir(path):
        return types.DirType()
    else:
        ext = path_ext(path)
        return types.LocalFileType(extension=types.Const(types.String(), ext))


def open_(path):
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
                        subdir_files[sub_fname] = 1
                sub_dir = file.SubDir(
                    full_path, 10, subdir_dirs, subdir_files
                )  # TODO: size
                sub_dirs[fname] = sub_dir
            else:
                # sub_file = LocalFile(full_path, os.path.getsize(full_path), {}, {})
                sub_file = LocalFile(full_path)
                sub_files[fname] = sub_file
        return file.Dir(path, 111, sub_dirs, sub_files)
    else:
        return LocalFile(path)


def op_file_open_return_type(input_types):
    path = input_types["path"]
    if not isinstance(path, types.Const):
        return types.UnionType(types.LocalFileType(), types.DirType())
    else:
        return path_type(path.val)


@op(
    name="localpathReturnType",
    input_type={"path": types.String()},
    output_type=types.Type(),
)
def local_path_return_type(path):
    return path_type(path)


@op(
    name="localpath",
    input_type={"path": types.String()},
    output_type=op_file_open_return_type,
    pure=False,
)
def local_path(path):
    return open_(path)
