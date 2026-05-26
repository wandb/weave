import httpx
import vcr.stubs.httpx_stubs as _vcr_httpx_stubs
from vcr.filters import decode_response
from vcr.stubs.httpx_stubs import _from_serialized_headers


# vcrpy 7.0.0's `_from_serialized_response` is decorated with
# `@patch("httpx.Response.read", MagicMock())`, which replaces `Response.read`
# at the class level for the duration of the call. That replacement is visible
# to every other thread. crewai's `kickoff_for_each_async` runs each kickoff
# via `asyncio.to_thread`, so two sync OpenAI completions execute on different
# threads; if thread A is mid-replay (class-level mock active) while thread B's
# `httpx.Client.send` runs its post-replay `response.read()`, B's read is a
# no-op and `_content` is never set, so litellm's later `raw_response.parse()`
# trips `httpx.ResponseNotRead`. Manifests on Windows where GIL timing widens
# the window. Upstream: kevin1024/vcrpy#832, #834. Patching is unnecessary --
# `httpx.Response(content=bytes)` populates `_content` via real `read()`.
def _from_serialized_response_threadsafe(request, serialized_response, history=None):
    if "status_code" in serialized_response:
        serialized_response = decode_response(
            cassette_dict={
                "interactions": [
                    {
                        "response": {
                            "headers": serialized_response["headers"],
                            "body": {"string": serialized_response["content"]},
                            "status": {"code": serialized_response["status_code"]},
                        },
                    }
                ]
            },
            serializer=None,
        )["interactions"][0]["response"]
    extensions = None
    if "message" in serialized_response["status"]:
        extensions = {
            "reason_phrase": serialized_response["status"]["message"].encode()
        }
    return httpx.Response(
        status_code=serialized_response["status"]["code"],
        request=request,
        headers=_from_serialized_headers(serialized_response["headers"]),
        content=serialized_response["body"]["string"],
        history=history or [],
        extensions=extensions,
    )


_vcr_httpx_stubs._from_serialized_response = _from_serialized_response_threadsafe
