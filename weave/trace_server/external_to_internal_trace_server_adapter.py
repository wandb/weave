import abc
import types
import typing
from collections.abc import Callable, Iterator
from typing import ClassVar, TypeVar, cast

from pydantic import BaseModel

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_server_converter import (
    universal_ext_to_int_ref_converter,
    universal_int_to_ext_ref_converter,
)


class IdConverter:
    @abc.abstractmethod
    def ext_to_int_project_id(self, project_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def int_to_ext_project_id(self, project_id: str) -> str | None:
        raise NotImplementedError()

    @abc.abstractmethod
    def ext_to_int_run_id(self, run_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def int_to_ext_run_id(self, run_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def ext_to_int_user_id(self, user_id: str) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def int_to_ext_user_id(self, user_id: str) -> str:
        raise NotImplementedError()


A = TypeVar("A")
B = TypeVar("B")


class ExternalTraceServer(tsi.FullTraceServerInterface):
    """Used to adapt the internal trace server to the external trace server.
    This is done by converting the project_id, run_id, and user_id to their
    internal representations before calling the internal trace server and
    converting them back to their external representations before returning
    them to the caller. Additionally, we convert references to their internal
    representations before calling the internal trace server and convert them
    back to their external representations before returning them to the caller.
    """

    _internal_trace_server: tsi.FullTraceServerInterface
    _idc: IdConverter

    def __init__(
        self,
        internal_trace_server: tsi.FullTraceServerInterface,
        id_converter: IdConverter,
    ):
        super().__init__()
        self._internal_trace_server = internal_trace_server
        self._idc = id_converter

    _STREAM_METHOD_SUFFIXES: ClassVar[tuple[str, ...]] = ("_stream", "_list")
    _AUTO_SKIP_REF_METHODS: ClassVar[set[str]] = {
        "file_create",
        "file_content_read",
    }
    _AUTO_STRICT_PROJECT_METHODS: ClassVar[set[str]] = {
        "call_read",
        "calls_query",
        "calls_query_stream",
        "obj_read",
        "objs_query",
    }

    def __getattribute__(self, name: str) -> typing.Any:
        if name.startswith("_"):
            return object.__getattribute__(self, name)

        attr = object.__getattribute__(self, name)
        if isinstance(attr, types.MethodType):
            func = attr.__func__
            if func.__module__ == "weave.trace_server.trace_server_interface":
                return object.__getattribute__(self, "__getattr__")(name)
        return attr

    def __getattr__(self, name: str) -> typing.Any:
        attr = getattr(self._internal_trace_server, name)
        if not callable(attr):
            return attr

        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            req: BaseModel | None = None
            if len(args) == 1 and not kwargs and isinstance(args[0], BaseModel):
                req = args[0]
            elif not args and len(kwargs) == 1:
                sole_value = next(iter(kwargs.values()))
                if isinstance(sole_value, BaseModel):
                    req = sole_value
            if req is not None:
                stream = name.endswith(self._STREAM_METHOD_SUFFIXES)
                convert_refs = name not in self._AUTO_SKIP_REF_METHODS
                strict_project_match = name in self._AUTO_STRICT_PROJECT_METHODS
                if stream:
                    return self._auto_forward(
                        attr,
                        req,
                        stream=True,
                        convert_refs=convert_refs,
                        strict_project_match=strict_project_match,
                    )
                return self._auto_forward(
                    attr,
                    req,
                    stream=False,
                    convert_refs=convert_refs,
                    strict_project_match=strict_project_match,
                )
            return attr(*args, **kwargs)

        return wrapper

    def _convert_ids(
        self,
        value: typing.Any,
        *,
        project_id_converter: Callable[[str], str],
        run_id_converter: Callable[[str], str],
        user_id_converter: Callable[[str], str],
    ) -> None:
        if isinstance(value, BaseModel):
            for field_name in value.model_fields:
                field_value = getattr(value, field_name)
                if field_name == "project_id" and isinstance(field_value, str):
                    setattr(value, field_name, project_id_converter(field_value))
                    field_value = getattr(value, field_name)
                elif field_name == "wb_run_id" and field_value is not None:
                    setattr(value, field_name, run_id_converter(field_value))
                    field_value = getattr(value, field_name)
                elif field_name == "wb_user_id" and field_value is not None:
                    setattr(value, field_name, user_id_converter(field_value))
                    field_value = getattr(value, field_name)
                elif field_name == "wb_run_ids" and isinstance(field_value, list):
                    setattr(
                        value,
                        field_name,
                        [run_id_converter(item) for item in field_value],
                    )
                elif field_name == "wb_user_ids" and isinstance(field_value, list):
                    setattr(
                        value,
                        field_name,
                        [user_id_converter(item) for item in field_value],
                    )

                if isinstance(field_value, BaseModel):
                    self._convert_ids(
                        field_value,
                        project_id_converter=project_id_converter,
                        run_id_converter=run_id_converter,
                        user_id_converter=user_id_converter,
                    )
                elif isinstance(field_value, list):
                    for item in field_value:
                        if isinstance(item, BaseModel):
                            self._convert_ids(
                                item,
                                project_id_converter=project_id_converter,
                                run_id_converter=run_id_converter,
                                user_id_converter=user_id_converter,
                            )
                elif isinstance(field_value, tuple):
                    for item in field_value:
                        if isinstance(item, BaseModel):
                            self._convert_ids(
                                item,
                                project_id_converter=project_id_converter,
                                run_id_converter=run_id_converter,
                                user_id_converter=user_id_converter,
                            )
                elif isinstance(field_value, set):
                    for item in field_value:
                        if isinstance(item, BaseModel):
                            self._convert_ids(
                                item,
                                project_id_converter=project_id_converter,
                                run_id_converter=run_id_converter,
                                user_id_converter=user_id_converter,
                            )
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                if isinstance(item, BaseModel):
                    self._convert_ids(
                        item,
                        project_id_converter=project_id_converter,
                        run_id_converter=run_id_converter,
                        user_id_converter=user_id_converter,
                    )

    def _convert_request_ids(self, req: BaseModel) -> dict[str, str]:
        project_id_map: dict[str, str] = {}

        def convert_project_id(project_id: str) -> str:
            internal_id = self._idc.ext_to_int_project_id(project_id)
            project_id_map[internal_id] = project_id
            return internal_id

        self._convert_ids(
            req,
            project_id_converter=convert_project_id,
            run_id_converter=self._idc.ext_to_int_run_id,
            user_id_converter=self._idc.ext_to_int_user_id,
        )
        return project_id_map

    def _convert_response_ids(
        self,
        res: typing.Any,
        *,
        project_id_map: dict[str, str],
        strict_project_match: bool = False,
    ) -> None:
        def convert_project_id(project_id: str) -> str:
            if project_id in project_id_map:
                return project_id_map[project_id]
            if strict_project_match and project_id_map:
                raise ValueError("Internal Error - Project Mismatch")
            external_id = self._idc.int_to_ext_project_id(project_id)
            return external_id if external_id is not None else project_id

        self._convert_ids(
            res,
            project_id_converter=convert_project_id,
            run_id_converter=self._idc.int_to_ext_run_id,
            user_id_converter=self._idc.int_to_ext_user_id,
        )

    def _prepare_request(
        self, req: A, *, convert_refs: bool = True
    ) -> tuple[A, dict[str, str]]:
        project_id_map: dict[str, str] = {}
        if isinstance(req, BaseModel):
            project_id_map = self._convert_request_ids(req)
            if convert_refs:
                req = universal_ext_to_int_ref_converter(
                    req, self._idc.ext_to_int_project_id
                )
        return req, project_id_map

    def _finalize_response(
        self,
        res: B,
        *,
        project_id_map: dict[str, str],
        convert_refs: bool = True,
        strict_project_match: bool = False,
    ) -> B:
        if convert_refs:
            res = universal_int_to_ext_ref_converter(
                res, self._idc.int_to_ext_project_id
            )
        self._convert_response_ids(
            res,
            project_id_map=project_id_map,
            strict_project_match=strict_project_match,
        )
        return res

    def _finalize_stream_response(
        self,
        res: Iterator[B],
        *,
        project_id_map: dict[str, str],
        convert_refs: bool = True,
        strict_project_match: bool = False,
    ) -> Iterator[B]:
        int_to_ext_project_cache: dict[str, str | None] = {}

        def cached_int_to_ext_project_id(project_id: str) -> str | None:
            if project_id not in int_to_ext_project_cache:
                int_to_ext_project_cache[project_id] = self._idc.int_to_ext_project_id(
                    project_id
                )
            return int_to_ext_project_cache[project_id]

        for item in res:
            if convert_refs:
                item = universal_int_to_ext_ref_converter(
                    item, cached_int_to_ext_project_id
                )
            self._convert_response_ids(
                item,
                project_id_map=project_id_map,
                strict_project_match=strict_project_match,
            )
            yield item

    @typing.overload
    def _auto_forward(
        self,
        method: Callable[[A], Iterator[B]],
        req: A,
        *,
        stream: typing.Literal[True],
        convert_refs: bool = True,
        strict_project_match: bool = False,
    ) -> Iterator[B]: ...

    @typing.overload
    def _auto_forward(
        self,
        method: Callable[[A], B],
        req: A,
        *,
        stream: typing.Literal[False] = False,
        convert_refs: bool = True,
        strict_project_match: bool = False,
    ) -> B: ...

    def _auto_forward(
        self,
        method: Callable[[A], typing.Any],
        req: A,
        *,
        stream: bool = False,
        convert_refs: bool = True,
        strict_project_match: bool = False,
    ) -> typing.Any:
        req_conv, project_id_map = self._prepare_request(req, convert_refs=convert_refs)
        res = method(req_conv)
        if stream:
            return self._finalize_stream_response(
                cast(Iterator[B], res),
                project_id_map=project_id_map,
                convert_refs=convert_refs,
                strict_project_match=strict_project_match,
            )
        return self._finalize_response(
            cast(B, res),
            project_id_map=project_id_map,
            convert_refs=convert_refs,
            strict_project_match=strict_project_match,
        )

    # Standard API Below:
    # Default behavior is handled by __getattr__ + _auto_forward.
    # Only special-case endpoints are defined explicitly here.

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        original_user_id = req.wb_user_id
        if original_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        res = self._auto_forward(self._internal_trace_server.feedback_create, req)
        if res.wb_user_id != original_user_id:
            raise ValueError("Internal Error - User Mismatch")
        res.wb_user_id = original_user_id
        return res

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        original_project_id = req.project_id
        req_conv, project_id_map = self._prepare_request(req)
        # TODO: How to handle wb_user_id and wb_run_id in the query filters?
        res = self._internal_trace_server.feedback_query(req_conv)
        res = self._finalize_response(res, project_id_map=project_id_map)
        for feedback in res.result:
            if "project_id" in feedback:
                if feedback["project_id"] != req_conv.project_id:
                    raise ValueError("Internal Error - Project Mismatch")
                feedback["project_id"] = original_project_id
            if "wb_user_id" in feedback and feedback["wb_user_id"] is not None:
                feedback["wb_user_id"] = self._idc.int_to_ext_user_id(
                    feedback["wb_user_id"]
                )
        return res

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        original_user_id = req.wb_user_id
        if original_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        res = self._auto_forward(self._internal_trace_server.feedback_replace, req)
        if res.wb_user_id != original_user_id:
            raise ValueError("Internal Error - User Mismatch")
        res.wb_user_id = original_user_id
        return res

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        original_project_id = req.project_id
        req_conv, project_id_map = self._prepare_request(req)
        res = self._internal_trace_server.cost_query(req_conv)
        res = self._finalize_response(res, project_id_map=project_id_map)
        # Extend this to account for ORG ID when org level costs are implemented
        for cost in res.results:
            if "pricing_level_id" in cost:
                if cost["pricing_level_id"] != req_conv.project_id:
                    raise ValueError("Internal Error - Project Mismatch")
                cost["pricing_level_id"] = original_project_id
        return res

    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        if req.wb_user_id is None:
            raise ValueError("wb_user_id cannot be None")
        return self._auto_forward(
            self._internal_trace_server.actions_execute_batch, req
        )

    def completions_create_stream(
        self, req: tsi.CompletionsCreateReq
    ) -> typing.Iterator[dict[str, typing.Any]]:
        # Convert IDs and any refs in the request (e.g., prompt) to internal format.
        req_conv, _ = self._prepare_request(req)
        # The streamed chunks contain no project-scoped references, so we can
        # forward directly without additional ref conversion.
        return self._internal_trace_server.completions_create_stream(req_conv)
