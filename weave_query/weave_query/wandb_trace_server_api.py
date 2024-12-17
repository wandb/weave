# This is an experimental client api used to make requests to the
# Weave Trace Server
import contextlib
import contextvars
import typing
import json

import aiohttp
import requests

from weave_query import errors
from weave_query import environment as weave_env
from weave_query import wandb_client_api, engine_trace, weave_http

from weave_query.context_state import WandbApiContext, _wandb_api_context

tracer = engine_trace.tracer()  # type: ignore

def get_wandb_api_context() -> typing.Optional[WandbApiContext]:
    return _wandb_api_context.get()

class WandbTraceApiAsync:
    def __init__(self, http: weave_http.HttpAsync) -> None:
        self.http = http

    async def query_calls_stream(
            self,
            project_id: str,
            filter: typing.Optional[dict] = None,
            limit: typing.Optional[int] = None,
            offset: typing.Optional[int] = None,
            sort_by: typing.Optional[list] = None,
            query: typing.Optional[dict] = None,
        ) -> typing.List[dict]:
            wandb_api_context = get_wandb_api_context()
            headers = {'content-type': 'application/json'}
            auth = None
            cookies = None
            if wandb_api_context is not None:
                headers = wandb_api_context.headers
                cookies = wandb_api_context.cookies
                if wandb_api_context.api_key is not None:
                    auth = aiohttp.BasicAuth("api", wandb_api_context.api_key)
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
            
            return await self.http.query_traces(url, payload, headers=headers, cookies=cookies, auth=auth)

class WandbTraceApiSync:
    def query_calls_stream(
        self,
        project_id: str,
        filter: typing.Optional[dict] = None,
        limit: typing.Optional[int] = None,
        offset: typing.Optional[int] = None,
        sort_by: typing.Optional[list] = None,
        query: typing.Optional[dict] = None,
        **kwargs: typing.Any
    ) -> typing.Any:
        wandb_api_context = get_wandb_api_context()
        headers = {'content-type': 'application/json'}
        auth = None
        cookies = None
        if wandb_api_context is not None:
            headers = wandb_api_context.headers
            cookies = wandb_api_context.cookies
            if wandb_api_context.api_key is not None:
                auth = aiohttp.BasicAuth("api", wandb_api_context.api_key)
            if cookies:
                headers["authorization"] = "Basic Og==" # base64 encoding of ":"

        url = f"{weave_env.weave_trace_server_url()}/calls/stream_query"

        api_key_override = kwargs.pop("api_key", None)
        if api_key_override:
            auth = ("api", api_key_override)

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
        
        payload.update(kwargs)

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=auth if auth else None,
            stream=True
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                yield json.loads(line.decode('utf-8'))
