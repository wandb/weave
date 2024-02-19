import dataclasses
import hashlib
import json
import copy
import typing
import uuid
import time
import datetime
import contextlib
import io
import os
from typing import Sequence, Sequence
from clickhouse_connect import get_client

from collections.abc import Mapping

# from weave.graph_client_sql import MemFilesArtifact

from ..graph_client import GraphClient
from ..op_def import OpDef
from ..ref_base import Ref
from .. import artifact_fs
from .. import artifact_base
from .. import artifact_local
from .. import storage
from .. import ref_base
from .. import uris
from .. import weave_types as types
from .. import mappers_python
from ..run import RunKey, Run
from ..runs import Run as WeaveRunObj
from ..run_sql import RunSql
from .. import storage

import functools
from urllib import parse
from typing import Any, Optional
from .. import graph_client_context
from .. import uris
from .. import errors
from .. import ref_base
from .. import weave_types as types


from .remote_http_trace_server import RemoteHTTPTraceServer
from . import trace_server_interface as tsi

quote_slashes = functools.partial(parse.quote, safe="")



# # From Tim: This feels really heavy and I need to understand it better
class MemTraceFilesArtifact(artifact_fs.FilesystemArtifact):
    RefClass = artifact_fs.FilesystemArtifactRef

    def __init__(self, path_contents=None, metadata=None):
        if path_contents is None:
            path_contents = {}
        self.path_contents = path_contents
        if metadata is None:
            metadata = {}
        self._metadata = metadata
        self.temp_read_dir = None

    @contextlib.contextmanager
    def new_file(self, path, binary=False):
        if binary:
            f = io.BytesIO()
        else:
            f = io.StringIO()
        yield f
        self.path_contents[path] = f.getvalue()
        f.close()

    @property
    def is_saved(self):
        return True

    @property
    def version(self):
        return None

    @contextlib.contextmanager
    def open(self, path, binary=False):
        try:
            if binary:
                f = io.BytesIO(self.path_contents[path])
            else:
                f = io.StringIO(self.path_contents[path].decode("utf-8"))
        except KeyError:
            raise FileNotFoundError(path)
        yield f
        f.close()

    def path(self, name: str) -> str:
        if name not in self.path_contents:
            raise FileNotFoundError(name)
        import tempfile

        if self.temp_read_dir is None:
            self.temp_read_dir = tempfile.mkdtemp()
        path = os.path.join(self.temp_read_dir, name)
        with open(path, "wb") as f:
            f.write(self.path_contents[name])
        return path

    @property
    def uri_obj(self) -> uris.WeaveURI:
        # TODO: This is why wrong, but why do we need it here?
        # because OpDefType.load_instance tries to use it
        return TraceObjectURI(
            "name",
            "version",
            "entity",
            "project",
        )

    @property
    def metadata(self):
        return self._metadata


def refs_to_str(val: typing.Any) -> typing.Any:
    if isinstance(val, ref_base.Ref):
        return str(val)
    elif isinstance(val, dict):
        return {k: refs_to_str(v) for k, v in val.items()}  # type: ignore
    elif isinstance(val, list):
        return [refs_to_str(v) for v in val]  # type: ignore
    else:
        return val


# def hash_inputs(
#     inputs: Mapping[str, typing.Any],
# ) -> str:
#     hasher = hashlib.md5()
#     hasher.update(json.dumps(refs_to_str(inputs)).encode())
#     return hasher.hexdigest()


# def make_run_id(op_name: str, inputs: dict[str, typing.Any]) -> str:
#     input_hash = hash_inputs(inputs)
#     hasher = hashlib.md5()
#     hasher.update(op_name.encode())
#     hasher.update(input_hash.encode())
#     return hasher.hexdigest()




