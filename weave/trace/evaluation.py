import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, TypedDict, Union

from responses import Call

import weave
from weave.trace.client_context.weave_client import require_weave_client
from weave.trace.refs import parse_op_uri
from weave.trace_server.trace_server_interface import LLMUsageSchema

logger = logging.logger(__name__)


class AnonymousModel(weave.Model):
    config: Optional[dict] = None


def log_generation(
    *,
    # Basic Config
    generator_id: str = "generator",
    geneartor_config: Optional[dict] = None,
    parent_call_id: Optional[str] = None,
    display_name: Optional[str] = None,
    # Pre-Start info
    attributes: Optional[dict] = None,  # TODO: Should these be exposed?
    # Start Info
    inputs: Optional[dict] = None,
    started_at: Optional[datetime] = None,
    # End Info
    latency_ms: Optional[float] = None,
    ended_at: Optional[datetime] = None,
    output: Optional[Any] = None,
    llm_token_usage: Optional[dict[str, LLMUsageSchema]] = None,
    exception: Optional[Union[BaseException, str]] = None,
    # Post-End Info
    summmary: Optional[dict] = None,  # TODO: Should these be exposed?
    # Scoring Info
    # TODO: Add me
) -> Call:
    wc = require_weave_client()

    # First we build the inputs:
    if inputs is None:
        inputs = {}

    # Next, we create a Model if a config exists:
    if geneartor_config is not None:
        # Safetey check:
        if "self" in inputs:
            raise ValueError(
                "inputs['self'] and generator_config cannot both be specified"
            )
        inputs["self"] = AnonymousModel(geneartor_config)

    # Next, let's resolve the timestamps
    timestamps = _resolve_timestamps(
        started_at,
        latency_ms,
        ended_at,
    )

    # I don't like this lookup here, but we need
    # the trace_id...
    parent_call = None
    if parent_call_id is not None:
        parent_call = wc.get_call(parent_call)

    call = wc.create_call(
        op=generator_id,
        inputs=inputs,
        parent=parent_call,
        attributes=attributes,
        display_name=display_name,
        started_at=timestamps["started_at"],
        use_stack=False,
    )

    if isinstance(exception, str):
        exception = Exception(exception)

    wc.finish_call(
        call=call,
        output=output,
        exception=exception,
        llm_token_usage=llm_token_usage,
        summmary=summmary,
    )

    return call


def _determine_op_ref(maybe_op_ref):
    if not maybe_op_ref.startswith("weave:///"):
        return None
    else:
        return parse_op_uri(maybe_op_ref)


class _ResolveTimestampsReturnType(TypedDict):
    started_at: datetime
    ended_at: datetime


def _resolve_timestamps(
    started_at: Optional[datetime] = None,
    latency_ms: Optional[float] = None,
    ended_at: Optional[datetime] = None,
) -> _ResolveTimestampsReturnType:
    now = datetime.now(tz=timezone.utc)

    # All Specified
    if started_at is not None and latency_ms is not None and ended_at is not None:
        logger.warn(
            "Should not specify all 3 of started_at, latency_ms, and ended_at, ignoring latency"
        )
        return {"started_at": started_at, "ended_at": ended_at}

    # None Specified
    if started_at is None and latency_ms is None and ended_at is None:
        return {"started_at": now, "ended_at": now}

    # Singular Specified - started_at
    if started_at is not None and latency_ms is None and ended_at is None:
        return {"started_at": started_at, "ended_at": started_at}

    # Singular Specified - ended_at
    if started_at is None and latency_ms is None and ended_at is not None:
        return {"started_at": ended_at, "ended_at": ended_at}

    # Singular Specified - latency_ms
    if started_at is None and latency_ms is not None and ended_at is None:
        ended_at = now
        started_at = ended_at - timedelta(milliseconds=latency_ms)
        return {"started_at": ended_at, "ended_at": ended_at}

    # Dual Specified - started_at & ended_at
    if started_at is not None and latency_ms is None and ended_at is not None:
        return {"started_at": started_at, "ended_at": ended_at}

    # Dual Specified - started_at & latency_ms
    if started_at is not None and latency_ms is not None and ended_at is None:
        ended_at = started_at + timedelta(milliseconds=latency_ms)
        return {"started_at": started_at, "ended_at": ended_at}

    # Dual Specified - ended_at & latency_ms
    if started_at is None and latency_ms is not None and ended_at is not None:
        started_at = ended_at - timedelta(milliseconds=latency_ms)
        return {"started_at": started_at, "ended_at": ended_at}

    raise Exception("Programming error - all cases not considered")
