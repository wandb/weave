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
from .. import artifact_local
from .. import ref_base
from .. import uris
from .. import weave_types as types
from .. import mappers_python
from ..run import RunKey, Run
from ..runs import Run as WeaveRunObj
from ..run_sql import RunSql
from .. import storage
from .. import box

import functools
from urllib import parse
from typing import Any, Optional
from .. import graph_client_context
from .. import uris
from .. import errors
from .. import ref_base
from .. import weave_types as types


from .trace_server_interface_util import version_hash_for_object
from . import trace_server_interface as tsi

quote_slashes = functools.partial(parse.quote, safe="")


class MemTraceFilesArtifact(artifact_fs.FilesystemArtifact):
    RefClass = artifact_fs.FilesystemArtifactRef

    def __init__(
        self,
        entity: str,
        project: str,
        name: str,
        version: str = None,
        path_contents=None,
        metadata=None,
    ):
        if path_contents is None:
            path_contents = {}
        self.path_contents = path_contents
        if metadata is None:
            metadata = {}
        self._metadata = metadata
        self.temp_read_dir = None

        self._entity = entity
        self._project = project
        self._name = name
        self._version = version

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
        return self._version

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

    def path(self, path: str) -> str:
        if path not in self.path_contents:
            raise FileNotFoundError(path)
        import tempfile

        if self.temp_read_dir is None:
            self.temp_read_dir = tempfile.mkdtemp()
        write_path = os.path.join(self.temp_read_dir, path)
        with open(write_path, "wb") as f:
            f.write(self.path_contents[path])
        return write_path

    @property
    def uri_obj(self) -> uris.WeaveURI:
        # TODO: This is why wrong, but why do we need it here?
        # because OpDefType.load_instance tries to use it
        trace_noun = "obj"
        # HACK!
        if "obj.py" in self.path_contents:
            trace_noun = "op"
        return TraceNounUri(
            entity=self._entity,
            project=self._project,
            trace_noun=trace_noun,
            name=self._name,
            version=self._version,
        )

    @property
    def metadata(self):
        return artifact_fs.ArtifactMetadata(self._metadata, {**self._metadata})


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


# URIS are the WORST! Here is what we want:
# `wandb-trace://[entity]/[project]/call/[ID]`
# `wandb-trace://[entity]/[project]/op/name:[CONTENT_HASH]`
# `wandb-trace://[entity]/[project]/obj/name:[CONTENT_HASH]/[PATH]#[EXTRA]`
@dataclasses.dataclass
class TraceNounUri(uris.WeaveURI):
    SCHEME = "wandb-trace"
    entity: str
    project: str
    trace_noun: str
    path: Optional[list[str]] = None
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
        entity = netloc.strip("/")
        path_parts = path.strip("/").split("/")

        if len(path_parts) < 3:
            raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")

        project = path_parts[0]
        trace_noun = path_parts[1]
        compound_version = path_parts[2]
        path = None
        extra = None
        if trace_noun == "call":
            name = ""
            version = compound_version
        elif trace_noun == "op" or trace_noun == "obj":
            compound_version_parts = compound_version.split(":")
            if not len(compound_version_parts) == 2:
                raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")
            name = compound_version_parts[0]
            version = compound_version_parts[1]
        else:
            raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")
        if trace_noun == "obj":
            path = path_parts[3:]
            if not path:
                path = None
            if fragment:
                extra = fragment.split("/")
                if not extra:
                    extra = None
        else:
            if path_parts[3:]:
                raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")
            if fragment:
                raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")

        return cls(
            entity=entity,
            project=project,
            trace_noun=trace_noun,
            name=name,
            version=version,
            path=path,
            extra=extra,
        )

    def __str__(self) -> str:
        compound_version = (
            f"{quote_slashes(self.name)}:{quote_slashes(self.version)}"
            if self.name
            else quote_slashes(self.version)
        )
        uri = (
            f"{self.SCHEME}://"
            f"{quote_slashes(self.entity)}/"
            f"{quote_slashes(self.project)}/"
            f"{quote_slashes(self.trace_noun)}/"
            f"{compound_version}"
        )
        if self.path:
            uri += f"/{'/'.join(self.path)}"
        if self.extra:
            uri += f"#{'/'.join(self.extra)}"
        return uri

    def to_ref(self) -> "TraceNounRef":
        return TraceNounRef.from_uri(self)

    def with_path(self, path: str) -> "TraceNounUri":

        return TraceNounUri(
            entity=self.entity,
            project=self.project,
            trace_noun=self.trace_noun,
            name=self.name,
            version=self.version,
            path=(self.path or []) + path.split("/"),
            extra=None,
        )


