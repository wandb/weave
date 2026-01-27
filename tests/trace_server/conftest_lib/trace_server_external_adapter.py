import base64
import functools
import typing

from pydantic import BaseModel

from weave.trace_server import (
    external_to_internal_trace_server_adapter,
)
from weave.trace_server import trace_server_interface as tsi


class TwoWayMapping:
    def __init__(self):
        self._ext_to_int_map = {}
        self._int_to_ext_map = {}

        # Useful for testing to ensure caching is working
        self.stats = {
            "ext_to_int": {
                "hits": 0,
                "misses": 0,
            },
            "int_to_ext": {
                "hits": 0,
                "misses": 0,
            },
        }

    def ext_to_int(self, key, default=None):
        if key not in self._ext_to_int_map:
            if default is None:
                raise ValueError(f"Key {key} not found")
            if default in self._int_to_ext_map:
                raise ValueError(f"Default {default} already in use")
            self._ext_to_int_map[key] = default
            self._int_to_ext_map[default] = key
            self.stats["ext_to_int"]["misses"] += 1
        else:
            self.stats["ext_to_int"]["hits"] += 1
        return self._ext_to_int_map[key]

    def int_to_ext(self, key, default):
        if key not in self._int_to_ext_map:
            if default is None:
                raise ValueError(f"Key {key} not found")
            if default in self._ext_to_int_map:
                raise ValueError(f"Default {default} already in use")
            self._int_to_ext_map[key] = default
            self._ext_to_int_map[default] = key
            self.stats["int_to_ext"]["misses"] += 1
        else:
            self.stats["int_to_ext"]["hits"] += 1
        return self._int_to_ext_map[key]


def b64(s: str) -> str:
    # Base64 encode the string
    return base64.b64encode(s.encode("ascii")).decode("ascii")


class DummyIdConverter(external_to_internal_trace_server_adapter.IdConverter):
    def __init__(self):
        self._project_map = TwoWayMapping()
        self._run_map = TwoWayMapping()
        self._user_map = TwoWayMapping()

    def ext_to_int_project_id(self, project_id: str) -> str:
        return self._project_map.ext_to_int(project_id, b64(project_id))

    def int_to_ext_project_id(self, project_id: str) -> str | None:
        return self._project_map.int_to_ext(project_id, b64(project_id))

    def ext_to_int_run_id(self, run_id: str) -> str:
        return self._run_map.ext_to_int(run_id, b64(run_id) + ":" + run_id)

    def int_to_ext_run_id(self, run_id: str) -> str:
        exp = run_id.split(":")[1]
        return self._run_map.int_to_ext(run_id, exp)

    def ext_to_int_user_id(self, user_id: str) -> str:
        return self._user_map.ext_to_int(user_id, b64(user_id))

    def int_to_ext_user_id(self, user_id: str) -> str:
        return self._user_map.int_to_ext(user_id, b64(user_id))


class TestOnlyUserInjectingExternalTraceServer(
    external_to_internal_trace_server_adapter.ExternalTraceServer
):
    def __init__(
        self,
        internal_trace_server: tsi.TraceServerInterface,
        id_converter: external_to_internal_trace_server_adapter.IdConverter,
        user_id: str,
    ):
        super().__init__(internal_trace_server, id_converter)
        self._user_id = user_id

    def __getattribute__(self, name: str) -> typing.Any:
        attr = super().__getattribute__(name)
        if name.startswith("_") or not callable(attr):
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
                self._inject_user_id(req)
            return attr(*args, **kwargs)

        return functools.wraps(attr)(wrapper)

    def _inject_user_id(self, value: typing.Any) -> None:
        if isinstance(value, BaseModel):
            for field_name in value.model_fields:
                field_value = getattr(value, field_name)
                if field_name == "wb_user_id":
                    setattr(value, field_name, self._user_id)
                    field_value = getattr(value, field_name)
                if isinstance(field_value, BaseModel):
                    self._inject_user_id(field_value)
                elif isinstance(field_value, dict):
                    for item in field_value.values():
                        if isinstance(item, BaseModel):
                            self._inject_user_id(item)
                elif isinstance(field_value, (list, tuple, set)):
                    for item in field_value:
                        if isinstance(item, BaseModel):
                            self._inject_user_id(item)
        elif isinstance(value, dict):
            for item in value.values():
                if isinstance(item, BaseModel):
                    self._inject_user_id(item)


def externalize_trace_server(
    trace_server: tsi.TraceServerInterface,
    user_id: str = "test_user",
    id_converter: external_to_internal_trace_server_adapter.IdConverter | None = None,
) -> TestOnlyUserInjectingExternalTraceServer:
    return TestOnlyUserInjectingExternalTraceServer(
        trace_server,
        id_converter or DummyIdConverter(),
        user_id,
    )
