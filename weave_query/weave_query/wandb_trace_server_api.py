# This is an experimental client api used to make requests to the
# Weave Trace Server
import typing
import requests
import json
from requests.auth import HTTPBasicAuth

from weave_query import environment as weave_env
from weave_query import engine_trace, server_error_handling

from weave_query.context_state import WandbApiContext, _wandb_api_context

tracer = engine_trace.tracer()  # type: ignore

def _get_wandb_api_context() -> typing.Optional[WandbApiContext]:
    return _wandb_api_context.get()

class WandbTraceApi:
    def __init__(self) -> None:
        self.session = requests.Session()

    def query_calls_stream(
        self,
        project_id: str,
        filter: typing.Optional[dict] = None,
        limit: typing.Optional[int] = None,
        offset: typing.Optional[int] = None,
        sort_by: typing.Optional[list] = None,
        query: typing.Optional[dict] = None,
    ) -> typing.Any:
        with tracer.trace("query_calls_stream"):
            wandb_api_context = _get_wandb_api_context()
            headers = {'content-type': 'application/json'}
            auth = None
            cookies = None
            if wandb_api_context is not None:
                headers = wandb_api_context.headers
                cookies = wandb_api_context.cookies
                if wandb_api_context.api_key is not None:
                    auth = HTTPBasicAuth("api", wandb_api_context.api_key)
                if cookies:
                    headers["authorization"] = "Basic Og==" # base64 encoding of ":"

            url = f"{weave_env.weave_trace_server_url()}/calls/stream_query"
            
            payload = {
                "project_id": project_id,
            }
            
            if filter:
                payload["filter"] = filter
            if limit:
                payload["limit"] = limit
            if offset:
                payload["offset"] = offset
            if sort_by:
                payload["sort_by"] = sort_by
            if query:
                payload["query"] = query
            
            with self.session.post(
                url=url, headers=headers, auth=auth, cookies=cookies, json=payload
            ) as r:
                results = []
                if r.status_code == 200:
                    for line in r.iter_lines():
                        if line:
                            results.append(json.loads(line))
                    return results
                else:
                    raise server_error_handling.WeaveInternalHttpException.from_code(r.status_code, "Weave Traces query failed")
                
def get_wandb_trace_api() -> WandbTraceApi:
    return WandbTraceApi()