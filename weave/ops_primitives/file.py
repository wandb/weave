import os

from ..api import op, mutation, weave_class
from .. import weave_types as types

_py_open = open


def path_ext(path):
    return os.path.splitext(path)[1].strip(".")


##### These are actually path ops, but they are called file for legacy reason


@op(
    name="file-dir",
    input_type={"file": types.DirType()},
    output_type=types.DirType(),
)
def file_dir(file):
    return file


##### End path ops


@weave_class(weave_type=types.FileType)
class File:
    @op(
        name="file-table",
        input_type={"file": types.FileType()},
        output_type=types.WBTable(),
    )
    def table(file):
        # file is an artifact manifest entry for now.
        local_path = file.download()
        import json

        return json.loads(_py_open(local_path).read())

    @op(
        name="file-directUrlAsOf",
        input_type={"file": types.FileType(), "asOf": types.Int()},
        output_type=types.String(),
    )
    def direct_url_as_of(file, asOf):
        # TODO: This should depend on whether its local or an artifact
        #    etc
        local_path = file.path
        return "/__weave/file/%s" % local_path

    @op(
        name="file-size", input_type={"file": types.FileType()}, output_type=types.Int()
    )
    def file_size(file):
        # file is an artifact manifest entry for now.
        return 10
        return file.size

    @mutation
    def file_contents_set(self, val):
        return self._file_contents_set(val)

    @op(
        setter=file_contents_set,
        name="file-contents",
        input_type={"file": types.FileType()},
        output_type=types.String(),
    )
    def file_contents(file):
        return file._contents()


types.FileType.instance_class = File
types.FileType.instance_classes = File


# Question, should all tables be lazy? That would mean we can serialize
#     and hand them between processes.... How would the user choose to
#     save a serialized version of a given table?


# @op(name="file-type", input_type={"file": types.FileType()}, output_type=types.Type())
# def file_type(file):
#     # file is an artifact manifest entry for now.
#     path = file.path
#     parts = path.split(".")
#     extension = None
#     if len(parts) > 1:
#         extension = parts[-1]
#     result_type = {"type": "file", "extension": extension}
#     if len(parts) > 2 and extension == "json":
#         # TODO: validate. I'm sure there is existing logic for this in wandb
#         result_type["wbObjectType"] = {
#             "type": parts[-2],
#         }
#     return result_type


@weave_class(weave_type=types.SubDirType)
class SubDir(object):
    def __init__(self, fullPath, size, dirs, files):
        self.fullPath = fullPath
        self.size = size
        self.dirs = dirs
        self.files = files


types.SubDirType.instance_classes = SubDir
types.SubDirType.instance_class = SubDir


@weave_class(weave_type=types.DirType)
class Dir(object):
    def __init__(self, fullPath, size, dirs, files):
        self.fullPath = fullPath
        self.size = size
        self.dirs = dirs
        self.files = files

    def get_local_path(self):
        return self.path

    @op(name="dir-size", input_type={"dir": types.DirType()}, output_type=types.Int())
    def size(dir):
        return dir.size

    @op(
        name="dir-pathReturnType",
        input_type={"dir": types.DirType(), "path": types.String()},
        output_type=types.Type(),
    )
    def path_return_type(dir, path):
        return dir._path_return_type(path)

    @op(
        name="dir-path",
        input_type={"dir": types.DirType(), "path": types.String()},
        output_type=types.UnionType(types.FileType(), types.DirType(), types.none_type),
    )
    def open(dir, path):
        return dir._path(path)


types.DirType.instance_classes = Dir
types.DirType.instance_class = Dir
