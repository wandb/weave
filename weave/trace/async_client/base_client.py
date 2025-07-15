"""Base async client classes for Weave, following OpenAI's architecture pattern."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar, Union

import httpx
from pydantic import BaseModel

if TYPE_CHECKING:
    from weave.trace_server import trace_server_interface as tsi

T = TypeVar("T")
ResponseT = TypeVar("ResponseT", bound=BaseModel)


class BaseClient(ABC, Generic[T]):
    """Base client class for both sync and async implementations."""

    _client: T
    _base_url: str
    _auth: Optional[tuple[str, str]]
    _extra_headers: Optional[dict[str, str]]
    _timeout: Union[float, httpx.Timeout]

    @abstractmethod
    def _make_request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """Make an HTTP request."""
        ...

    @abstractmethod
    def _process_response(self, response: httpx.Response) -> Any:
        """Process HTTP response."""
        ...


class SyncAPIClient(BaseClient[httpx.Client]):
    """Synchronous API client using httpx."""

    def __init__(
        self,
        base_url: str,
        *,
        auth: Optional[tuple[str, str]] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: Union[float, httpx.Timeout] = httpx.Timeout(timeout=60.0),
    ):
        self._base_url = base_url
        self._auth = auth
        self._extra_headers = extra_headers or {}
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=base_url,
            auth=auth,
            headers=self._extra_headers,
            timeout=timeout,
        )

    def _make_request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """Make a synchronous HTTP request."""
        request_headers = {**self._extra_headers}
        if headers:
            request_headers.update(headers)

        response = self._client.request(
            method=method,
            url=url,
            params=params,
            json=json,
            files=files,
            headers=request_headers,
        )
        response.raise_for_status()
        return response

    def _process_response(self, response: httpx.Response) -> Any:
        """Process HTTP response."""
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.content

    def get(self, url: str, **kwargs: Any) -> Any:
        """Make a GET request."""
        response = self._make_request("GET", url, **kwargs)
        return self._process_response(response)

    def post(self, url: str, **kwargs: Any) -> Any:
        """Make a POST request."""
        response = self._make_request("POST", url, **kwargs)
        return self._process_response(response)

    def put(self, url: str, **kwargs: Any) -> Any:
        """Make a PUT request."""
        response = self._make_request("PUT", url, **kwargs)
        return self._process_response(response)

    def delete(self, url: str, **kwargs: Any) -> Any:
        """Make a DELETE request."""
        response = self._make_request("DELETE", url, **kwargs)
        return self._process_response(response)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> SyncAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncAPIClient(BaseClient[httpx.AsyncClient]):
    """Asynchronous API client using httpx."""

    def __init__(
        self,
        base_url: str,
        *,
        auth: Optional[tuple[str, str]] = None,
        extra_headers: Optional[dict[str, str]] = None,
        timeout: Union[float, httpx.Timeout] = httpx.Timeout(timeout=60.0),
    ):
        self._base_url = base_url
        self._auth = auth
        self._extra_headers = extra_headers or {}
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=base_url,
            auth=auth,
            headers=self._extra_headers,
            timeout=timeout,
        )

    async def _make_request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """Make an asynchronous HTTP request."""
        request_headers = {**self._extra_headers}
        if headers:
            request_headers.update(headers)

        response = await self._client.request(
            method=method,
            url=url,
            params=params,
            json=json,
            files=files,
            headers=request_headers,
        )
        response.raise_for_status()
        return response

    async def _process_response(self, response: httpx.Response) -> Any:
        """Process HTTP response."""
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.content

    async def get(self, url: str, **kwargs: Any) -> Any:
        """Make a GET request."""
        response = await self._make_request("GET", url, **kwargs)
        return await self._process_response(response)

    async def post(self, url: str, **kwargs: Any) -> Any:
        """Make a POST request."""
        response = await self._make_request("POST", url, **kwargs)
        return await self._process_response(response)

    async def put(self, url: str, **kwargs: Any) -> Any:
        """Make a PUT request."""
        response = await self._make_request("PUT", url, **kwargs)
        return await self._process_response(response)

    async def delete(self, url: str, **kwargs: Any) -> Any:
        """Make a DELETE request."""
        response = await self._make_request("DELETE", url, **kwargs)
        return await self._process_response(response)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncAPIClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()