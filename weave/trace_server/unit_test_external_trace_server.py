from . import external_trace_server
from . import clickhouse_trace_server_batched


class DummyIdConverter(external_trace_server.IdConverter):
    def convert_ext_to_int_project_id(self, project_id: str) -> str:
        return "___".join(project_id.split("/"))

    def convert_int_to_ext_project_id(self, project_id: str) -> str:
        return "/".join(project_id.split("___"))

    def convert_ext_to_int_run_id(self, run_id: str) -> str:
        return run_id

    def convert_int_to_ext_run_id(self, run_id: str) -> str:
        return run_id

    def convert_ext_to_int_user_id(self, user_id: str) -> str:
        return user_id

    def convert_int_to_ext_user_id(self, user_id: str) -> str:
        return user_id


def make_local_clickhouse_trace_server() -> external_trace_server.ExternalTraceServer:
    ch_server = clickhouse_trace_server_batched.ClickHouseTraceServer.from_env(
        use_async_insert=False
    )
    return external_trace_server.ExternalTraceServer(ch_server, DummyIdConverter())
