from __future__ import annotations

import dataclasses
import logging
import os
import re
from typing import TYPE_CHECKING, Any, TypedDict

import pydantic

from weave.client.weave_client import WeaveClient
from weave.trace import settings
from weave.trace.call import (
    Call,
    CallsIter,
)
from weave.trace.constants import TRACE_CALL_EMOJI
from weave.trace.init_message import WANDB_AVAILABLE
from weave.trace.interface_query_builder import (
    exists_expr,
    get_field_expr,
    literal_expr,
)
from weave.trace.object_record import (
    ObjectRecord,
    dataclass_object_record,
    pydantic_object_record,
)
from weave.trace.op import (
    as_op,
)
from weave.trace.op import op as op_deco
from weave.trace.op_protocol import Op
from weave.trace.ref_util import get_ref
from weave.trace.refs import (
    ObjectRef,
    Ref,
)
from weave.trace.serialization.serialize import (
    isinstance_namedtuple,
)
from weave.trace.settings import (
    client_parallelism,
)
from weave.trace.table import Table
from weave.trace.vals import WeaveObject, WeaveTable
from weave.trace_server.constants import MAX_OBJECT_NAME_LENGTH
from weave.trace_server.interface.feedback_types import (
    runnable_feedback_output_selector,
    runnable_feedback_runnable_ref_selector,
)
from weave.trace_server.trace_server_interface import (
    Query,
)
from weave.utils.sanitize import REDACTED_VALUE, should_redact

if TYPE_CHECKING:
    import wandb

# Controls if objects can have refs to projects not the WeaveClient project.
# If False, object refs with with mismatching projects will be recreated.
# If True, use existing ref to object in other project.
ALLOW_MIXED_PROJECT_REFS = False

logger = logging.getLogger(__name__)


# TODO: should be Call, not WeaveObject


def print_call_link(call: Call) -> None:
    if settings.should_print_call_link():
        logger.info(f"{TRACE_CALL_EMOJI} {call.ui_url}")


def _add_scored_by_to_calls_query(
    scored_by: list[str] | str | None, query: Query | None
) -> Query | None:
    # This logic might be pushed down to the server soon, but for now it lives here:
    if not scored_by:
        return query

    if isinstance(scored_by, str):
        scored_by = [scored_by]
    exprs = []
    if query is not None:
        exprs.append(query["$expr"])
    for name in scored_by:
        ref = Ref.maybe_parse_uri(name)
        if ref and isinstance(ref, ObjectRef):
            uri = name
            scorer_name = ref.name
            exprs.append(
                {
                    "$eq": (
                        get_field_expr(
                            runnable_feedback_runnable_ref_selector(scorer_name)
                        ),
                        literal_expr(uri),
                    )
                }
            )
        else:
            exprs.append(
                exists_expr(get_field_expr(runnable_feedback_output_selector(name)))
            )
    return Query.model_validate({"$expr": {"$and": exprs}})


def get_obj_name(val: Any) -> str:
    name = getattr(val, "name", None)
    if name is None:
        if isinstance(val, ObjectRecord):
            name = val._class_name
        else:
            name = f"{val.__class__.__name__}"
    if not isinstance(name, str):
        raise TypeError(f"Object's name attribute is not a string: {name}")
    return name


def _get_direct_ref(obj: Any) -> Ref | None:
    if isinstance(obj, WeaveTable):
        # TODO: this path is odd. We want to use table_ref when serializing
        # which is the direct ref to the table. But .ref on WeaveTable is
        # the "container ref", ie a ref to the root object that the WeaveTable
        # is within, with extra pointing to the table.
        return obj.table_ref
    return get_ref(obj)


def _remove_empty_ref(obj: ObjectRecord) -> ObjectRecord:
    if hasattr(obj, "ref"):
        if obj.ref is not None:
            raise ValueError(f"Unexpected ref in object record: {obj}")
        else:
            del obj.__dict__["ref"]
    return obj


