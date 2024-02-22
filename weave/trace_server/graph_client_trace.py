import dataclasses
import typing
import datetime
import contextlib
import io
import os
from typing import Sequence, Sequence


# from weave.graph_client_sql import MemFilesArtifact

from ..graph_client import GraphClient
from ..op_def import OpDef
from ..ref_base import Ref
from .. import artifact_fs
from .. import artifact_local
from .. import ref_base
from .. import uris
from .. import weave_types as types
from ..run import RunKey, Run
from .. import box
from .. import urls
import functools
from urllib import parse
from typing import Any, Optional
from .. import graph_client_context
from .. import uris
from .. import errors
from .. import ref_base
from .. import weave_types as types


from .trace_server_interface_util import (
    TRACE_REF_SCHEME,
    decode_b64_to_bytes,
    encode_bytes_as_b64,
    generate_id,
    version_hash_for_object,
)
from . import trace_server_interface as tsi

quote_slashes = functools.partial(parse.quote, safe="")


class MemTraceFilesArtifact(artifact_fs.FilesystemArtifact):
    RefClass = artifact_fs.FilesystemArtifactRef
    temp_read_dir: Optional[str]
    path_contents: typing.Dict[str, typing.Union[str, bytes]]

    def __init__(
        self,
        entity: str,
        project: str,
        name: str,
        version: str,
        path_contents: typing.Optional[
            typing.Mapping[str, typing.Union[str, bytes]]
        ] = None,
        metadata: typing.Optional[typing.Dict[str, str]] = None,
    ):
        if path_contents is None:
            path_contents = {}
        self.path_contents = path_contents  # type: ignore
        if metadata is None:
            metadata = {}
        self._metadata = metadata
        self.temp_read_dir = None

        self._entity = entity
        self._project = project
        self._name = name
        self._version = version

    @contextlib.contextmanager
    def new_file(
        self, path: str, binary: bool = False
    ) -> typing.Iterator[typing.Union[io.StringIO, io.BytesIO]]:
        f: typing.Union[io.StringIO, io.BytesIO]
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

    @property
    def version(self) -> str:
        return self._version

    @contextlib.contextmanager
    def open(
        self, path: str, binary: bool = False
    ) -> typing.Iterator[typing.Union[io.StringIO, io.BytesIO]]:
        f: typing.Union[io.StringIO, io.BytesIO]
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
    def uri_obj(self) -> uris.WeaveURI:
        trace_noun = "obj"
        # Hack! We should have a better way to determine this
        if "obj.py" in self.path_contents:
            trace_noun = "op"
        return TraceURI(
            entity=self._entity,
            project=self._project,
            trace_noun=trace_noun,
            name=self._name,
            version=self._version,
        )

    @property
    def metadata(self) -> artifact_fs.ArtifactMetadata:
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


