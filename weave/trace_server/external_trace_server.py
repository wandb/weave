import abc
import io
import json
import sys
import typing as t

from pydantic import BaseModel

from . import refs_internal as ri


from . import trace_server_interface as tsi


class IdConverter:
    @abc.abstractmethod
    def convert_ext_to_int_project_id(self, project_id: str) -> str:
        ...

    @abc.abstractmethod
    def convert_int_to_ext_project_id(self, project_id: str) -> str:
        ...

    @abc.abstractmethod
    def convert_ext_to_int_run_id(self, run_id: str) -> str:
        ...

    @abc.abstractmethod
    def convert_int_to_ext_run_id(self, run_id: str) -> str:
        ...

    @abc.abstractmethod
    def convert_ext_to_int_user_id(self, user_id: str) -> str:
        ...

    @abc.abstractmethod
    def convert_int_to_ext_user_id(self, user_id: str) -> str:
        ...


class ExternalTraceServer(tsi.TraceServerInterface):
    _internal_trace_server: tsi.TraceServerInterface
    _id_converter: IdConverter

    def __init__(
        self, internal_trace_server: tsi.TraceServerInterface, id_converter: IdConverter
    ):
        super().__init__()
        self._internal_trace_server = internal_trace_server
        self._id_converter = id_converter

    # Call API
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        req.start.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.start.project_id
        )
        if req.start.wb_run_id:
            req.start.wb_run_id = self._id_converter.convert_ext_to_int_run_id(
                req.start.run_id
            )
        if req.start.wb_user_id:
            req.start.wb_user_id = self._id_converter.convert_ext_to_int_user_id(
                req.start.user_id
            )

        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.call_start(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        req.end.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.end.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.call_end(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        req.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.call_read(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        req.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.calls_query(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        req.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.calls_query_stats(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        req.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.project_id
        )
        if req.wb_user_id:
            req.wb_user_id = self._id_converter.convert_ext_to_int_user_id(req.user_id)
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.calls_delete(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    # Op API

    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        req.op_obj.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.op_obj.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.op_create(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        req.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.op_read(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        req.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.ops_query(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    # Obj API

    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        req.obj.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.obj.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.obj_create(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        req.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.obj_read(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        req.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.objs_query(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        req.table.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.table.project_id
        )

        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.table_create(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        req.project_id = self._id_converter.convert_ext_to_int_project_id(
            req.project_id
        )
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.table_query(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        return self._universal_int_to_ext_ref_converter(
            self._internal_trace_server.refs_read_batch(
                self._universal_ext_to_int_ref_converter(req)
            )
        )

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return self._internal_trace_server.file_create(req)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return self._internal_trace_server.file_content_read(req)

    def _universal_ext_to_int_ref_converter(self, obj: t.Any) -> t.Any:
        ext_to_int_project_cache: t.Dict[str, str] = {}
        weave_prefix = ri.WEAVE_SCHEME + ":///"

        def replace_ref(ref_str: str) -> str:
            if not ref_str.startswith(weave_prefix):
                raise ValueError(f"Invalid URI: {ref_str}")
            rest = ref_str[len(weave_prefix) :]
            parts = rest.split("/", 2)
            if len(parts) != 3:
                raise ValueError(f"Invalid URI: {ref_str}")
            entity, project, tail = parts
            project_key = f"{entity}/{project}"
            if project_key not in ext_to_int_project_cache:
                ext_to_int_project_cache[
                    project_key
                ] = self._id_converter.convert_ext_to_int_project_id(project_key)
            internal_project_id = ext_to_int_project_cache[project_key]
            return f"{ri.WEAVE_INTERNAL_SCHEME}:///{internal_project_id}/{tail}"

        def mapper(obj: t.Any) -> t.Any:
            if isinstance(obj, str) and obj.startswith(weave_prefix):
                return replace_ref(obj)
            return obj

        return _map_values(obj, mapper)

    def _universal_int_to_ext_ref_converter(
        self,
        obj: t.Any,
    ) -> t.Any:
        int_to_ext_project_cache: t.Dict[str, str] = {}

        weave_internal_prefix = ri.WEAVE_INTERNAL_SCHEME + ":///"

        def replace_ref(ref_str: str) -> str:
            if not ref_str.startswith(weave_internal_prefix):
                raise ValueError(f"Invalid URI: {ref_str}")
            rest = ref_str[len(weave_internal_prefix) :]
            parts = rest.split("/", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid URI: {ref_str}")
            project_id, tail = parts
            if project_id not in int_to_ext_project_cache:
                int_to_ext_project_cache[
                    project_id
                ] = self._id_converter.convert_int_to_ext_project_id(project_id)
            external_project_id = int_to_ext_project_cache[project_id]
            return f"{ri.WEAVE_SCHEME}:///{external_project_id}/{tail}"

        def mapper(obj: t.Any) -> t.Any:
            if isinstance(obj, str) and obj.startswith(weave_internal_prefix):
                return replace_ref(obj)
            return obj

        return _map_values(obj, mapper)


def _map_values(obj: t.Any, func: t.Callable[[t.Any], t.Any]) -> t.Any:
    if isinstance(obj, BaseModel):
        # `by_alias` is required since we have Mongo-style properties in the
        # query models that are aliased to conform to start with `$`. Without
        # this, the model_dump will use the internal property names which are
        # not valid for the `model_validate` step.
        orig = obj.model_dump(by_alias=True)
        new = _map_values(orig, func)
        return obj.model_validate(new)
    if isinstance(obj, dict):
        return {k: _map_values(v, func) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_map_values(v, func) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_map_values(v, func) for v in obj)
    if isinstance(obj, set):
        return {_map_values(v, func) for v in obj}
    return func(obj)
