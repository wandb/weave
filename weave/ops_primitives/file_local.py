import os

from ..api import op, mutation, weave_class
from .. import weave_types as types
from . import file as weave_file
from . import csv_


class LocalFileType(types.FileType):
    name = "local_file"

    def property_types(self):
        return {
            "extension": self.extension,
            "path": types.String(),
            # TODO: Datetime?
            "mtime": types.Float(),
        }


@weave_class(weave_type=LocalFileType)
class LocalFile(weave_file.File):
    def __init__(self, path, mtime=None, extension=None):
        self.extension = extension
        if self.extension is None:
            self.extension = weave_file.path_ext(path)
        self.path = path
        # Include mtime so that pure ops can consume us and hit cache
        # if the file has not been updated.
        self.mtime = mtime
        if self.mtime is None:
            self.mtime = os.path.getmtime(path)

    def _file_contents_set(self, val):
        with open(self.path, "w") as f:
            f.write(val)
        return self

    def _contents(self):
        return open(self.path, encoding="ISO-8859-1").read()

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
    def writecsv(self, csv_data):
        csv_.save_csv(self.get_local_path(), csv_data)

    # TODO: Move to File object, but does inheritance work?? Probably.
    @op(
        # TODO: I had to mark pure=False
        # But that's not true! We need to know if the file we're reading is
        # immutable (inside an artifact) or not (on a filesystem).
        setter=writecsv,
        name="file-readcsv",
        input_type={"self": types.FileType(types.String())},
        output_type=types.List(types.TypedDict({})),
    )
    def readcsv(self):
        # TODO: shouldn't need to do this, we can know the type of the file
        # we're opening and just return that type directly.

        # file is an artifact manifest entry for now.
        return csv_.load_csv(self.get_local_path())


LocalFileType.instance_classes = LocalFile
LocalFileType.instance_class = LocalFile


# This is exactly types.DirType except it uses LocalFileType in .files.
# TODO: Make a more general mechanism to do this, with less boilerplate.
# We want something like `type LocalDir = Dir<LocalFile>`
class LocalDirType(types.ObjectType):
    name = "localdir"

    def __init__(self):
        pass

    def property_types(self):
        return {
            "fullPath": types.String(),
            "size": types.Int(),
            "dirs": types.Dict(types.String(), types.SubDirType(LocalFileType())),
            "files": types.Dict(types.String(), LocalFileType()),
        }


@weave_class(weave_type=LocalDirType)
class LocalDir(weave_file.Dir):
    def _path_return_type(self, path):
        return path_type(os.path.join(self.fullPath, path))

    def _path(self, path):
        return open_(os.path.join(self.fullPath, path))


LocalDirType.instance_classes = LocalDir
LocalDirType.instance_class = LocalDir


def path_type(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Specified file or directory does not exist: '{path}'")
    elif os.path.isdir(path):
        return LocalDirType()
    else:
        ext = weave_file.path_ext(path)
        return LocalFileType(extension=types.Const(types.String(), ext))


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
                        subdir_files[sub_fname] = LocalFile(full_path)
                sub_dir = weave_file.SubDir(
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


def op_local_path_return_type(input_types):
    path = input_types["path"]
    if not isinstance(path, types.Const):
        return types.UnionType(LocalFileType(), LocalDirType())
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
    output_type=op_local_path_return_type,
    pure=False,
)
def local_path(path):
    return open_(path)
