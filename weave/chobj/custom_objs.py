import contextlib
import io
import os
from typing import Optional, Union, Mapping, Iterator
from weave import weave_types as types
from weave import box
from weave import artifact_fs
from weave.trace_server.trace_server_interface_util import (
    encode_bytes_as_b64,
    decode_b64_to_bytes,
)


class MemTraceFilesArtifact(artifact_fs.FilesystemArtifact):
    RefClass = artifact_fs.FilesystemArtifactRef
    temp_read_dir: Optional[str]
    path_contents: dict[str, Union[str, bytes]]

    def __init__(
        self,
        path_contents: Optional[Mapping[str, Union[str, bytes]]] = None,
        metadata: Optional[dict[str, str]] = None,
    ):
        if path_contents is None:
            path_contents = {}
        self.path_contents = path_contents  # type: ignore
        if metadata is None:
            metadata = {}
        self._metadata = metadata
        self.temp_read_dir = None

    @contextlib.contextmanager
    def new_file(
        self, path: str, binary: bool = False
    ) -> Iterator[Union[io.StringIO, io.BytesIO]]:
        f: Union[io.StringIO, io.BytesIO]
        if binary:
            f = io.BytesIO()
        else:
            f = io.StringIO()
        yield f
        self.path_contents[path] = f.getvalue()
        f.close()

    @property
    def is_saved(self) -> bool:
        return True

    @contextlib.contextmanager
    def open(
        self, path: str, binary: bool = False
    ) -> Iterator[Union[io.StringIO, io.BytesIO]]:
        f: Union[io.StringIO, io.BytesIO]
        try:
            if binary:
                val = self.path_contents[path]
                if not isinstance(val, bytes):
                    raise ValueError(
                        f"Expected binary file, but got string for path {path}"
                    )
                f = io.BytesIO(val)
            else:
                val = self.path_contents[path]
                if not isinstance(val, bytes):
                    raise ValueError(
                        f"Expected string file, but got binary for path {path}"
                    )
                f = io.StringIO(val.decode("utf-8"))
        except KeyError:
            raise FileNotFoundError(path)
        yield f
        f.close()

    def path(self, path: str) -> str:
        if path not in self.path_contents:
            raise FileNotFoundError(path)
        import tempfile

        if self.temp_read_dir is None:
            self.temp_read_dir = tempfile.mkdtemp()
        write_path = os.path.join(self.temp_read_dir, path)
        with open(write_path, "wb") as f:
            f.write(self.path_contents[path])  # type: ignore
        return write_path

    @property
    def metadata(self) -> artifact_fs.ArtifactMetadata:
        return artifact_fs.ArtifactMetadata(self._metadata, {**self._metadata})


def encode_custom_obj(obj):
    weave_type = types.type_of(obj)
    if weave_type == types.UnknownType():
        # We silently return None right now. We could warn here. This object
        # will not be recoverable with client.get
        return None
    obj = box.box(obj)
    art = MemTraceFilesArtifact()
    weave_type.save_instance(obj, art, "obj")

    encoded_path_contents = encode_bytes_as_b64(
        {
            k: (v.encode("utf-8") if isinstance(v, str) else v)
            for k, v in art.path_contents.items()
        }
    )
    return {
        "_type": "custom_obj",
        "weave_type": weave_type.to_dict(),
        "files": encoded_path_contents,
    }


def decode_custom_obj(weave_type, encoded_path_contents):
    art = MemTraceFilesArtifact(
        decode_b64_to_bytes(encoded_path_contents),
        metadata={},
    )
    wb_type = types.TypeRegistry.type_from_dict(weave_type)
    return wb_type.load_instance(art, "obj")