@dataclasses.dataclass
class TraceObjectURI(uris.WeaveURI):
    SCHEME = "trace-object"
    name: str
    version: typing.Optional[str]
    entity_name: str
    project_name: str
    extra: Optional[list[str]] = None

    @classmethod
    def from_parsed_uri(
        cls,
        uri: str,
        schema: str,
        netloc: str,
        path: str,
        params: str,
        query: dict[str, list[str]],
        fragment: str,
    ):
        parts = path.strip("/").split("/")
        parts = [parse.unquote(part) for part in parts]
        if len(parts) < 3:
            raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")
        entity_name = parts[0]
        project_name = parts[1]
        name = parts[2]
        version = parts[3]

        extra: Optional[list[str]] = None
        if fragment:
            extra = fragment.split("/")
        return cls(
            name,
            version,
            entity_name,
            project_name,
            extra,
        )

    def __str__(self) -> str:
        uri = (
            f"{self.SCHEME}:///"
            f"{quote_slashes(self.entity_name)}/"
            f"{quote_slashes(self.project_name)}/"
            f"{quote_slashes(self.name)}"
            f":{quote_slashes(self.version)}"
        )
        # if self.row_id:
        #     uri += f"/{quote_slashes(self.row_id)}"
        # if self.version_hash:
        #     uri += f"/{quote_slashes(self.version_hash)}"
        if self.extra:
            uri += f"#{'/'.join(self.extra)}"
        return uri

    def to_ref(self) -> "TraceObjectRef":
        return TraceObjectRef.from_uri(self)

    def with_path(self, path: str) -> "TraceObjectURI":
        return TraceObjectURI(
            self.name,
            self.version,
            self.entity_name,
            self.project_name,
            # path,
            self.extra,
        )


class TraceObjectRef(ref_base.Ref):
    def __init__(
        self,
        entity_name: str,
        project_name: str,
        object_name: str,
        version_hash: Optional[str],
        obj: Optional[Any] = None,
        type: Optional["types.Type"] = None,
        extra: Optional[list[str]] = None,
    ):
        self._entity_name = entity_name
        self._project_name = project_name
        self._object_name = object_name
        self._version_hash = version_hash
        self._extra = extra

        # Needed because mappers_python checks this
        self.artifact = None

        super().__init__(obj=obj, type=type)

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "TraceObjectRef":
        if not isinstance(uri, TraceObjectURI):
            raise ValueError("Expected WandbTableURI")
        return cls(
            uri.entity_name,
            uri.project_name,
            uri.name,
            uri.version_hash,
            uri.row_version,
            extra=uri.extra,
        )

    @property
    def is_saved(self) -> bool:
        return True

    @property
    def type(self) -> "types.Type":
        if self._type is None:
            # TODO: expensive
            self._type = types.TypeRegistry.type_of(self.obj)
        return self._type

    @property
    def initial_uri(self) -> str:
        return self.uri

    @property
    def uri(self) -> str:
        return str(
            TraceObjectURI(
                self._object_name,
                self._version_hash,
                self._entity_name,
                self._project_name,
                # None,  # netloc ?
                # row_version=self._row_version,
                extra=self.extra,
            )
        )

    def _get(self) -> Any:
        raise NotImplementedError
        # gc = graph_client_context.require_graph_client()
        # assert isinstance(gc, GraphClientTrace)
        # assert self._version_hash
        # client = gc.client
        # query_result = client.query(
        #     f"SELECT * FROM objects WHERE id = '{self._version_hash}'",
        #     # Tell clickhouse_connect to return the files map as bytes. But this
        #     # also returns the keys as bytes...
        #     column_formats={"files": {"string": "bytes"}},
        # )
        # item = query_result.first_item
        # files = {k.decode("utf-8"): v for k, v in item["files"].items()}
        # art = MemFilesArtifact(files, metadata=json.loads(item["art_meta"]))
        # wb_type = types.TypeRegistry.type_from_dict(json.loads(item["type"]))
        # mapper = mappers_python.map_from_python(wb_type, art)  # type: ignore
        # res = mapper.apply(json.loads(item["val"]))
        # return res

    def __repr__(self) -> str:
        return f"<{self.__class__}({id(self)}) entity_name={self._entity_name} project_name={self._project_name} object_name={self._object_name} version_hash={self._version_hash} row_version={self._row_version} obj={self._obj} type={self._type}>"

    def with_extra(
        self, new_type: typing.Optional[types.Type], obj: typing.Any, extra: list[str]
    ) -> "TraceObjectRef":
        new_extra = self.extra
        if self.extra is None:
            new_extra = []
        else:
            new_extra = self.extra.copy()
        new_extra += extra
        return self.__class__(
            entity_name=self._entity_name,
            project_name=self._project_name,
            object_name=self._object_name,
            version_hash=self._version_hash,
            obj=obj,
            extra=new_extra,
        )


