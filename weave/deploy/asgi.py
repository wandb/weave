import asyncio
from dataclasses import dataclass

from flask import Request, Response, make_response
from mangum.protocols import HTTPCycle
from mangum.types import ASGI


@dataclass(slots=True)
class GcpMangum:
    """
    Wrapper to allow GCP Cloud Functions' HTTP (Flask) events to interact with ASGI frameworks
    Offloads internals to Mangum while acting as a wrapper for flask compatability
    """

    app: ASGI

    def __call__(self, request: Request) -> Response:
        try:
            return self.asgi(request)
        except BaseException as e:
            raise e

    def asgi(self, request: Request) -> Response:
        environ = request.environ
        scope = {
            "type": "http",
            "server": (environ["SERVER_NAME"], environ["SERVER_PORT"]),
            "client": environ["REMOTE_ADDR"],
            "method": request.method,
            "path": request.path,
            "scheme": request.scheme,
            "http_version": "1.1",
            "root_path": "",
            "query_string": request.query_string,
            "headers": [[k.encode(), v.encode()] for k, v in request.headers],
        }
        request_body = request.data or b""

        http_cycle = HTTPCycle(scope, request_body)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        http_response = http_cycle(self.app)
        return make_response(http_response["body"], http_response["status"], http_response["headers"])
