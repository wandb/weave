"""
Weave Log is a direct API for logging calls without a tracing framework.

It also exposes similar functionality for working with evaluations.
"""

from __future__ import annotations

# from datetime import datetime
from typing import TYPE_CHECKING, Any

from weave.trace.context.weave_client_context import require_weave_client

if TYPE_CHECKING:
    from weave.trace.weave_client import Call

"""
Variations to consider:
* Binding to a model (self arg)
* Children Calls
* Context Managers
* Ability to pass in parent object OR parent/trance id

Problems:
* Specifying summary
* Specifying model usage
"""


def log(
    *,
    name: str | None = None,
    # display_name: str | None = None,
    # trace_id: str | None = None,
    # parent_id: str | None = None,
    parent_call: Call | None = None,
    # started_at: datetime | None = None,
    attributes: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
    # ended_at: datetime | None = None,
    output: Any | None = None,
    exception: BaseException | None = None,
    # summary: str | None = None,
    auto_finish: bool = True,
) -> Call:
    wc = require_weave_client()

    # Defaults:
    if name is None:
        name = "anonymous"
    if inputs is None:
        inputs = {}
    if attributes is None:
        attributes = {}
    # if summary is None:
    #     summary = {}

    call = wc.create_call(
        op=name, parent=parent_call, inputs=inputs, attributes=attributes
    )
    if auto_finish:
        wc.finish_call(
            call,
            output=output,
            #    summary=summary,
            exception=exception,
        )
    return call
