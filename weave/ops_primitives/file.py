import os
import typing
from ..api import op
from .. import weave_types as types
from .. import file_base


@op(name="dir-pathReturnType")
def path_return_type(dir: file_base.Dir, path: str) -> types.Type:
    return types.TypeRegistry.type_of(dir.path_info(path))


@op(
    name="dir-path",
    refine_output_type=path_return_type,
)
def open(
    dir: file_base.Dir, path: str
) -> typing.Union[file_base.File, file_base.Dir, None]:
    return dir.path_info(path)


@op(name="file-direct_url_as_of")
def direct_url_as_of(file: file_base.File, asOf: int) -> str:
    # This should only be used in the first dispatch phase
    raise NotImplementedError


@op(name="file-contents")
def file_contents(file: file_base.File) -> str:
    with file.open("rb") as f:
        return f.read().decode("ISO-8859-1")


@op(name="file-dir")
def artifactfile_dir(
    item: typing.Union[file_base.File, file_base.Dir],
) -> typing.Optional[file_base.Dir]:
    if not isinstance(item, file_base.Dir):
        return None
    return item


@op(name="file-type")
def file_type(file: typing.Union[file_base.File, file_base.Dir]) -> types.Type:
    return types.TypeRegistry.type_of(file)


@op(name="file-path")
def file_path(file: file_base.File) -> str:
    return file.path


@op(name="file-size")
def file_size(file: file_base.File) -> int:
    return file.size()