# `wandb-trace:///[entity]/[project]/call/[ID]`
# `wandb-trace:///[entity]/[project]/op/[name]:[CONTENT_HASH]`
# `wandb-trace:///[entity]/[project]/obj/[name]:[CONTENT_HASH]/[PATH]#[EXTRA]`
@dataclasses.dataclass
class TraceURI(uris.WeaveURI):
    SCHEME = TRACE_REF_SCHEME
    version: str
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
    ) -> "TraceURI":
        path_parts = path.strip("/").split("/")

        if len(path_parts) < 4:
            raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")

        entity = path_parts[0]
        project = path_parts[1]
        trace_noun = path_parts[2]
        compound_version = path_parts[3]
        path_res: typing.Optional[typing.List[str]] = None
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
            path_res = path_parts[4:]
            if not path_res:
                path_res = None
            if fragment:
                extra = fragment.split("/")
                if not extra:
                    extra = None
        else:
            if path_parts[4:]:
                raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")
            if fragment:
                raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")

        return cls(
            entity=entity,
            project=project,
            trace_noun=trace_noun,
            name=name,
            version=version,
            path=path_res,
            extra=extra,
        )

    def __str__(self) -> str:
        compound_version = (
            f"{quote_slashes(self.name)}:{quote_slashes(self.version)}"
            if self.name
            else quote_slashes(self.version)
        )
        uri = (
            f"{self.SCHEME}:///"
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

    def to_ref(self) -> "TraceRef":
        return TraceRef.from_uri(self)

    def with_path(self, path: str) -> "TraceURI":

        return TraceURI(
            entity=self.entity,
            project=self.project,
            trace_noun=self.trace_noun,
            name=self.name,
            version=self.version,
            path=(self.path or []) + path.split("/"),
            extra=None,
        )


class TraceRef(ref_base.Ref):
    version: str

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
    def from_uri(cls, uri: uris.WeaveURI) -> "TraceRef":
        if not isinstance(uri, TraceURI):
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
            self._type = types.TypeRegistry.type_of(self.obj)
        return self._type

    @property
    def initial_uri(self) -> str:
        return self.uri

    @property
    def uri(self) -> str:
        return str(
            TraceURI(
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
            raise ValueError("Cannot get call ref")
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
                decode_b64_to_bytes(res.op_obj.b64_file_map),
                metadata=res.op_obj.metadata_dict,
            )
            wb_type = types.TypeRegistry.type_from_dict(res.op_obj.type_dict)
            data = wb_type.load_instance(art, "obj")
            return data
        elif self._trace_noun == "obj":
            if self._path != ["obj"] or self._extra:
                raise NotImplementedError(
                    "Non trivial path not implemented yet", self._path, self._extra
                )
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
                decode_b64_to_bytes(res.obj.b64_file_map),
                metadata=res.obj.metadata_dict,
            )
            wb_type = types.TypeRegistry.type_from_dict(res.obj.type_dict)
            data = wb_type.load_instance(art, "obj")
            return data
        else:
            raise ValueError(f"Invalid trace noun: {self._trace_noun}")

    def __repr__(self) -> str:
        return f"<{self.__class__}({id(self)}) entity_name={self._entity} project_name={self._project} object_name={self._name} version_hash={self._version} obj={self._obj} type={self._type}>"

    def with_extra(
        self, new_type: typing.Optional[types.Type], obj: typing.Any, extra: list[str]
    ) -> "TraceRef":
        if self._trace_noun != "obj":
            raise ValueError("Can only add extra to obj ref")

        new_extra = self._extra
        if new_extra is None:
            new_extra = []
        else:
            new_extra = new_extra.copy()
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

    @property
    def ui_url(self) -> str:
        return urls.object_version_path(
            self._entity, self._project, self._name, self._version
        )


class CallSchemaRun(Run):
    def __init__(self, call: tsi.CallSchema):
        self._call = call

    @property
    def id(self) -> str:
        return self._call.id

    @property
    def trace_id(self) -> str:
        return self._call.trace_id

    @property
    def ui_url(self) -> str:
        return urls.call_path_as_peek(
            self._call.entity, self._call.project, self._call.id
        )


def _run_from_call(call: tsi.CallSchema) -> CallSchemaRun:
    return CallSchemaRun(call)


@dataclasses.dataclass
class GraphClientTrace(GraphClient[CallSchemaRun]):
    def __init__(
        self, entity: str, project: str, trace_server: tsi.TraceServerInterface
    ):
        self.entity = entity
        self.project = project
        self.trace_server = trace_server

    ##### Read API

    # Implement the required members from the "GraphClient" protocol class
    def runs(self) -> Sequence[CallSchemaRun]:
        res = self.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=self.entity,
                project=self.project,
            )
        )
        return [_run_from_call(call) for call in res.calls]

    def run(self, run_id: str) -> typing.Optional[CallSchemaRun]:
        res = self.trace_server.call_read(
            tsi.CallReadReq(
                entity=self.entity,
                project=self.project,
                id=run_id,
            )
        )
        return _run_from_call(res.call)

    def find_op_run(
        self, op_name: str, inputs: dict[str, typing.Any]
    ) -> typing.Optional[Run]:
        # We don't have a good way to do this yet (need to hash the inputs if we want to do it properly)
        raise NotImplementedError()

    def run_children(self, run_id: str) -> Sequence[CallSchemaRun]:
        res = self.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=self.entity,
                project=self.project,
                filter=tsi._CallsFilter(parent_ids=[run_id]),
            )
        )
        return [_run_from_call(call) for call in res.calls]

    def op_runs(self, op_def: OpDef) -> Sequence[CallSchemaRun]:
        ref = _get_ref(op_def)
        if not isinstance(ref, TraceRef):
            raise ValueError("Expected TraceRef")
        ref_str = str(ref)
        res = self.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=self.entity,
                project=self.project,
                filter=tsi._CallsFilter(op_version_refs=[ref_str]),
            )
        )
        return [_run_from_call(call) for call in res.calls]

    def ref_input_to(self, ref: Ref) -> Sequence[CallSchemaRun]:
        if not isinstance(ref, TraceRef):
            raise ValueError("Expected TraceRef")
        ref_str = str(ref)
        res = self.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=self.entity,
                project=self.project,
                filter=tsi._CallsFilter(input_object_version_refs=[ref_str]),
            )
        )
        return [_run_from_call(call) for call in res.calls]

    def ref_value_input_to(self, ref: Ref) -> list[CallSchemaRun]:
        if not isinstance(ref, TraceRef):
            raise ValueError("Expected TraceRef")
        ref_str = str(ref)
        res = self.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=self.entity,
                project=self.project,
                filter=tsi._CallsFilter(input_object_version_refs=[ref_str]),
            )
        )
        return [_run_from_call(call) for call in res.calls]

    def ref_output_of(self, ref: Ref) -> typing.Optional[CallSchemaRun]:
        if not isinstance(ref, TraceRef):
            raise ValueError("Expected TraceRef")
        ref_str = str(ref)
        res = self.trace_server.calls_query(
            tsi.CallsQueryReq(
                entity=self.entity,
                project=self.project,
                filter=tsi._CallsFilter(output_object_version_refs=[ref_str]),
            )
        )
        if not res.calls:
            return None
        return _run_from_call(res.calls[0])

    def run_feedback(self, run_id: str) -> Sequence[dict[str, typing.Any]]:
        raise NotImplementedError()

    def feedback(self, feedback_id: str) -> typing.Optional[dict[str, typing.Any]]:
        raise NotImplementedError()

    # Helpers

    def ref_is_own(self, ref: typing.Optional[ref_base.Ref]) -> bool:
        return isinstance(ref, TraceRef)

    def ref_uri(
        self, name: str, version: str, path: str
    ) -> artifact_local.WeaveLocalArtifactURI:
        raise NotImplementedError()

    def run_ui_url(self, run: Run) -> str:
        return urls.call_path_as_peek(self.entity, self.project, run.id)

    ##### Write API

    def save_object(self, obj: typing.Any, name: str, branch_name: str) -> ref_base.Ref:
        _orig_ref = _get_ref(obj)
        if isinstance(_orig_ref, TraceRef):
            return _orig_ref
        weave_type = types.type_of_with_refs(obj)
        orig_obj = obj
        obj = box.box(obj)
        art = MemTraceFilesArtifact(
            self.entity, self.project, name, "_VERSION_PENDING_"
        )
        obj_name = "obj"
        path: typing.Optional[typing.List[str]] = [obj_name]
        ref: ref_base.Ref = art.set(obj_name, weave_type, obj)

        encoded_path_contents = encode_bytes_as_b64(
            {
                k: (v.encode("utf-8") if isinstance(v, str) else v)
                for k, v in art.path_contents.items()
            }
        )
        partial_obj = tsi.ObjSchemaForInsert(
            entity=self.entity,
            project=self.project,
            name=name,
            type_dict=weave_type.to_dict(),
            b64_file_map=encoded_path_contents,
            metadata_dict=art.metadata.as_dict(),
            created_datetime=datetime.datetime.now(tz=datetime.timezone.utc),
        )
        version_hash = version_hash_for_object(partial_obj)
        if isinstance(obj, OpDef):
            trace_noun = "op"
            self.trace_server.op_create(tsi.OpCreateReq(op_obj=partial_obj))
            path = None
        else:
            trace_noun = "obj"
            self.trace_server.obj_create(tsi.ObjCreateReq(obj=partial_obj))

        art._version = version_hash

        ref = TraceRef(
            entity=self.entity,
            project=self.project,
            trace_noun=trace_noun,
            name=name,
            version=version_hash,
            path=path,
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
    ) -> CallSchemaRun:

        if parent:
            trace_id = parent.trace_id
            parent_id = parent.id
        else:
            trace_id = generate_id()
            parent_id = None

        start = tsi.StartedCallSchemaForInsert(
            entity=self.entity,
            project=self.project,
            id=generate_id(),
            name=op_name,
            trace_id=trace_id,
            start_datetime=datetime.datetime.now(tz=datetime.timezone.utc),
            parent_id=parent_id,
            inputs=refs_to_str(inputs),
            attributes={},
        )
        self.trace_server.call_start(tsi.CallStartReq(start=start))
        return CallSchemaRun(start)

    def fail_run(self, run: CallSchemaRun, exception: BaseException) -> None:
        self.trace_server.call_end(
            tsi.CallEndReq.model_validate(
                {
                    "end": {
                        "entity": self.entity,
                        "project": self.project,
                        "id": run.id,
                        "end_datetime": datetime.datetime.now(tz=datetime.timezone.utc),
                        "outputs": {},
                        "exception": str(exception),
                        "summary": {},
                    },
                }
            )
        )

    def finish_run(
        self,
        run: CallSchemaRun,
        output: typing.Any,
        output_refs: Sequence[Ref],
    ) -> None:
        output = refs_to_str(output)
        if not isinstance(output, dict):
            output = {"_result": output}
        self.trace_server.call_end(
            tsi.CallEndReq.model_validate(
                {
                    "end": {
                        "entity": self.entity,
                        "project": self.project,
                        "id": run.id,
                        "end_datetime": datetime.datetime.now(tz=datetime.timezone.utc),
                        "outputs": output,
                        "summary": {},
                    },
                }
            )
        )

    def add_feedback(self, run_id: str, feedback: typing.Any) -> None:
        raise NotImplementedError()


def _get_ref(obj: typing.Any) -> typing.Optional[ref_base.Ref]:
    if isinstance(obj, ref_base.Ref):
        return obj
    return ref_base.get_ref(obj)
