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
from weave_query import wandb_client_api, engine_trace

from weave_query.context_state import WandbApiContext, _wandb_api_context

tracer = engine_trace.tracer()  # type: ignore

def get_wandb_api_context() -> typing.Optional[WandbApiContext]:
    return _wandb_api_context.get()

# todo(dom): Figure out how to use this async client API within ops.
class WandbTraceApiAsync:
    def __init__(self) -> None:
        self.connector = aiohttp.TCPConnector(limit=50)
    
    async def query_calls_stream(
            self,
            project_id: str,
            filter: typing.Optional[dict] = None,
            limit: typing.Optional[int] = None,
            offset: typing.Optional[int] = None,
            sort_by: typing.Optional[list] = None,
            include_costs: bool = False,
            include_feedback: bool = False,
            **kwargs: typing.Any
        ) -> typing.AsyncIterator[dict]:
            wandb_context = get_wandb_api_context()
            headers = {'content-type: application/json'}
            auth = None
            
            if wandb_context is not None:
                if wandb_context.headers:
                    headers.update(wandb_context.headers)
                if wandb_context.api_key is not None:
                    auth = aiohttp.BasicAuth("api", wandb_context.api_key)

            api_key_override = kwargs.pop("api_key", None)
            if api_key_override:
                auth = aiohttp.BasicAuth("api", api_key_override)

            # todo(dom): Add env var support instead of hardcoding
            # url = f"{weave_env.weave_trace_server_url()}/calls/stream_query"
            url = "http://127.0.0.1:6345/calls/stream_query"
            
            payload = {
                "project_id": project_id,
                "include_costs": include_costs,
                "include_feedback": include_feedback,
            }
            
            if filter:
                payload["filter"] = filter
            if limit:
                payload["limit"] = limit
            if offset:
                payload["offset"] = offset
            if sort_by:
                payload["sort_by"] = sort_by
            
            payload.update(kwargs)

            async with aiohttp.ClientSession(
                connector=self.connector,
                headers=headers,
            ) as session:
                async with session.post(url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.content:
                        if line:
                            decoded_line = line.decode('utf-8').strip()
                            if decoded_line:
                                yield json.loads(decoded_line)

class WandbTraceApiSync:
    def query_calls_stream(
        self,
        project_id: str,
        filter: typing.Optional[dict] = None,
        limit: typing.Optional[int] = None,
        offset: typing.Optional[int] = None,
        sort_by: typing.Optional[list] = None,
        include_costs: bool = False,
        include_feedback: bool = False,
        **kwargs: typing.Any
    ) -> typing.Any:
        wandb_context = get_wandb_api_context()
        headers = {}
        
        if wandb_context is not None:
            if wandb_context.headers:
                headers.update(wandb_context.headers)
                headers["authorization"] = "Basic Og=="
            if wandb_context.api_key is not None:
                auth = ("api", wandb_context.api_key)

        api_key_override = kwargs.pop("api_key", None)
        if api_key_override:
            auth = ("api", api_key_override)

        # todo(dom): Add env var support instead of hardcoding
        # url = f"https://trace_server.wandb.test/calls/stream_query"
        url = "http://127.0.0.1:6345/calls/stream_query"
        
        payload = {
            "project_id": project_id,
            "include_costs": include_costs,
            "include_feedback": include_feedback,
        }
        
        if filter:
            payload["filter"] = filter
        if limit:
            payload["limit"] = limit
        if offset:
            payload["offset"] = offset
        if sort_by:
            payload["sort_by"] = sort_by
        
        payload.update(kwargs)

        # todo(dom): Figure out a way to specify the auth kwarg with it
        # causing a 403 error when it is None (when using the authorization header)
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            stream=True
        )
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                yield json.loads(line.decode('utf-8'))

async def get_wandb_trace_api() -> WandbTraceApiAsync:
    return WandbTraceApiAsync()

def get_wandb_trace_api_sync() -> WandbTraceApiSync:
    return WandbTraceApiSync()