class TraceNounRef(ref_base.Ref):
    def __init__(
        self,
        entity: str,
        project: str,
        trace_noun: str,
        name: str,
        version: str,
        path: Optional[list[str]] = None,
        extra: Optional[list[str]] = None,
        type: typing.Optional[types.Type] = None,
        obj: typing.Optional[typing.Any] = None,
    ):
        self._entity = entity
        self._project = project
        self._trace_noun = trace_noun
        self._name = name
        self._version = version
        self._path = path
        self._extra = extra

        if trace_noun not in ["call", "op", "obj"]:
            raise ValueError(f"Invalid trace noun: {trace_noun}")
        if path or extra:
            if trace_noun != "obj":
                raise ValueError("Path and extra only valid for obj noun")

        # Needed because mappers_python checks this
        self.artifact = None

        super().__init__(obj=obj, type=type)

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "TraceNounRef":
        if not isinstance(uri, TraceNounUri):
            raise ValueError("Expected WandbTableURI")
        return cls(
            entity=uri.entity,
            project=uri.project,
            trace_noun=uri.trace_noun,
            name=uri.name,
            version=uri.version,
            path=uri.path,
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
            TraceNounUri(
                entity=self._entity,
                project=self._project,
                trace_noun=self._trace_noun,
                name=self._name,
                version=self._version,
                path=self._path,
                extra=self._extra,
            )
        )

    def _get(self) -> Any:
        gc = graph_client_context.require_graph_client()
        assert isinstance(gc, GraphClientTrace)
        if self._trace_noun == "call":
            raise NotImplementedError
        elif self._trace_noun == "op":
            res = gc.trace_server.op_read(
                tsi.OpReadReq(
                    entity=self._entity,
                    project=self._project,
                    name=self._name,
                    version_hash=self._version,
                )
            )
            art = MemTraceFilesArtifact(
                self._entity,
                self._project,
                self._name,
                self._version,
                {k: v for k, v in res.op_obj.encoded_file_map.items()},
                metadata=res.op_obj.metadata_dict,
            )
            wb_type = types.TypeRegistry.type_from_dict(res.op_obj.type_dict)
            data = wb_type.load_instance(art, "obj")
            return data
        elif self._trace_noun == "obj":
            res = gc.trace_server.obj_read(
                tsi.ObjReadReq(
                    entity=self._entity,
                    project=self._project,
                    name=self._name,
                    version_hash=self._version,
                    # path=self._path,
                    # extra=self._extra,
                )
            )

            art = MemTraceFilesArtifact(
                self._entity,
                self._project,
                self._name,
                self._version,
                {k: v for k, v in res.obj.encoded_file_map.items()},
                metadata=res.obj.metadata_dict,
            )
            wb_type = types.TypeRegistry.type_from_dict(res.obj.type_dict)
            # mapper = mappers_python.map_from_python(wb_type, art)  # type: ignore
            data = wb_type.load_instance(art, "obj")
            return data
            # return mapper.apply(res.obj.val_dict)
        else:
            raise ValueError(f"Invalid trace noun: {self._trace_noun}")

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
    ) -> "TraceNounRef":
        if self._trace_noun != "obj":
            raise ValueError("Can only add extra to obj ref")

        new_extra = self._extra
        if new_extra is None:
            new_extra = []
        else:
            new_extra = self._extra.copy()
        new_extra += extra
        return self.__class__(
            entity=self._entity,
            project=self._project,
            trace_noun=self._trace_noun,
            name=self._name,
            version=self._version,
            path=self._path,
            extra=new_extra,
        )


