import os
import typing

from weave_query.weave_query import environment, file_local2
from weave_query.weave_query import weave_types as types
from weave_query.weave_query.api import op


@op(name="LocalFile-directUrl")
def direct_url(file: file_local2.LocalFile) -> str:
    local_path = os.path.abspath(file.get_local_path())
    return f"{environment.weave_server_url()}/__weave/file{local_path}"


@op(name="LocalFile-directUrlAsOf")
def direct_url_as_of(file: file_local2.LocalFile, asOf: int) -> str:
    local_path = os.path.abspath(file.get_local_path())
    return f"{environment.weave_server_url()}/__weave/file{local_path}"


@op(name="localpathReturnType", hidden=True)
def local_path_refine_type(path: str) -> types.Type:
    return file_local2.get_path_type(path)


@op(
    name="localpath",
    pure=False,
    render_info={"type": "function"},
    refine_output_type=local_path_refine_type,
)
def local_path(
    path: str,
) -> typing.Optional[typing.Union[file_local2.LocalDir, file_local2.LocalFile]]:
    return file_local2.get_path_info(path)
