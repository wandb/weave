# This is an experimental client api used to make requests to the
# Weave Trace Server
import contextlib
import contextvars
import typing

import aiohttp

from weave_query import errors
from weave_query import environment as weave_env
from weave_query import wandb_client_api, engine_trace

from weave_query.context_state import WandbApiContext, _wandb_api_context

tracer = engine_trace.tracer()  # type: ignore

def get_wandb_api_context() -> typing.Optional[WandbApiContext]:
    return _wandb_api_context.get()

class WandbTraceApiAsync:
    def __init__(self) -> None:
        self.connector = aiohttp.TCPConnector(limit=50)
    
    async def query_calls_stream(
            self,
            project_id: str,
            filter: typing.Optional[dict] = None,
            limit: typing.Optional[int] = None,
            offset: typing.Optional[int] = None,
            include_costs: bool = False,
            include_feedback: bool = False,
            **kwargs: typing.Any
        ) -> typing.Any:
            wandb_context = get_wandb_api_context()
            headers = {
                "Accept": "application/jsonl",
                "Content-Type": "application/json"
            }
            auth = None
            
            if wandb_context is not None:
                if wandb_context.headers:
                    headers.update(wandb_context.headers)
                if wandb_context.api_key is not None:
                    auth = aiohttp.BasicAuth("api", wandb_context.api_key)

            api_key_override = kwargs.pop("api_key", None)
            if api_key_override:
                auth = aiohttp.BasicAuth("api", api_key_override)

            url = f"{weave_env.weave_trace_server_url()}/calls/stream_query"
            
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
            
            payload.update(kwargs)

            async with aiohttp.ClientSession(
                connector=self.connector,
                headers=headers,
                auth=auth
            ) as session:
                async with session.post(url, json=payload) as response:
                    response.raise_for_status()
                    return await response.json()

class WandbTraceApiSync:
    def query_calls_stream(
        self,
        project_id: str,
        filter: typing.Optional[dict] = None,
        limit: typing.Optional[int] = None,
        offset: typing.Optional[int] = None,
        include_costs: bool = False,
        include_feedback: bool = False,
        **kwargs: typing.Any
    ) -> typing.Any:
        wandb_context = get_wandb_api_context()
        headers = {
            "Accept": "application/jsonl",
            "Content-Type": "application/json"
        }
        auth = None
        
        if wandb_context is not None:
            if wandb_context.headers:
                headers.update(wandb_context.headers)
            if wandb_context.api_key is not None:
                auth = ( "api", wandb_context.api_key)

        api_key_override = kwargs.pop("api_key", None)
        if api_key_override:
            auth = ("api", api_key_override)

        url = f"{weave_env.wandb_base_url()}/calls/stream_query"
        
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
        
        payload.update(kwargs)

        with aiohttp.ClientSession(
            connector=self.connector,
            headers=headers,
            auth=auth
        ) as session:
            with session.post(url, json=payload) as response:
                response.raise_for_status()
                return response.json()
            
async def get_wandb_api() -> WandbTraceApiAsync:
    return WandbTraceApiAsync()


def get_wandb_api_sync() -> WandbTraceApiSync:
    return WandbTraceApiSync()
