import os

from ..api import op, mutation, weave_class
from .. import weave_types as types

_py_open = open


@weave_class(weave_type=types.FileType)
class FileOps:
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


@op(name="file-size", input_type={"file": types.FileType()}, output_type=types.Int())
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

    @op(
        name="file-type", input_type={"file": types.DirType()}, output_type=types.Type()
    )
    def file_type(file):
        print("FILE", file, flush=True)
        if isinstance(file, Dir):
            return types.DirType()
        else:
            parts = file.path.split(".")
            ext = ""
            if len(parts) != 1:
                ext = parts[-1]
            return types.LocalFileType(extension=types.Const(types.String(), ext))

    @op(
        name="file-dir",
        input_type={"file": types.DirType()},
        output_type=types.DirType(),
    )
    def file_dir(file):
        return file

    @op(name="dir-size", input_type={"dir": types.DirType()}, output_type=types.Int())
    def size(dir):
        return dir.size

    @op(
        name="dir-pathReturnType",
        input_type={"dir": types.DirType(), "path": types.String()},
        output_type=types.Type(),
    )
    def path_return_type(dir, path):
        from . import file_local

        return file_local.path_type(os.path.join(dir.fullPath, path))

    @op(
        name="dir-path",
        input_type={"dir": types.DirType(), "path": types.String()},
        output_type=types.UnionType(
            types.LocalFileType(), types.DirType(), types.none_type
        ),
    )
    def open(dir, path):
        from . import file_local

        return file_local.open_(os.path.join(dir.fullPath, path))


types.DirType.instance_classes = Dir
types.DirType.instance_class = Dir


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
