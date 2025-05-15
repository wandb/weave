import asyncio
import logging
import os
from collections.abc import Coroutine
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, TypedDict

import sentry_sdk
from confluent_kafka import KafkaError, Message
from tenacity import (
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

# This import is used to register built-in scorers so they can be deserialized from the DB
import weave.scorers  # noqa: F401
from weave.flow.monitor import Monitor
from weave.flow.scorer import Scorer
from weave.trace.call import Call, apply_scorer_async
from weave.trace.objectify import maybe_objectify
from weave.trace.op import (
    Op,
    _call_sync_func,
)
from weave.trace.serialization.serialize import to_json
from weave.trace.weave_client import (
    RUNNABLE_FEEDBACK_TYPE_PREFIX,
    FeedbackCreateReq,
    ObjectRef,
    from_json,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer
from weave.trace_server.kafka import CALL_ENDED_TOPIC, KafkaConsumer
from weave.trace_server.refs_internal import (
    InternalCallRef,
    InternalObjectRef,
    parse_internal_uri,
)
from weave.trace_server.trace_server_interface import TraceServerInterface

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_TRACE_SERVER: Optional[TraceServerInterface] = None


def get_trace_server() -> TraceServerInterface:
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

    _cache: dict[str, tuple[datetime, list[ActiveMonitor]]] = {}
    _ttl_seconds = 60

    @classmethod
    def get(cls, project_id: str) -> list[ActiveMonitor] | None:
        if (cached_value := cls._cache.get(project_id)) is not None:
            if cached_value[0] > datetime.now() - timedelta(seconds=cls._ttl_seconds):
                return cached_value[1]
            else:
                del cls._cache[project_id]

        return None

    @classmethod
    def set(cls, project_id: str, monitors: list[ActiveMonitor]) -> None:
        cls._cache[project_id] = (datetime.now(), monitors)


def get_active_monitors(project_id: str) -> list[ActiveMonitor]:
    """Returns cached active monitors for a given project."""
    if (cached_monitors := MonitorsCache.get(project_id)) is not None:
        return cached_monitors

    monitors = fetch_active_monitors(project_id)

    MonitorsCache.set(project_id, monitors)

    return monitors


def fetch_active_monitors(project_id: str) -> list[ActiveMonitor]:
    """Returns active monitors for a given project."""
    logger.info("Fetching active monitors for project %s", project_id)
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
        ActiveMonitor(
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
    stop=stop_after_attempt(5),
    before=before_log(logger, logging.INFO),
)
def get_filtered_call(
    op_names: list[str],
    query: Optional[tsi.Query],
    ended_call: tsi.EndedCallSchemaForInsert,
) -> Optional[Call]:
    """Looks up the call based on a monitor's call filter."""
    server = get_trace_server()

    # We do this two-step querying to circumvent the absence of write->read consistency in ClickHouse.
    # We want to differentiate between a call not written yet and a call existing but not matching the filter.
    # - first we count the calls that match the call id
    # - if that returns 0, we raise an exception in order to trigger a retry
    # - if that returns > 0, we know the call exists, so we can proceed with the filter

    count_req = tsi.CallsQueryStatsReq(
        project_id=ended_call.project_id,
        filter=tsi.CallsFilter(call_ids=[ended_call.id]),
    )

    count = server.calls_query_stats(count_req).count

    if count == 0:
        raise CallNotWrittenError(f"Call {ended_call.id} not yet written to DB")

    req = tsi.CallsQueryReq(
        project_id=ended_call.project_id,
        filter=tsi.CallsFilter(
            call_ids=[ended_call.id],
            query=query,
            op_names=op_names,
        ),
    )

    calls = server.calls_query(req).calls

    if len(calls) == 0:
        logger.info("No matching calls found for call id %s", ended_call.id)
        return None

    if len(calls) > 1:
        logger.warning("Multiple calls found for call id %s", ended_call.id)
        return None

    call = calls[0]

    if not call.ended_at:
        return None

    if call.exception:
        return None

    logger.info("Found call %s", call.id)

    return build_client_call(call)


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


async def process_monitor(
    monitor: Monitor,
    monitor_internal_ref: InternalObjectRef,
    ended_call: tsi.EndedCallSchemaForInsert,
    wb_user_id: str,
) -> None:
    """Actually apply the monitor's scorers for an ended call."""
    if (call := get_filtered_call(monitor.op_names, monitor.query, ended_call)) is None:
        return

    for scorer in monitor.scorers:
        logger.info("Applying scorer %s to call %s", scorer.name, call.id)
        await apply_scorer(
            monitor_internal_ref, scorer, call, ended_call.project_id, wb_user_id
        )


class WeaveWorkerClient:
    def __init__(self, project_id: str):
        self._project_id = project_id
        self._server = get_trace_server()

    def create_call(
        self,
        op: str | Op,
        inputs: dict,
        parent: Call | None = None,
        attributes: dict | None = None,
        display_name: str | Callable[[Call], str] | None = None,
        *,
        use_stack: bool = True,
    ) -> Call:
        assert isinstance(op, Op)  # necessary for type narrowing
        inputs_json = to_json(inputs, self._project_id, None, use_dictify=False)  # type: ignore

        call_start_req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                op_name=op.name,
                project_id=self._project_id,
                inputs=inputs_json,
                started_at=datetime.now(),
                attributes={},
            )
        )

        call_start_res = self._server.call_start(call_start_req)

        return Call(
            _op_name=op.name,
            project_id=self._project_id,
            parent_id=None,
            trace_id=call_start_res.trace_id,
            id=call_start_res.id,
            inputs=inputs,
        )

    def finish_call(
        self,
        call: Call,
        output: Any,
        exception: BaseException | None = None,
        *__: Any,
        **___: Any,
    ) -> None:
        call_end_req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=self._project_id,
                id=call.id,
                ended_at=datetime.now(),
                output=output,
                summary={},
            )
        )

        self._server.call_end(call_end_req)


