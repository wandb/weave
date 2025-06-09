import asyncio
import logging
import os
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional, TypedDict

import ddtrace
import sentry_sdk
from confluent_kafka import KafkaError, Message
from tenacity import (
    RetryError,
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

# This import is used to register built-in scorers so they can be deserialized from the DB
import weave.scorers  # noqa: F401
from weave.flow.monitor import Monitor
from weave.flow.scorer import Scorer, preparer_scorer_op_args
from weave.trace.box import box
from weave.trace.objectify import maybe_objectify
from weave.trace.op import _default_on_input_handler
from weave.trace.serialization.serialize import to_json
from weave.trace.weave_client import (
    RUNNABLE_FEEDBACK_TYPE_PREFIX,
    Call,
    FeedbackCreateReq,
    ObjectRef,
    from_json,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.environment import (
    wf_enable_online_eval,
    wf_scoring_worker_batch_size,
    wf_scoring_worker_batch_timeout,
)
from weave.trace_server.kafka import CALL_ENDED_TOPIC, KafkaConsumer
from weave.trace_server.refs_internal import (
    InternalCallRef,
    InternalObjectRef,
    parse_internal_uri,
)

# We add the hostname to differentiate between workers. This will be the pod name in Kubernetes.
hostname = os.environ.get("HOSTNAME", "localhost")
logging.basicConfig(
    level=logging.INFO,
    format=f"%(levelname)s:{hostname}:%(name)s: %(message)s",
)
logger = logging.getLogger("weave.workers.weave_scorer")
logger.setLevel(logging.INFO)


_TRACE_SERVER: Optional[ClickHouseTraceServer] = None


def get_trace_server() -> ClickHouseTraceServer:
    global _TRACE_SERVER

    if _TRACE_SERVER is None:
        _TRACE_SERVER = ClickHouseTraceServer.from_env()

    return _TRACE_SERVER


class ActiveMonitor(TypedDict):
    """Type definition for the output of get_active_monitors."""

    monitor: Monitor
    internal_ref: InternalObjectRef
    wb_user_id: Optional[str]


class MonitorsCache:
    """Cache for active monitors."""

    _cache: OrderedDict[str, tuple[datetime, list[ActiveMonitor]]] = OrderedDict()
    _ttl_seconds = 60
    _capacity = 100

    @classmethod
    def get(cls, project_id: str) -> Optional[list[ActiveMonitor]]:
        if (cached_value := cls._cache.get(project_id)) is not None:
            if cached_value[0] > datetime.now() - timedelta(seconds=cls._ttl_seconds):
                cls._cache.move_to_end(project_id)
                return cached_value[1]
            else:
                del cls._cache[project_id]

        return None

    @classmethod
    def set(cls, project_id: str, monitors: list[ActiveMonitor]) -> None:
        cls._cache[project_id] = (datetime.now(), monitors)
        if len(cls._cache) > cls._capacity:
            cls._cache.popitem(last=False)


def get_active_monitors(project_id: str) -> list[ActiveMonitor]:
    """Returns cached active monitors for a given project."""
    if (cached_monitors := MonitorsCache.get(project_id)) is not None:
        return cached_monitors

    monitors = fetch_active_monitors(project_id)

    MonitorsCache.set(project_id, monitors)

    return monitors


def _make_active_monitor(project_id: str, obj: tsi.ObjSchema) -> ActiveMonitor:
    return ActiveMonitor(
        monitor=Monitor(
            name=obj.val["name"],
            description=obj.val["description"],
            sampling_rate=obj.val["sampling_rate"],
            scorers=resolve_scorer_refs(obj.val["scorers"], project_id),
            op_names=obj.val["op_names"],
            query=obj.val["query"],
            active=obj.val["active"],
        ),
        internal_ref=InternalObjectRef(
            project_id=project_id, name=obj.val["name"], version=obj.digest
        ),
        wb_user_id=obj.wb_user_id,
    )


def fetch_active_monitors(project_id: str) -> list[ActiveMonitor]:
    """Returns active monitors for a given project."""
    obj_query = tsi.ObjQueryReq(
        project_id=project_id,
        filter=tsi.ObjectVersionFilter(
            is_op=False,
            base_object_classes=[Monitor.__name__],
            latest_only=True,
        ),
    )

    server = get_trace_server()

    monitor_objects = server.objs_query(obj_query)

    active_monitors = [
        _make_active_monitor(project_id, obj)
        for obj in monitor_objects.objs
        if obj.val["active"]
    ]

    return active_monitors


def resolve_scorer_refs(scorer_ref_uris: list[str], project_id: str) -> list[Scorer]:
    """Resolves scorer references to Scorer objects."""
    server = get_trace_server()

    scorer_refs = [
        parse_internal_uri(scorer_ref_uri) for scorer_ref_uri in scorer_ref_uris
    ]

    scorer_dicts = server.refs_read_batch(
        tsi.RefsReadBatchReq(refs=scorer_ref_uris)
    ).vals

    scorers = [
        maybe_objectify(from_json(scorer_dict, project_id, server))
        for scorer_dict in scorer_dicts
    ]

    for scorer, scorer_ref in zip(scorers, scorer_refs):
        scorer.__dict__["internal_ref"] = scorer_ref

    return scorers  # type: ignore


class CallNotWrittenError(Exception):
    pass


# We do the following retry logic because ClickHouse does not guarantee that the call will be available immediately.
@retry(
    retry=retry_if_exception_type(CallNotWrittenError),
    wait=wait_fixed(1),
    stop=stop_after_attempt(10),
    before=before_log(logger, logging.INFO),
)
async def get_filtered_calls(
    project_id: str,
    call_ids: list[str],
    op_names: list[str],
    query: Optional[tsi.Query],
) -> list[Call]:
    """This function is used to get the calls that match the filter."""
    logger.info("Attempting to get %s calls", len(call_ids))
    server = get_trace_server()
    count_req = tsi.CallsQueryStatsReq(
        project_id=project_id,
        filter=tsi.CallsFilter(call_ids=call_ids),
        # We want to make sure all end_call events have been written to the DB
        query={
            "$expr": {
                "$not": [{"$eq": [{"$getField": "ended_at"}, {"$literal": None}]}]
            }
        },
    )

    count = server.calls_query_stats(count_req).count

    if count != len(set(call_ids)):
        raise CallNotWrittenError("Some calls not yet written to DB")

    req = tsi.CallsQueryReq(
        project_id=project_id,
        filter=tsi.CallsFilter(
            call_ids=call_ids,
            query=query,
            op_names=op_names,
        ),
    )

    calls = server.calls_query(req).calls

    logger.info("Found %s calls to score.", len(calls))

    return [build_client_call(call) for call in calls]


def build_client_call(server_call: tsi.CallSchema) -> Call:
    """Converts a server call to a client call."""
    server = get_trace_server()

    return Call(
        _op_name=server_call.op_name,
        project_id=server_call.project_id,
        trace_id=server_call.trace_id,
        parent_id=server_call.parent_id,
        id=server_call.id,
        inputs=from_json(server_call.inputs, server_call.project_id, server),
        output=from_json(server_call.output, server_call.project_id, server),
        exception=server_call.exception,
        summary=dict(server_call.summary) if server_call.summary is not None else None,
        _display_name=server_call.display_name,
        attributes=server_call.attributes,
        started_at=server_call.started_at,
        ended_at=server_call.ended_at,
        deleted_at=server_call.deleted_at,
    )


def _do_score_call(scorer: Scorer, call: Call, project_id: str) -> tuple[str, Any]:
    example = {k: v for k, v in call.inputs.items() if k != "self"}
    output = call.output

    if isinstance(output, ObjectRef):
        output = output.get()

    score_op, score_args = preparer_scorer_op_args(scorer, example, output)

    inputs_with_defaults = _default_on_input_handler(score_op, (), score_args).inputs
    score_args = {**inputs_with_defaults, "self": scorer}

    server = get_trace_server()

    call_start_req = tsi.CallStartReq(
        start=tsi.StartedCallSchemaForInsert(
            op_name=score_op.name,
            project_id=project_id,
            inputs=inputs_with_defaults,
            started_at=datetime.now(),
            attributes={},
        )
    )

    call_start_res = server.call_start(call_start_req)

    result = score_op.resolve_fn(**score_args)

    result = box(result)

    call_end_req = tsi.CallEndReq(
        end=tsi.EndedCallSchemaForInsert(
            project_id=project_id,
            id=call_start_res.id,
            ended_at=datetime.now(),
            output=result,
            summary={},
        )
    )

    server.call_end(call_end_req, publish=False)

    return call_start_res.id, result


@ddtrace.tracer.wrap(name="weave_scorer.apply_scorer")
async def apply_scorer(
    monitor_internal_ref: InternalObjectRef,
    scorer: Scorer,
    call: Call,
    project_id: str,
    wb_user_id: Optional[str],
) -> None:
    """Actually apply the scorer to the call."""
    score_call_id, result = _do_score_call(scorer, call, project_id)

    # score_call = _get_score_call(score_call_id, project_id)

    call_ref = InternalCallRef(project_id=project_id, id=call.id)  # type: ignore
    score_call_ref = InternalCallRef(project_id=project_id, id=score_call_id)  # type: ignore

    results_json = to_json(result, project_id, None)  # type: ignore
    payload = {"output": results_json}

    feedback_req = FeedbackCreateReq(
        project_id=project_id,
        weave_ref=call_ref.uri(),
        feedback_type=RUNNABLE_FEEDBACK_TYPE_PREFIX + "." + scorer.name,  # type: ignore
        payload=payload,
        runnable_ref=scorer.__dict__["internal_ref"].uri(),
        call_ref=score_call_ref.uri(),
        wb_user_id=wb_user_id,
        trigger_ref=monitor_internal_ref.uri(),
    )

    logger.info("Creating feedback for scorer %s and call %s", scorer.name, call.id)
    server = get_trace_server()
    server.feedback_create(feedback_req)


def _task_done_callback(
    task: asyncio.Task,
    messages: list[Message],
    consumer: KafkaConsumer,
    tasks: set[asyncio.Task],
) -> None:
    tasks.discard(task)

    try:
        task.result()
        for msg in messages:
            consumer.commit(msg)
    except RetryError as e:
        logger.warning("Retries exhausted. Messages should be re-consumed.")
    except Exception as e:
        logger.exception(
            f"Error processing message: {e.__class__.__name__} {e}", exc_info=e
        )


def handle_kafka_errors(msg: Message) -> bool:
    """Handle Kafka-specific errors."""
    if msg.error():
        if msg.error().code() == KafkaError._PARTITION_EOF:
            logger.error(
                "%% %s [%d] reached end at offset %d\n",
                msg.topic(),
                msg.partition(),
                msg.offset(),
            )
        else:
            logger.exception("Kafka error: %s", msg.error())

        return False

    return True


async def cleanup_and_wait(tasks: set[asyncio.Task]) -> set[asyncio.Task]:
    """Clean up completed tasks and wait for pending ones."""
    done_tasks = {t for t in tasks if not t.done()}

    if done_tasks:
        _, pending = await asyncio.wait(done_tasks, return_when=asyncio.FIRST_COMPLETED)
        return pending

    return set()


KAFKA_CONSUMER_GROUP_ID = "weave-worker-scorer"


async def process_project_ended_calls(
    project_id: str,
    ended_calls: list[tsi.EndedCallSchemaForInsert],
) -> None:
    if len(ended_calls) == 0:
        logger.warning("No ended calls to process, this should not happen")
        return

    project_id = ended_calls[0].project_id

    active_monitors = get_active_monitors(project_id)

    call_ids = [ended_call.id for ended_call in ended_calls]

    async def _process_monitor(active_monitor: ActiveMonitor) -> None:
        monitor = active_monitor["monitor"]
        monitor_internal_ref = active_monitor["internal_ref"]
        wb_user_id = active_monitor["wb_user_id"]

        # Here we potentially query the same calls multiple times.
        # The reasons is that each monitor has its own call filter, so we need to query the DB for each monitor.
        # We could merge the call filters and do a single query, but then
        # we would need to figure out which call match what monitor filter.
        # Currently we have no way to apply filters outside the DB
        calls = await get_filtered_calls(
            project_id,
            call_ids,
            monitor.op_names,
            monitor.query,
        )

        with get_trace_server().call_batch():
            await asyncio.gather(
                *[
                    apply_scorer(
                        monitor_internal_ref, scorer, call, project_id, wb_user_id
                    )
                    for scorer in monitor.scorers
                    for call in calls
                ]
            )

    await asyncio.gather(
        *[_process_monitor(active_monitor) for active_monitor in active_monitors]
    )


async def run_consumer() -> None:
    """This is the main loop consuming the ended calls from the Kafka topic."""
    consumer = KafkaConsumer.from_env(group_id=KAFKA_CONSUMER_GROUP_ID)
    tasks: set[asyncio.Task] = set()

    consumer.subscribe([CALL_ENDED_TOPIC])
    logger.info("Subscribed to %s", CALL_ENDED_TOPIC)

    try:
        while True:
            messages: list[Message] = consumer.consume(
                num_messages=wf_scoring_worker_batch_size(),
                timeout=wf_scoring_worker_batch_timeout(),
            )
            if len(messages) == 0:
                continue

            ended_calls_by_project_id: dict[
                str, tuple[list[tsi.EndedCallSchemaForInsert], list[Message]]
            ] = defaultdict(lambda: ([], []))
            for message in messages:
                if not handle_kafka_errors(message):
                    continue

                ended_call: tsi.EndedCallSchemaForInsert = (
                    tsi.EndedCallSchemaForInsert.model_validate_json(
                        message.value().decode("utf-8")
                    )
                )
                ended_calls_by_project_id[ended_call.project_id][0].append(ended_call)
                ended_calls_by_project_id[ended_call.project_id][1].append(message)

            try:
                for project_id, (
                    ended_calls,
                    messages,
                ) in ended_calls_by_project_id.items():
                    task = asyncio.create_task(
                        process_project_ended_calls(project_id, ended_calls)
                    )
                    task.add_done_callback(
                        lambda t: _task_done_callback(t, messages, consumer, tasks)
                    )
                    tasks.add(task)

                tasks = await cleanup_and_wait(tasks)
            except Exception as e:
                logger.exception("Error processing messages: %s", e, exc_info=e)

    finally:
        if tasks:
            await asyncio.gather(*tasks)
        consumer.close()


def init_sentry() -> None:
    sentry_sdk.init(
        dsn="https://8ed9a67d68481736b1bc4e815a2a8901@o151352.ingest.us.sentry.io/4509210797277185",
        environment=os.environ.get("WEAVE_SENTRY_ENV", "dev"),
        release=weave.version.VERSION,
    )


async def main() -> None:
    init_sentry()

    await run_consumer()


if __name__ == "__main__":
    if wf_enable_online_eval():
        logger.info("Starting scorer worker...")
        asyncio.run(main())
    else:
        logger.info("Online eval is disabled, exiting.")
