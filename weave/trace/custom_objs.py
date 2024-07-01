import contextlib
import io
import os
import tempfile
from typing import Any, Dict, Generator, Iterator, Mapping, Optional, Union

from weave.client_context.weave_client import require_weave_client
from weave.legacy import artifact_fs
from weave.trace import op_type  # Must import this to register op save/load
from weave.trace.op import Op, op
from weave.trace.refs import ObjectRef, parse_uri
from weave.trace.serializer import get_serializer_by_id, get_serializer_for_obj
from weave.trace_server.trace_server_interface_util import (
    decode_b64_to_bytes,
    encode_bytes_as_b64,
)


class MemTraceFilesArtifact(artifact_fs.FilesystemArtifact):
    RefClass = artifact_fs.FilesystemArtifactRef
    temp_read_dir: Optional[tempfile.TemporaryDirectory]
    path_contents: dict[str, bytes]

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
        self.path_contents[path] = f.getvalue()  # type: ignore
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
                f = io.StringIO(val.decode("utf-8"))
        except KeyError:
            raise FileNotFoundError(path)
        yield f
        f.close()

    def path(self, path: str) -> str:
        if path not in self.path_contents:
            raise FileNotFoundError(path)

        self.temp_read_dir = tempfile.TemporaryDirectory()
        write_path = os.path.join(self.temp_read_dir.name, path)
        with open(write_path, "wb") as f:
            f.write(self.path_contents[path])
            f.flush()
            os.fsync(f.fileno())
        return write_path

    @property
    def metadata(self) -> artifact_fs.ArtifactMetadata:
        return artifact_fs.ArtifactMetadata(self._metadata, {**self._metadata})

    @contextlib.contextmanager
    def writeable_file_path(self, path: str) -> Generator[str, None, None]:
        with tempfile.TemporaryDirectory() as tmpdir:
            full_path = os.path.join(tmpdir, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            yield full_path
            with open(full_path, "rb") as fp:
                self.path_contents[path] = fp.read()


def encode_custom_obj(obj: Any) -> Optional[dict]:
    serializer = get_serializer_for_obj(obj)
    if serializer is None:
        # We silently return None right now. We could warn here. This object
        # will not be recoverable with client.get
        return None
    art = MemTraceFilesArtifact()
    serializer.save(obj, art, "obj")

    # Save the load_instance function as an op, and store a reference
    # to that op in the saved value record. We don't do this if what
    # we're saving is actually an op, since that would be self-referential
    # (the op loading code is always present, we don't need to save/load it).
    load_op_uri = None
    if serializer.id() != "Op":
        # Ensure load_instance is an op
        if not isinstance(serializer.load, Op):
            serializer.load = op(serializer.load)
        # Save the load_intance_op
        wc = require_weave_client()

        # TODO(PR): this can fail right? Or does it return None?
        load_instance_op_ref = wc._save_op(serializer.load, "load_" + serializer.id())  # type: ignore
        load_op_uri = load_instance_op_ref.uri()

    encoded_path_contents = {
        k: (v.encode("utf-8") if isinstance(v, str) else v)  # type: ignore
        for k, v in art.path_contents.items()
    }
    return {
        "_type": "CustomWeaveType",
        "weave_type": {"type": serializer.id()},
        "files": encoded_path_contents,
        "load_op": load_op_uri,
    }


def decode_custom_obj(
    weave_type: Dict,
    encoded_path_contents: Mapping[str, Union[str, bytes]],
    load_instance_op_uri: Optional[str],
) -> Any:
    from weave.legacy import artifact_fs

    load_instance_op = None
    if load_instance_op_uri is not None:
        ref = parse_uri(load_instance_op_uri)
        if not isinstance(ref, ObjectRef):
            raise ValueError(f"Expected ObjectRef, got {load_instance_op_uri}")
        wc = require_weave_client()
        load_instance_op = wc.get(ref)
        if load_instance_op == None:  # == to check for None or BoxedNone
            raise ValueError(
                f"Failed to load op needed to decoded object of type {weave_type}. See logs above for more information."
            )

    if load_instance_op is None:
        serializer = get_serializer_by_id(weave_type["type"])
        if serializer is None:
            raise ValueError(f"No serializer found for {weave_type}")
        load_instance_op = serializer.load

    art = MemTraceFilesArtifact(
        encoded_path_contents,
        metadata={},
    )
    with artifact_fs.loading_artifact(art):
        return load_instance_op(art, "obj")