async def _do_score_call(
    scorer: Scorer, call: Call, project_id: str
) -> tuple[str, Any]:
    example = {k: v for k, v in call.inputs.items() if k != "self"}
    output = call.output

    if isinstance(output, ObjectRef):
        output = output.get()

    client = WeaveWorkerClient(project_id)

    def _async_call_op(
        op: Op, *args: Any, **kwargs: Any
    ) -> Coroutine[Any, Any, tuple[Any, Call]]:
        return asyncio.to_thread(
            lambda: _call_sync_func(op, *args, client=client, **kwargs)
        )

    apply_scorer_result = await apply_scorer_async(
        scorer, example, output, _async_call_op
    )
    logger.info("Apply scorer result: %s", apply_scorer_result)

    assert apply_scorer_result.score_call.id is not None, "Score call was not created"

    return apply_scorer_result.score_call.id, apply_scorer_result.result


def _get_score_call(score_call_id: str, project_id: str) -> Call:
    """Gets a score call from the DB."""
    server = get_trace_server()

    call_req = tsi.CallsQueryReq(
        project_id=project_id, filter=tsi.CallsFilter(call_ids=[score_call_id])
    )

    calls = server.calls_query(call_req).calls

    return build_client_call(calls[0])


async def apply_scorer(
    monitor_internal_ref: InternalObjectRef,
    scorer: Scorer,
    call: Call,
    project_id: str,
    wb_user_id: str,
) -> None:
    """Actually apply the scorer to the call."""
    score_call_id, result = await _do_score_call(scorer, call, project_id)

    score_call = _get_score_call(score_call_id, project_id)

    call_ref = InternalCallRef(project_id=project_id, id=call.id)  # type: ignore
    score_call_ref = InternalCallRef(project_id=project_id, id=score_call.id)  # type: ignore

    results_json = to_json(result, project_id, None)  # type: ignore
    payload = {"output": results_json}

    server = get_trace_server()

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

    server.feedback_create(feedback_req)


async def process_ended_call(ended_call: tsi.EndedCallSchemaForInsert) -> None:
    logger.info("Processing ended call %s", ended_call.id)
    project_id = ended_call.project_id

    active_monitors = get_active_monitors(project_id)

    for active_monitor in active_monitors:
        await process_monitor(
            active_monitor["monitor"],
            active_monitor["internal_ref"],
            ended_call,
            active_monitor["wb_user_id"],  # type: ignore
        )


def _task_done_callback(
    task: asyncio.Task,
    msg: Message,
    consumer: KafkaConsumer,
    tasks: set[asyncio.Task],
) -> None:
    tasks.discard(task)

    try:
        task.result()
        consumer.commit(msg)
    except Exception as e:
        logger.exception(
            f"Error processing message: {e.__class__.__name__} {e}", exc_info=e
        )


def create_task(
    msg: Message, consumer: KafkaConsumer, tasks: set[asyncio.Task]
) -> asyncio.Task:
    """Process a single Kafka message and create a task for it."""
    ended_call = tsi.EndedCallSchemaForInsert.model_validate_json(
        msg.value().decode("utf-8")
    )
    logger.debug("Creating task for ended call %s", ended_call.id)

    task = asyncio.create_task(process_ended_call(ended_call))
    task.add_done_callback(lambda t: _task_done_callback(t, msg, consumer, tasks))

    return task


async def handle_kafka_errors(msg: Message) -> bool:
    """Handle Kafka-specific errors."""
    if msg.error():
        if msg.error().code() == KafkaError._PARTITION_EOF:
            logger.error(
                "%% %s [%d] reached end at offset %d\n"
                % (msg.topic(), msg.partition(), msg.offset())
            )
        else:
            logger.exception("Kafka error: %s", msg.error())

        return False

    return True


async def cleanup_tasks(tasks: set[asyncio.Task]) -> set[asyncio.Task]:
    """Clean up completed tasks and wait for pending ones."""
    done_tasks = {t for t in tasks if not t.done()}

    if done_tasks:
        _, pending = await asyncio.wait(done_tasks, return_when=asyncio.FIRST_COMPLETED)
        return pending

    return set()


async def run_consumer() -> None:
    """This is the main loop consuming the ended calls from the Kafka topic."""
    consumer = KafkaConsumer.from_env()
    tasks: set[asyncio.Task] = set()

    consumer.subscribe([CALL_ENDED_TOPIC])
    logger.info("Subscribed to %s", CALL_ENDED_TOPIC)

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue

            if not await handle_kafka_errors(msg):
                continue

            try:
                task = create_task(msg, consumer, tasks)
                tasks.add(task)
                tasks = await cleanup_tasks(tasks)
            except Exception as e:
                logger.exception("Error processing message: %s", e, exc_info=e)
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
    asyncio.run(main())
