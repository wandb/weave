import asyncio
import inspect
import logging
from datetime import datetime
from typing import Any
import sentry_sdk
import os

# This import is used to register built-in scorers so they can be deserialized from the DB
import weave.scorers  # noqa: F401
from confluent_kafka import KafkaError, Message
from tenacity import (
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)
from weave.flow.monitor import Monitor
from weave.flow.scorer import Scorer, get_scorer_attributes
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

_TRACE_SERVER: TraceServerInterface | None = None


def get_trace_server() -> TraceServerInterface:
    global _TRACE_SERVER

    if _TRACE_SERVER is None:
        _TRACE_SERVER = ClickHouseTraceServer.from_env()

    return _TRACE_SERVER


# This should be cached to avoid hitting ClickHouse for each ended call.
def get_active_monitors(project_id: str) -> list[tuple[Monitor, str]]:
    """
    Returns active monitors for a given project.
    """
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

    active_monitors_ref_user_ids = [
        (
            Monitor(
                name=obj.val["name"],
                description=obj.val["description"],
                sampling_rate=obj.val["sampling_rate"],
                scorers=resolve_scorer_refs(obj.val["scorers"], project_id),
                op_names=obj.val["op_names"],
                query=obj.val["query"],
                active=obj.val["active"],
            ),
            InternalObjectRef(
                project_id=project_id, name=obj.val["name"], version=obj.digest
            ),
            obj.wb_user_id,
        )
        for obj in monitor_objects.objs
        if obj.val["active"]
    ]

    return active_monitors_ref_user_ids


def resolve_scorer_refs(scorer_ref_uris: list[str], project_id: str) -> list[Scorer]:
    """
    Resolves scorer references to Scorer objects.
    """
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

    return scorers


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
    op_names: list[str], query: tsi.Query | None, ended_call: tsi.EndedCallSchemaForInsert
) -> Call | None:
    """
    Looks up the call based on a monitor's call filter.
    """
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
        logger.warning("No matching calls found for call id %s", ended_call.id)
        return

    if len(calls) > 1:
        logger.warning("Multiple calls found for call id %s", ended_call.id)
        return

    call = calls[0]

    if not call.ended_at:
        return

    if call.exception:
        return

    logger.info("Found call %s", call.id)

    return build_client_call(call)


def build_client_call(server_call: tsi.CallSchema) -> Call:
    """
    Converts a server call to a client call.
    """
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
):
    """
    Actually apply the monitor's scorers for an ended call.
    """
    if (call := get_filtered_call(monitor.op_names, monitor.query, ended_call)) is None:
        return

    for scorer in monitor.scorers:
        logger.info("Applying scorer %s to call %s", scorer.name, call.id)
        await apply_scorer(
            monitor_internal_ref, scorer, call, ended_call.project_id, wb_user_id
        )


def _do_score_call(scorer: Scorer, call: Call, project_id: str) -> tuple[str, Any]:
    example = {k: v for k, v in call.inputs.items() if k != "self"}
    output = call.output

    if isinstance(output, ObjectRef):
        output = output.get()

    scorer_attributes = get_scorer_attributes(scorer)
    score_op = scorer_attributes.score_op
    score_signature = inspect.signature(score_op)
    score_arg_names = list(score_signature.parameters.keys())
    score_output_name = "output" if "output" in score_arg_names else "model_output"
    score_arg_names = [param for param in score_arg_names if (param != "self")]
    score_args = {k: v for k, v in example.items() if k in score_arg_names}
    score_args[score_output_name] = output

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

    server.call_end(call_end_req)

    return call_start_res.id, result


