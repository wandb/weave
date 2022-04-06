import csv
import json
import pandas
import os

from ..api import op, mutation, weave_class
from .. import weave_types as types
from . import table

_py_open = open


class CsvType(table.ListTableType):
    name = "csv"


@weave_class(weave_type=CsvType)
class Csv(table.ListTable):
    # TODO: should take uri instead of path?
    def load(self, path):
        with open(path) as csvfile:
            dialect = csv.Sniffer().sniff(csvfile.read(1024), delimiters=";,")
            csvfile.seek(0)
            reader = csv.reader(csvfile, dialect)
            header = next(reader)
            col_types = {}
            for key in header:
                col_types[key] = int

            # shitty type guessing
            rows = []
            for raw_row in reader:
                rows.append(raw_row)
                for key, val in zip(header, raw_row):
                    cur_col_type = col_types[key]
                    try:
                        val = int(val)
                    except ValueError:
                        try:
                            val = float(val)
                            if cur_col_type == int:
                                col_types[key] = float
                        except ValueError:
                            if cur_col_type != str:
                                col_types[key] = str
            final_rows = []
            for raw_row in rows:
                row = {}
                for key, val in zip(header, raw_row):
                    row[key] = col_types[key](val)
                final_rows.append(row)
            self.list = final_rows

    def save(self, path):
        field_names = list(self.list[0].keys())
        with open(path, "w") as f:
            writer = csv.DictWriter(f, field_names, delimiter=";")
            writer.writeheader()
            for row in self.list:
                writer.writerow(row)


CsvType.instance_classes = Csv
CsvType.instance_class = Csv


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
        local_path = self.get_local_path()
        obj = Csv([])  # TODO: weird
        obj.load(local_path)
        from . import storage

        return obj


types.LocalFileType.instance_classes = LocalFile
types.LocalFileType.instance_class = LocalFile


@weave_class(weave_type=types.FileType)
class FileOps(object):
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
        input_type={"file": types.FileType(), "asOf": types.Number()},
        output_type=types.String(),
    )
    def direct_url_as_of(file, asOf):
        # TODO: This should depend on whether its local or an artifact
        #    etc
        local_path = file.path
        return "/__weave/file/%s" % local_path


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


@op(name="file-size", input_type={"file": types.FileType()}, output_type=types.Number())
def file_size(file):
    # file is an artifact manifest entry for now.
    return 10
    return file.size


@op(
    name="file-contents",
    input_type={"file": types.FileType()},
    output_type=types.String(),
)
def file_contents(file):
    from . import tags

    artifact = tags.get_tag(file, "artifact")
    if artifact is not None:
        local_path = os.path.join("local-artifacts", artifact.path, file.path)
    else:
        local_path = file.path
    # file is an artifact manifest entry for now.
    return _py_open(local_path, encoding="ISO-8859-1").read()


@op(
    name="file-readcsvpandas",
    input_type={"file": types.FileType()},
    output_type=types.Table(),
)
def file_readpandascsv(file):
    local_path = file.get_local_path()
    try:
        return pandas.read_csv(local_path)
    except:
        return pandas.read_csv(local_path, delimiter=";")


class SubDirType(types.ObjectType):
    # TODO doesn't match frontend
    name = "subdir"

    type_vars: dict[str, types.Type] = {}

    def __init__(self):
        pass

    def property_types(self):
        return {
            "fullPath": types.String(),
            "size": types.Number(),
            "dirs": types.Dict(types.String(), types.Int()),
            # TODO: this should actually be just FileType
            "files": types.Dict(types.String(), types.Int()),
        }


@weave_class(weave_type=SubDirType)
class SubDir(object):
    def __init__(self, fullPath, size, dirs, files):
        self.fullPath = fullPath
        self.size = size
        self.dirs = dirs
        self.files = files


SubDirType.instance_classes = SubDir
SubDirType.instance_class = SubDir


class DirType(types.ObjectType):
    # Fronend src/model/types.ts switches on this (and PanelDir)
    # TODO: We actually want to be localdir here. But then the
    # frontend needs to use a different mechanism for type checking
    name = "dir"

    type_vars: dict[str, types.Type] = {}

    def __init__(self):
        pass

    def property_types(self):
        return {
            "fullPath": types.String(),
            "size": types.Number(),
            "dirs": types.Dict(types.String(), SubDirType()),
            # TODO: this should actually be just FileType
            "files": types.Dict(types.String(), types.LocalFileType()),
        }


def path_ext(path):
    return os.path.splitext(path)[1].strip(".")


def path_type(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Specified file or directory does not exist: '{path}'")
    elif os.path.isdir(path):
        return DirType()
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
                sub_dir = SubDir(full_path, 10, subdir_dirs, subdir_files)  # TODO: size
                sub_dirs[fname] = sub_dir
            else:
                # sub_file = LocalFile(full_path, os.path.getsize(full_path), {}, {})
                sub_file = LocalFile(full_path)
                sub_files[fname] = sub_file
        return Dir(path, 111, sub_dirs, sub_files)
    else:
        return LocalFile(path)


@weave_class(weave_type=DirType)
class Dir(object):
    def __init__(self, fullPath, size, dirs, files):
        self.fullPath = fullPath
        self.size = size
        self.dirs = dirs
        self.files = files

    def get_local_path(self):
        return self.path

    @op(name="dir-size", input_type={"dir": DirType()}, output_type=types.Number())
    def size(dir):
        return dir.size

    @op(
        name="dir-pathReturnType",
        input_type={"dir": DirType(), "path": types.String()},
        output_type=types.Type(),
    )
    def path_return_type(dir, path):
        return path_type(os.path.join(dir.fullPath, path))

    @op(
        name="dir-path",
        input_type={"dir": DirType(), "path": types.String()},
        output_type=types.UnionType(types.LocalFileType(), DirType(), types.none_type),
    )
    def open(dir, path):
        return open_(os.path.join(dir.fullPath, path))


DirType.instance_classes = Dir
DirType.instance_class = Dir


def op_file_open_return_type(input_types):
    path = input_types["path"]
    if not isinstance(path, types.Const):
        return types.UnionType(types.LocalFileType(), DirType())
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


def op_get_return_type(uri):
    from . import storage

    return storage.refs.LocalArtifactRef.from_str(uri).type


def op_get_return_type_from_inputs(inputs):
    return op_get_return_type(inputs["uri"].val)


@op(name="getReturnType", input_type={"uri": types.String()}, output_type=types.Type())
def get_returntype(uri):
    return op_get_return_type(uri)


# @op(
#     name="save",
#     input_type={"obj": types.Any(), "name": types.String()},
#     output_type=lambda input_types: types.LocalArtifactRefType(input_types["obj"]),
# )
# def save(obj, name):
#     from . import storage

#     return storage.save(obj, name=name)


# Hmm... This returns the same obj, not a ref anymore
# TODO: is this what we want?
@op(
    name="save",
    input_type={"obj": types.Any(), "name": types.String()},
    output_type=lambda input_types: input_types["obj"],
)
def save(obj, name):
    from . import storage

    ref = storage.save(obj, name=name)
    return ref.obj


@mutation
def _save(name, obj):
    obj_name, version = name.split("/")
    from . import storage

    storage.save(obj, name=obj_name)


@op(
    pure=False,
    setter=_save,
    name="get",
    input_type={"uri": types.String()},
    output_type=op_get_return_type_from_inputs,
)
def get(uri):
    from . import storage

    return storage.get(uri)