@dataclasses.dataclass
class GraphClientTrace(GraphClient[WeaveRunObj]):
    def __init__(
        self, entity: str, project: str, trace_server: tsi.TraceServerInterface
    ):
        self.entity = entity
        self.project = project
        self.trace_server = trace_server

    ##### Read API

    # Implement the required members from the "GraphClient" protocol class
    def runs(self) -> Sequence[Run]:
        res = self.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=self.entity,
                project=self.project,
            )
        )
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
        return isinstance(ref, TraceNounRef)

    def ref_uri(
        self, name: str, version: str, path: str
    ) -> artifact_local.WeaveLocalArtifactURI:
        raise NotImplementedError

    def run_ui_url(self, run: Run) -> str:
        return "<UI URL NOT IMPLEMENTED>"

    ##### Write API

    # def save_object(self, obj: typing.Any, name: str, branch_name: str) -> TraceNounRef:
    def save_object(self, obj: typing.Any, name: str, branch_name: str) -> ref_base.Ref:
        _orig_ref = _get_ref(obj)
        if isinstance(_orig_ref, TraceNounRef):
            return _orig_ref
        weave_type = types.type_of_with_refs(obj)
        orig_obj = obj
        obj = box.box(obj)
        art = MemTraceFilesArtifact(self.entity, self.project, name)
        ref = art.set("obj", weave_type, obj)
        # ref_base._put_ref(obj, ref)

        # mapper = mappers_python.map_to_python(weave_type, art)
        # val = mapper.apply(obj)

        # type_val = storage.to_python(obj, ref_persister=save_custom_object)
        # Should this encoding be handled below the server abstraction?
        encoded_path_contents = {}
        for k, v in art.path_contents.items():
            if isinstance(v, str):
                encoded_path_contents[k] = v.encode("utf-8")
            else:
                encoded_path_contents[k] = v
        partial_obj = tsi.PartialObjForCreationSchema(
            entity=self.entity,
            project=self.project,
            name=name,
            type_dict=weave_type.to_dict(),
            # val_dict=val,
            encoded_file_map=encoded_path_contents,
            metadata_dict=art.metadata.as_dict(),
        )
        version_hash = version_hash_for_object(partial_obj)
        if isinstance(obj, OpDef):
            trace_noun = "op"
            self.trace_server.op_create(tsi.OpCreateReq(op_obj=partial_obj))
        else:
            trace_noun = "obj"
            self.trace_server.obj_create(tsi.ObjCreateReq(obj=partial_obj))

        art._version = version_hash

        ref = TraceNounRef(
            entity=self.entity,
            project=self.project,
            trace_noun=trace_noun,
            name=name,
            version=version_hash,
            path=None,
            extra=None,
            obj=obj,
            type=weave_type,
        )
        ref_base._put_ref(obj, ref)
        ref_base._put_ref(orig_obj, ref)
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

        call = tsi.PartialCallForCreationSchema(
            entity=self.entity,
            project=self.project,
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
        self.trace_server.call_update(
            {
                "entity": self.entity,
                "project": self.project,
                "id": run.id,
                "fields": {
                    "end_time_s": time.time(),
                    "exception": str(exception),
                },
            }
        )

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
        self.trace_server.call_update(
            tsi.CallUpdateReq.model_validate(
                {
                    "entity": self.entity,
                    "project": self.project,
                    "id": run.id,
                    "fields": {"end_time_s": time.time(), "outputs": output},
                }
            )
        )

    def add_feedback(self, run_id: str, feedback: typing.Any) -> None:
        raise NotImplementedError


def _get_ref(obj: typing.Any) -> typing.Optional[ref_base.Ref]:
    if isinstance(obj, ref_base.Ref):
        return obj
    return ref_base.get_ref(obj)
