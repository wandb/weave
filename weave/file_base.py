import contextlib
import dataclasses
import typing

from . import weave_types as types


def wb_object_type_from_path(path: str) -> typing.Tuple[types.Type, str]:
    parts = path.split(".")
    ext = ""
    wbObjectType: types.Type = types.NoneType()
    if len(parts) != 1:
        ext = parts[-1]
    if len(parts) > 2 and ext == "json":
        pathext_wbobjecttype = types.type_name_to_type(parts[-2])
        if pathext_wbobjecttype != None:
            wbObjectType = pathext_wbobjecttype()
    return wbObjectType, ext


@dataclasses.dataclass(frozen=True)
# It'd be nice to just name this FileType, but Weave0 uses that to mean
# ArtifactFile
class FileBaseType(types.Type):
    extension: types.Type = types.String()
    # Match weave0 snakeCase name.
    wbObjectType: types.Type = types.Any()

    @classmethod
    def type_of_instance(cls, obj: "File") -> "FileBaseType":
        # Default implementation for Types that take no arguments.
        wbObjectType, ext = wb_object_type_from_path(obj.path)
        return cls(
            extension=types.Const(types.String(), ext), wbObjectType=wbObjectType
        )

    def _to_dict(self) -> dict:
        # NOTE: js_compat
        # In the js Weave code, file is a non-standard type that
        # puts a const string at extension as just a plain string.
        d = super()._to_dict()
        if isinstance(self.extension, types.Const):
            d["extension"] = self.extension.val
        else:
            d.pop("extension")
        if not isinstance(self.wbObjectType, (types.Any, types.NoneType)):
            d["wbObjectType"] = self.wbObjectType.to_dict()
        else:
            d.pop("wbObjectType")
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "FileBaseType":
        # NOTE: js_compat
        # In the js Weave code, file is a non-standard type that
        # puts a const string at extension as just a plain string.
        extension: types.Type = types.String()
        if "extension" in d:
            extension = types.Const(types.String(), d["extension"])
        wbObjectType: types.Type = types.NoneType()
        if "wbObjectType" in d:
            wbObjectType = types.TypeRegistry.type_from_dict(d["wbObjectType"])
        return cls(extension, wbObjectType)


class File:
    path: str

    def size(self) -> int:
        raise NotImplementedError

    @contextlib.contextmanager
    def open(self, mode: str = "r") -> typing.Generator[typing.IO, None, None]:
        raise NotImplementedError

    def digest(self) -> typing.Optional[str]:
        raise NotImplementedError


FileBaseType.instance_classes = File


class BaseDirType(types.ObjectType):
    def property_types(self) -> dict[str, types.Type]:
        return {
            "fullPath": types.String(),
            "size": types.Int(),
            "dirs": types.Dict(types.String(), SubDirType()),
            # "files": types.Dict(types.String(), FileBaseType()),
            "files": types.Dict(types.String(), SubFileType()),
        }


class Dir:
    def __init__(
        self,
        fullPath: str,
        size: int,
        dirs: typing.Mapping[str, "SubDir"],
        files: typing.Mapping[str, File],
    ):
        self.fullPath = fullPath
        self.size = size
        self.dirs = dirs
        self.files = files

    def path_info(self, path: str) -> typing.Union[File, "Dir", None]:
        raise NotImplementedError


BaseDirType.instance_classes = Dir


@dataclasses.dataclass(frozen=True)
class SubDirType(types.ObjectType):
    # TODO doesn't match frontend
    name = "subdir"

    # A type argument, can be subdir of LocalFile or of FilesystemArtifactFile
    file_type: types.Type = FileBaseType()

    def property_types(self) -> dict[str, types.Type]:
        return {
            "fullPath": types.String(),
            "size": types.Int(),
            "dirs": types.Dict(types.String(), types.Int()),
            "files": types.Dict(types.String(), self.file_type),
        }


class SubDir:
    def __init__(
        self,
        fullPath: str,
        size: int,
        dirs: dict[str, int],
        files: typing.Mapping[str, File],
    ):
        self.fullPath = fullPath
        self.size = size
        self.dirs = dirs
        self.files = files


@dataclasses.dataclass(frozen=True)
class SubFileType(types.ObjectType):
    # TODO doesn't match frontend
    name = "subfile"

    # # A type argument, can be subfile of LocalFile or of FilesystemArtifactFile
    file_type: types.Type = FileBaseType()

    def property_types(self) -> dict[str, types.Type]:
        return {
            "birthArtifactID": types.String(),
            "digest": types.String(),
            "fullPath": types.String(),
            "size": types.Int(),
            "type": types.String(),
            "url": types.String(),
            "_w1_file": self.file_type,
        }


class SubFile:
    def __init__(
        self,
        birthArtifactID: str,
        digest: str,
        fullPath: str,
        size: int,
        url: str,
    ):
        self.birthArtifactID = birthArtifactID
        self.digest = digest
        self.fullPath = fullPath
        self.size = size
        self.url = url


SubDirType.instance_classes = SubDir


# attach to types, a lot of places expect it there
types.FileType = FileBaseType  # type: ignore