@dataclasses.dataclass
class GraphClientTrace(GraphClient[WeaveRunObj]):
    def __init__(self, trace_server:tsi.TraceServerInterface):
        self.trace_server = trace_server

    ##### Read API

    # Implement the required members from the "GraphClient" protocol class
    def runs(self) -> Sequence[Run]:
        res = self.trace_server.calls_query(tsi.CallsQueryReq(
            entity="test_entity",
            project="test_project",
        ))
        return res.calls

    def run(self, run_id: str) -> typing.Optional[Run]:
        raise NotImplementedError

    def find_op_run(
        self, op_name: str, inputs: dict[str, typing.Any]
    ) -> typing.Optional[Run]:
        raise NotImplementedError

    def run_children(self, run_id: str) -> Sequence[Run]:
        raise NotImplementedError

    def op_runs(self, op_def: OpDef) -> Sequence[Run]:
        raise NotImplementedError

    def ref_input_to(self, ref: Ref) -> Sequence[Run]:
        raise NotImplementedError

    def ref_value_input_to(self, ref: Ref) -> list[Run]:
        raise NotImplementedError

    def ref_output_of(self, ref: Ref) -> typing.Optional[Run]:
        raise NotImplementedError

    def run_feedback(self, run_id: str) -> Sequence[dict[str, typing.Any]]:
        raise NotImplementedError

    def feedback(self, feedback_id: str) -> typing.Optional[dict[str, typing.Any]]:
        raise NotImplementedError

    # Helpers

    def ref_is_own(self, ref: typing.Optional[ref_base.Ref]) -> bool:
        # raise NotImplementedError
        # return False
        return isinstance(ref, TraceObjectRef)

    def ref_uri(
        self, name: str, version: str, path: str
    ) -> artifact_local.WeaveLocalArtifactURI:
        raise NotImplementedError

    def run_ui_url(self, run: Run) -> str:
        return "<UI URL NOT IMPLEMENTED>"

    ##### Write API

    # def save_object(self, obj: typing.Any, name: str, branch_name: str) -> TraceObjectRef:
    def save_object(self, obj: typing.Any, name: str, branch_name: str) -> ref_base.Ref:
        wb_type = types.type_of_with_refs(obj)

        art = MemTraceFilesArtifact()

        mapper = mappers_python.map_to_python(wb_type, art)
        # val = mapper.apply(obj)

        # type_val = storage.to_python(obj, ref_persister=save_custom_object)
        id_ = str(uuid.uuid4())
        encoded_path_contents = {}
        for k, v in art.path_contents.items():
            if isinstance(v, str):
                encoded_path_contents[k] = v.encode("utf-8")
            else:
                encoded_path_contents[k] = v
        # TODO: Make this work
        # self.client.insert(
        #     "objects",
        #     [
        #         (
        #             id_,
        #             json.dumps(wb_type.to_dict()),
        #             json.dumps(val),
        #             encoded_path_contents,
        #             json.dumps(art.metadata),
        #         )
        #     ],
        # )
        # TODO  we have have already computed type here, should construct
        # ref with it (type_val["_type"])
        ref = TraceObjectRef("entity", "project", name, id_, obj, None, None)
        ref_base._put_ref(obj, ref)
        return ref

    def create_run(
        self,
        op_name: str,
        parent: typing.Optional["RunKey"],
        inputs: typing.Dict[str, typing.Any],
        input_refs: Sequence[Ref],
    ) -> WeaveRunObj:
        inputs = copy.copy(inputs)
        inputs["_keys"] = list(inputs.keys())
        for i, ref in enumerate(input_refs[:3]):
            inputs["_ref%s" % i] = ref
            inputs["_ref_digest%s" % i] = ref.digest

        if parent:
            trace_id = parent.trace_id
            parent_id = parent.id
        else:
            trace_id = str(uuid.uuid4())
            parent_id = None

        call=tsi.PartialCallForCreationSchema(
            entity="test_entity",
            project="test_project",
            id=str(uuid.uuid4()),
            name=op_name,
            trace_id=trace_id,
            start_time_s=time.time(),
            parent_id=parent_id,
            inputs=refs_to_str(inputs),
        )
        self.trace_server.call_create(tsi.CallCreateReq(call=call))
        return RunSql(call.model_dump())

    def fail_run(self, run: Run, exception: BaseException) -> None:
        self.trace_server.call_update({
            "entity": "test_entity",
            "project": "test_project",
            "id": run.id,
            "fields": {
                "end_time_s": time.time(),
                "exception": str(exception),
            },
        })

    def finish_run(
        self,
        run: WeaveRunObj,
        output: typing.Any,
        output_refs: Sequence[Ref],
    ) -> None:
        # TODO process outputs into Refs
        output = refs_to_str(output)
        if not isinstance(output, dict):
            output = {"_result": output}
        self.trace_server.call_update(tsi.CallUpdateReq.model_validate({
            "entity": "test_entity",
            "project": "test_project",
            "id": run.id,
            "fields": {
                "end_time_s": time.time(),
                "outputs":output
            },
        }))

    def add_feedback(self, run_id: str, feedback: typing.Any) -> None:
        raise NotImplementedError