def _get_score_call(score_call_id: str, project_id: str) -> Call:
    """
    Gets a score call from the DB.
    """
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
):
    """
    Actually apply the scorer to the call.
    """
    score_call_id, result = _do_score_call(scorer, call, project_id)

    score_call = _get_score_call(score_call_id, project_id)

    call_ref = InternalCallRef(project_id=project_id, id=call.id)
    score_call_ref = InternalCallRef(project_id=project_id, id=score_call.id)

    results_json = to_json(result, project_id, None)
    payload = {"output": results_json}

    server = get_trace_server()

    feedback_req = FeedbackCreateReq(
        project_id=project_id,
        weave_ref=call_ref.uri(),
        feedback_type=RUNNABLE_FEEDBACK_TYPE_PREFIX + "." + scorer.name,
        payload=payload,
        runnable_ref=scorer.__dict__["internal_ref"].uri(),
        call_ref=score_call_ref.uri(),
        wb_user_id=wb_user_id,
        trigger_ref=monitor_internal_ref.uri(),
    )

    server.feedback_create(feedback_req)


async def process_ended_call(ended_call: tsi.EndedCallSchemaForInsert):
    project_id = ended_call.project_id

    active_monitors_ref_user_ids = get_active_monitors(project_id)

    for monitor, monitor_internal_ref, wb_user_id in active_monitors_ref_user_ids:
        await process_monitor(monitor, monitor_internal_ref, ended_call, wb_user_id)


def _call_processor_done_callback(
    task: asyncio.Task,
    msg: Message,
    consumer: KafkaConsumer,
    call_processors: set[asyncio.Task],
) -> None:
    call_processors.discard(task)

    try:
        task.result()
        consumer.commit(msg)
    except Exception as e:
        logger.error(f"Error processing message: {e.__class__.__name__} {e}")


async def process_kafka_message(
    msg: Message, consumer: KafkaConsumer, call_processors: set[asyncio.Task]
) -> bool:
    """
    Process a single Kafka message and create a task for it.
    """
    try:
        ended_call = tsi.EndedCallSchemaForInsert.model_validate_json(
            msg.value().decode("utf-8")
        )
        logger.info("Processing ended call %s", ended_call.id)

        task = asyncio.create_task(process_ended_call(ended_call))
        call_processors.add(task)
        task.add_done_callback(
            lambda t: _call_processor_done_callback(t, msg, consumer, call_processors)
        )

        return True
    except Exception as e:
        logger.error("Error processing message: %s", e)
        return False


async def handle_kafka_errors(msg: Message) -> bool:
    """
    Handle Kafka-specific errors.
    """
    if msg.error():
        if msg.error().code() == KafkaError._PARTITION_EOF:
            logger.error(
                "%% %s [%d] reached end at offset %d\n"
                % (msg.topic(), msg.partition(), msg.offset())
            )
        else:
            logger.error("Kafka error: %s", msg.error())

        return False

    return True


async def cleanup_tasks(call_processors: set[asyncio.Task]) -> set[asyncio.Task]:
    """
    Clean up completed tasks and wait for pending ones.
    """
    call_processors = {t for t in call_processors if not t.done()}

    if call_processors:
        _, pending = await asyncio.wait(
            call_processors, return_when=asyncio.FIRST_COMPLETED
        )
        return pending

    return set()


async def run_consumer():
    """
    This is the main loop consuming the ended calls from the Kafka topic.
    """
    consumer = KafkaConsumer.from_env()
    call_processors = set()

    consumer.subscribe([CALL_ENDED_TOPIC])
    logger.info("Subscribed to %s", CALL_ENDED_TOPIC)

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue

            if not await handle_kafka_errors(msg):
                continue

            if await process_kafka_message(msg, consumer, call_processors):
                call_processors = await cleanup_tasks(call_processors)
    finally:
        if call_processors:
            await asyncio.gather(*call_processors)
        consumer.close()


def init_sentry():
    sentry_sdk.init(
        dsn="https://8ed9a67d68481736b1bc4e815a2a8901@o151352.ingest.us.sentry.io/4509210797277185",
        environment=os.environ.get("WEAVE_SENTRY_ENV", "dev"),
        release=weave.version.VERSION
    )


async def main():
    init_sentry()

    await run_consumer()


if __name__ == "__main__":
    asyncio.run(main())