def map_to_refs(obj: Any) -> Any:
    if isinstance(obj, Ref):
        return obj
    if ref := _get_direct_ref(obj):
        return ref

    if isinstance(obj, ObjectRecord):
        # Here, we expect ref to be empty since it would have short circuited
        # above with `_get_direct_ref`
        return _remove_empty_ref(obj.map_values(map_to_refs))
    elif isinstance(obj, (pydantic.BaseModel, pydantic.v1.BaseModel)):
        # Check if this object has a custom serializer registered
        from weave.trace.serialization.serializer import get_serializer_for_obj

        if get_serializer_for_obj(obj) is not None:
            # If it has a custom serializer, don't convert to ObjectRecord
            # Let the serialization layer handle it
            return obj
        obj_record = pydantic_object_record(obj)
        # Here, we expect ref to be empty since it would have short circuited
        # above with `_get_direct_ref`
        obj_record = _remove_empty_ref(obj_record)
        return obj_record.map_values(map_to_refs)
    elif dataclasses.is_dataclass(obj):
        obj_record = dataclass_object_record(obj)
        # Here, we expect ref to be empty since it would have short circuited
        # above with `_get_direct_ref`
        obj_record = _remove_empty_ref(obj_record)
        return obj_record.map_values(map_to_refs)
    elif isinstance(obj, Table):
        return obj.ref
    elif isinstance(obj, WeaveTable):
        return obj.ref
    elif isinstance_namedtuple(obj):
        return {k: map_to_refs(v) for k, v in obj._asdict().items()}
    elif isinstance(obj, (list, tuple)):
        return [map_to_refs(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: map_to_refs(v) for k, v in obj.items()}

    # This path should only be reached if the object is both:
    # 1. A `WeaveObject`; and
    # 2. Has been dirtied (edited in any way), causing obj.ref=None
    elif isinstance(obj, WeaveObject):
        return map_to_refs(obj._val)

    return obj


RESERVED_SUMMARY_USAGE_KEY = "usage"
RESERVED_SUMMARY_STATUS_COUNTS_KEY = "status_counts"

BACKGROUND_PARALLELISM_MIX = 0.5
# This size is correlated with the maximum single row insert size
# in clickhouse, which is currently unavoidable.
MAX_TRACE_PAYLOAD_SIZE = int(3.5 * 1024 * 1024)  # 3.5 MiB


class PendingJobCounts(TypedDict):
    """Counts of pending jobs for each type."""

    main_jobs: int
    fastlane_jobs: int
    call_processor_jobs: int
    feedback_processor_jobs: int
    total_jobs: int


class FlushStatus(TypedDict):
    """Status information about the current flush operation."""

    # Current job counts
    job_counts: PendingJobCounts

    # Tracking of completed jobs
    completed_since_last_update: int
    total_completed: int

    # Maximum number of jobs seen during this flush operation
    max_total_jobs: int

    # Whether there are any pending jobs
    has_pending_jobs: bool


def get_parallelism_settings() -> tuple[int | None, int | None]:
    total_parallelism = client_parallelism()

    # if user has explicitly set 0 or 1 for total parallelism,
    # don't use fastlane executor
    if total_parallelism is not None and total_parallelism <= 1:
        return total_parallelism, 0

    # if total_parallelism is None, calculate it
    if total_parallelism is None:
        total_parallelism = min(32, (os.cpu_count() or 1) + 4)

    # use 50/50 split between main and fastlane
    parallelism_main = int(total_parallelism * (1 - BACKGROUND_PARALLELISM_MIX))
    parallelism_fastlane = total_parallelism - parallelism_main

    return parallelism_main, parallelism_fastlane


def _safe_get_wandb_run() -> wandb.sdk.wandb_run.Run | None:
    if WANDB_AVAILABLE:
        import wandb

        return wandb.run
    return None


def safe_current_wb_run_id() -> str | None:
    wandb_run = _safe_get_wandb_run()
    if wandb_run is None:
        return None

    return f"{wandb_run.entity}/{wandb_run.project}/{wandb_run.id}"


def safe_current_wb_run_step() -> int | None:
    wandb_run = _safe_get_wandb_run()
    if wandb_run is None:
        return None
    try:
        return int(wandb_run.step)
    except Exception:
        return None


def check_wandb_run_matches(
    wandb_run_id: str | None, weave_entity: str, weave_project: str
) -> None:
    if wandb_run_id:
        # ex: "entity/project/run_id"
        wandb_entity, wandb_project, _ = wandb_run_id.split("/")
        if wandb_entity != weave_entity or wandb_project != weave_project:
            raise ValueError(
                f'Project Mismatch: weave and wandb must be initialized using the same project. Found wandb.init targeting project "{wandb_entity}/{wandb_project}" and weave.init targeting project "{weave_entity}/{weave_project}". To fix, please use the same project for both library initializations.'
            )


def _build_anonymous_op(name: str, config: dict[str, Any] | None = None) -> Op:
    if config is None:

        def op_fn(*args, **kwargs):  # type: ignore
            # Code-capture unavailable for this op
            pass

    else:

        def op_fn(*args, **kwargs):  # type: ignore
            # Code-capture unavailable for this op
            op_config = config

    op_fn.__name__ = name
    op = op_deco(op_fn)
    op = as_op(op)
    op.name = name
    return op


def redact_sensitive_keys(obj: Any) -> Any:
    # We should NEVER mutate reffed objects.
    #
    # 1. This code builds new objects that no longer have refs
    # 2. Even if we did an in-place edit, that would invalidate the ref (since
    # the ref is to the object's digest)
    if get_ref(obj):
        return obj

    if isinstance(obj, dict):
        dict_res = {}
        for k, v in obj.items():
            if isinstance(k, str) and should_redact(k):
                dict_res[k] = REDACTED_VALUE
            else:
                dict_res[k] = redact_sensitive_keys(v)
        return dict_res

    elif isinstance(obj, list):
        list_res = []
        for v in obj:
            list_res.append(redact_sensitive_keys(v))
        return list_res

    elif isinstance(obj, tuple):
        tuple_res = []
        for v in obj:
            tuple_res.append(redact_sensitive_keys(v))
        return tuple(tuple_res)

    return obj


def sanitize_object_name(name: str) -> str:
    # Replaces any non-alphanumeric characters with a single dash and removes
    # any leading or trailing dashes. This is more restrictive than the DB
    # constraints and can be relaxed if needed.
    res = re.sub(r"([._-]{2,})+", "-", re.sub(r"[^\w._]+", "-", name)).strip("-_")
    if not res:
        raise ValueError(f"Invalid object name: {name}")
    if len(res) > MAX_OBJECT_NAME_LENGTH:
        res = res[:MAX_OBJECT_NAME_LENGTH]
    return res


__docspec__ = [WeaveClient, Call, CallsIter]
