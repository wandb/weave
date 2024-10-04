import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, TypedDict, Union

import weave
from weave.trace.client_context.weave_client import require_weave_client
from weave.trace.op import Op, maybe_unbind_method
from weave.trace.weave_client import Call, make_client_call
from weave.trace_server.trace_server_interface import (
    CallsFilter,
    CallsQueryReq,
    LLMUsageSchema,
    SortBy,
)

logger = logging.Logger(__name__)


class AnonymousModel(weave.Model):
    config: Optional[dict] = None


def log_generation(
    inputs: Optional[dict] = None,  # I wish we could allow an "any" here...
    output: Optional[Any] = None,
    *,
    # Basic Config
    generator_id: str = "generator",
    geneartor_config: Optional[dict] = None,
    parent_call_id: Optional[str] = None,
    display_name: Optional[str] = None,
    # Pre-Start info
    attributes: Optional[dict] = None,  # TODO: Should these be exposed?
    # Start Info
    started_at: Optional[datetime] = None,
    # End Info
    latency_ms: Optional[float] = None,
    ended_at: Optional[datetime] = None,
    llm_token_usage: Optional[dict[str, LLMUsageSchema]] = None,
    exception: Optional[Union[BaseException, str]] = None,
    # Post-End Info
    summmary: Optional[dict] = None,  # TODO: Should these be exposed?
    # TODO: Consider adding a project here so we can create a temo client - similar to "get" in refs.py
) -> Call:
    """
    This is an alternatve mechanism of logging "Calls", which is optmized for the
    specific case of logging "generations" (my new word for predict), which can be used
    completely outside the weave tracing lifecyle. This is useful if you have predictions
    that are generated in some way outside of what can be traced but still want to add that
    data to Weave.

    Base-bones example:

    ```python
    call = log_generation(
        {
            "prompt": "Hello, what is your name?"
        },
        "I am a bot named GPT!"
    )
    ```
    """
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


# class BackfillCallsQuery


# Maybe this should be a convenience off of the CallIter?
def backfill_scores(
    *,
    for_op: Op,
    scorers: list[Op],
    rerun_all: bool = False,
    # all_versions: Optional[bool] = False,
    # Partial of `CallsQueryReq` - consider making this cleaner
    filter: Optional[CallsFilter] = None,
    limit: Optional[int] = 1000,
    offset: Optional[int] = None,
    sort_by: Optional[list[SortBy]] = None,
) -> dict:
    wc = require_weave_client()

    saved_scorers = [
        (scorer, wc._save_op(maybe_unbind_method(scorer))) for scorer in scorers
    ]

    if filter is None:
        filter = CallsFilter()

    op_ref = wc._save_op(maybe_unbind_method(for_op))

    filter.op_names = [op_ref.uri()]  # what if they specified something here?

    stats = {
        "calls_found": 0,
        "cache_hits": 0,
        "score_records": [],
    }
    for raw_call in wc.server.calls_query_stream(
        CallsQueryReq(
            project_id=wc._project_id(),
            filter=filter,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            include_costs=False,
            include_feedback=True,
        )
    ):
        stats["calls_found"] += 1
        call = make_client_call(wc.entity, wc.project, raw_call, wc.server)
        for scorer, scorer_op_ref in saved_scorers:
            # TODO Refeactor to by more dry since apply_scorer is called twice
            if rerun_all:
                existing_call_ref = call.apply_scorer(scorer)
                stats["score_records"].append(
                    {
                        "call_ref": call.ref.uri(),
                        "scorer_ref": scorer_op_ref.uri(),
                        "feedback_id": existing_call_ref,
                    }
                )
            else:
                existing_call_ref = None
                # TODO: Remove magic strings & type this
                # TODO: might need to sort here to ensure we get the latest one.
                for feedback in call.summary["weave"]["feedback"]:
                    if (
                        feedback["feedback_type"] == "score"
                        and feedback.get("payload").get("op_ref") == scorer_op_ref
                    ):
                        existing_call_ref = feedback.get("payload").get("call_ref")
                        break
                if existing_call_ref is None:
                    existing_call_ref = call.apply_scorer(scorer)
                    stats["score_records"].append(
                        {
                            "call_ref": call.ref.uri(),
                            "scorer_ref": scorer_op_ref.uri(),
                            "feedback_id": existing_call_ref,
                        }
                    )
                else:
                    stats["cache_hits"] += 1

    return stats


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
