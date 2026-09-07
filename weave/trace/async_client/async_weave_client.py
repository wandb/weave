"""Async implementation of WeaveClient."""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import json
import logging
import os
from collections import defaultdict
from collections.abc import AsyncIterator, Iterator, Sequence
from functools import cached_property, lru_cache
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Optional,
    Protocol,
    TypedDict,
    TypeVar,
    Union,
    cast,
    overload,
)

import pydantic
from requests import HTTPError

from weave import version
from weave.trace import trace_sentry, urls
from weave.trace.casting import CallsFilterLike, QueryLike, SortByLike
from weave.trace.context import call_context
from weave.trace.exception import exception_to_json_str
from weave.trace.feedback import FeedbackQuery, RefFeedbackQuery
from weave.trace.interface_query_builder import (
    exists_expr,
    get_field_expr,
    literal_expr,
)
from weave.trace.isinstance import weave_isinstance
from weave.trace.object_record import (
    ObjectRecord,
    dataclass_object_record,
    pydantic_object_record,
)
from weave.trace.objectify import maybe_objectify
from weave.trace.op import (
    Op,
    as_op,
    is_op,
    is_placeholder_call,
    is_tracing_setting_disabled,
    maybe_unbind_method,
    placeholder_call,
    print_call_link,
    should_skip_tracing_for_op,
)
from weave.trace.op import op as op_deco
from weave.trace.ref_util import get_ref, remove_ref, set_ref
from weave.trace.refs import (
    CallRef,
    ObjectRef,
    OpRef,
    Ref,
    TableRef,
    maybe_parse_uri,
    parse_op_uri,
    parse_uri,
)
from weave.trace.sanitize import REDACTED_VALUE, should_redact
from weave.trace.serialization.serialize import (
    from_json,
    isinstance_namedtuple,
    to_json,
)
from weave.trace.serialization.serializer import get_serializer_for_obj
from weave.trace.settings import (
    client_parallelism,
    should_capture_client_info,
    should_capture_system_info,
    should_print_call_link,
    should_redact_pii,
)
from weave.trace.table import Table
from weave.trace.util import deprecated, log_once
from weave.trace.vals import WeaveObject, WeaveTable, make_trace_obj
from weave.trace.weave_client import make_client_call
from weave.trace_server.constants import MAX_DISPLAY_NAME_LENGTH, MAX_OBJECT_NAME_LENGTH
from weave.trace_server.ids import generate_id
from weave.trace_server.interface.feedback_types import (
    RUNNABLE_FEEDBACK_TYPE_PREFIX,
    runnable_feedback_output_selector,
)
from weave.trace_server import trace_server_interface as tsi

if TYPE_CHECKING:
    from weave.flow.dataset import Dataset
    from weave.flow.eval import Evaluation
    from weave.flow.feedback import FeedbackDataset
    from weave.flow.model import Model
    from weave.flow.prompt.prompt import Prompt
    from weave.flow.scorer import Scorer
    from weave.trace.run import Run
    from weave.trace.weave_init import InitializedClient

try:
    from .async_http_trace_server import AsyncRemoteHTTPTraceServer
except ImportError:
    raise ImportError(
        "The async WeaveClient requires httpx. Install it with: pip install httpx"
    )

logger = logging.getLogger(__name__)

RefType = TypeVar("RefType", bound=Ref)
ObjType = TypeVar("ObjType")
ObjSchemaType = TypeVar("ObjSchemaType", bound=pydantic.BaseModel)


class AsyncWeaveClient:
    """Async version of WeaveClient."""

    def __init__(
        self,
        entity: str,
        project: str,
        server: AsyncRemoteHTTPTraceServer,
        ensure_project_exists: bool = True,
    ):
        self.entity = entity
        self.project = project
        self.server = server
        self._anonymous_ops: dict[str, Op] = {}
        self.ensure_project_exists = ensure_project_exists
        self._project_exists_checked = False

    async def __aenter__(self) -> AsyncWeaveClient:
        """Async context manager entry."""
        if self.ensure_project_exists and not self._project_exists_checked:
            resp = await self.server.ensure_project_exists(self.entity, self.project)
            self.project = resp.project_name
            self._project_exists_checked = True
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.server.close()

    def _ref_is_own(self, ref: Ref) -> bool:
        """Check if a reference belongs to this client's project."""
        return ref.entity == self.entity and ref.project == self.project

    def _project_id(self) -> str:
        """Get project ID."""
        return f"{self.entity}/{self.project}"

    async def create_call(
        self,
        op: str | Op,
        inputs: dict[str, Any],
        parent: Optional[str | CallRef] = None,
        thread_id: Optional[str] = None,
        turn_id: Optional[str] = None,
        display_name: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
        use_stack: bool = True,
    ) -> tuple[str, tsi.StartedCallSchemaForInsert]:
        """Create a call (async version)."""
        op_name: str
        if isinstance(op, str):
            op_name = op
        elif isinstance(op, Op):
            op_name = op.ref(self).uri()
        else:
            raise ValueError(f"Invalid op type: {type(op)}")

        # Generate IDs
        call_id = generate_id()
        trace_id = generate_id()

        # Handle parent
        parent_id = None
        if parent:
            if isinstance(parent, str):
                parent_id = parent
            elif isinstance(parent, CallRef):
                parent_id = parent.id
                trace_id = parent.trace_id

        # Create call schema
        started_at = datetime.datetime.now(datetime.timezone.utc)
        
        # Serialize inputs
        inputs_with_refs = to_json(inputs, self._project_id(), self.server)
        
        # Prepare attributes
        call_attributes = attributes or {}
        
        # Create the call
        req = tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=self._project_id(),
                id=call_id,
                op_name=op_name,
                display_name=display_name,
                trace_id=trace_id,
                parent_id=parent_id,
                thread_id=thread_id,
                turn_id=turn_id,
                started_at=started_at,
                attributes=call_attributes,
                inputs=inputs_with_refs,
            )
        )

        await self.server.call_start(req)
        
        return call_id, req.start

    async def finish_call(
        self,
        call_id: str,
        output: Any = None,
        exception: Optional[str] = None,
        op: Optional[Op] = None,
        summary: Optional[dict[str, Any]] = None,
    ) -> None:
        """Finish a call (async version)."""
        ended_at = datetime.datetime.now(datetime.timezone.utc)
        
        # Serialize output
        output_with_refs = None
        if output is not None:
            output_with_refs = to_json(output, self._project_id(), self.server)
        
        # Create end request
        req = tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=self._project_id(),
                id=call_id,
                ended_at=ended_at,
                output=output_with_refs,
                exception=exception,
                summary=summary or {},  # Default to empty dict if None
            )
        )
        
        await self.server.call_end(req)

    async def save(
        self,
        obj: Any,
        name: str,
        branch: str = "latest",
    ) -> ObjectRef:
        """Save an object (async version)."""
        if name and len(name) > MAX_OBJECT_NAME_LENGTH:
            raise ValueError(
                f"Object name must be less than {MAX_OBJECT_NAME_LENGTH} characters. Received {len(name)} characters."
            )

        # Check if it's already saved
        cur_ref = get_ref(obj)
        if cur_ref is not None:
            if self._ref_is_own(cur_ref):
                return cur_ref
            else:
                obj = remove_ref(obj)

        # Serialize object
        serialized = to_json(obj, self._project_id(), self.server)
        
        # Create object
        req = tsi.ObjCreateReq(
            obj=tsi.ObjSchemaForInsert(
                project_id=self._project_id(),
                object_id=name,  # Use name as object_id like sync client
                val=serialized,
            )
        )
        
        res = await self.server.obj_create(req)
        
        # Create reference
        if is_op(obj):
            ref = OpRef(
                entity=self.entity,
                project=self.project,
                name=name,
                _digest=res.digest,
            )
        else:
            ref = ObjectRef(
                entity=self.entity,
                project=self.project,
                name=name,
                _digest=res.digest,
            )
        
        # Set ref on object
        try:
            set_ref(obj, ref)
        except Exception:
            # Don't worry if we can't set the ref.
            # This can happen for primitive types that don't have __dict__
            pass
        
        return ref

    async def get(
        self,
        ref: str | ObjectRef,
    ) -> Any:
        """Get an object by reference (async version)."""
        if isinstance(ref, str):
            ref = parse_uri(ref)
            if not isinstance(ref, ObjectRef):
                raise ValueError(f"Invalid object reference: {ref}")
        
        req = tsi.ObjReadReq(
            project_id=f"{ref.entity}/{ref.project}",
            object_id=ref.name,  # ObjectRef uses name, not object_id
            digest=ref._digest,
        )
        
        res = await self.server.obj_read(req)
        
        # Update ref with actual digest
        ref = dataclasses.replace(ref, _digest=res.obj.digest)
        
        # Deserialize
        obj = from_json(res.obj.val, f"{ref.entity}/{ref.project}", self.server)
        
        # Convert to trace object
        weave_obj = make_trace_obj(obj, ref, self.server, None)
        
        return maybe_objectify(weave_obj)

    async def calls(
        self,
        filter: Optional[CallsFilterLike] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort: Optional[list[SortByLike]] = None,
    ) -> list[WeaveObject]:
        """Query calls (async version)."""
        req = tsi.CallsQueryReq(
            project_id=self._project_id(),
            filter=filter,
            limit=limit,
            offset=offset,
            sort_by=sort,
        )
        
        res = await self.server.calls_query(req)
        
        calls = []
        for call_schema in res.calls:
            # Use make_client_call to create proper Call objects
            call_obj = make_client_call(
                self.entity,
                self.project,
                call_schema,
                self.server,
            )
            calls.append(call_obj)
        
        return calls

    async def op(self, name: str) -> Optional[Op]:
        """Get an operation by name (async version)."""
        req = tsi.OpReadReq(
            project_id=self._project_id(),
            name=name,
        )
        
        try:
            res = await self.server.op_read(req)
            # Deserialize the op
            return from_json(res.op_obj.val, self._project_id(), self.server)
        except Exception:
            return None

    async def objects(
        self,
        filter: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[WeaveObject]:
        """Query objects (async version)."""
        req = tsi.ObjQueryReq(
            project_id=self._project_id(),
            filter=filter,
            limit=limit,
            offset=offset,
        )
        
        res = await self.server.objs_query(req)
        
        objects = []
        for obj_schema in res.objs:
            # Deserialize and add to list
            obj = from_json(obj_schema.val, self._project_id(), self.server)
            
            # Create reference
            ref = ObjectRef(
                entity=self.entity,
                project=self.project,
                object_id=obj_schema.object_id,
                name=obj_schema.name,
                _digest=obj_schema.digest,
            )
            set_ref(obj, ref)
            
            objects.append(obj)
        
        return objects

    async def table(
        self,
        name: str,
        rows: Optional[list[dict[str, Any]]] = None,
    ) -> Table:
        """Create or get a table (async version)."""
        # Create table if rows provided
        if rows is not None:
            table = Table(rows=rows)
            ref = await self.save(table, name)
            return table
        else:
            # Get existing table
            ref = ObjectRef(
                entity=self.entity,
                project=self.project,
                name=name,
            )
            return await self.get(ref)

    async def dataset(self, name: str, rows: Optional[list[dict[str, Any]]] = None):
        """Create or get a dataset (async version)."""
        # This would require async Dataset implementation
        # For now, we'll raise NotImplementedError
        raise NotImplementedError("Async Dataset not yet implemented")

    async def model(self, name: str):
        """Get a model (async version)."""
        # This would require async Model implementation
        raise NotImplementedError("Async Model not yet implemented")

    async def evaluation(self, name: str):
        """Get an evaluation (async version)."""
        # This would require async Evaluation implementation
        raise NotImplementedError("Async Evaluation not yet implemented")

    async def scorer(self, name: str):
        """Get a scorer (async version)."""
        # This would require async Scorer implementation
        raise NotImplementedError("Async Scorer not yet implemented")

    async def prompt(self, name: str):
        """Get a prompt (async version)."""
        # This would require async Prompt implementation
        raise NotImplementedError("Async Prompt not yet implemented")

    async def feedback(
        self,
        call: Union[str, WeaveObject, CallRef],
        feedback_type: str,
        payload: dict[str, Any],
    ) -> str:
        """Add feedback to a call (async version)."""
        # Get call ref URI
        weave_ref: str
        if isinstance(call, str):
            # Assume it's a call ID, create ref URI
            weave_ref = f"weave:///{self.entity}/{self.project}/call/{call}"
        elif isinstance(call, CallRef):
            weave_ref = call.uri()
        elif hasattr(call, "id"):
            # It's a Call object
            weave_ref = f"weave:///{self.entity}/{self.project}/call/{call.id}"
        else:
            raise ValueError(f"Invalid call type: {type(call)}")
        
        # Create feedback
        req = tsi.FeedbackCreateReq(
            project_id=self._project_id(),
            weave_ref=weave_ref,
            feedback_type=feedback_type,
            payload=payload,
        )
        
        res = await self.server.feedback_create(req)
        return res.id

    async def get_feedback(
        self,
        call: Optional[Union[str, WeaveObject, CallRef]] = None,
        feedback_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Get feedback (async version)."""
        # Build filter
        where: dict[str, Any] = {}
        if call:
            call_id: str
            if isinstance(call, str):
                call_id = call
            elif isinstance(call, CallRef):
                call_id = call.id
            elif hasattr(call, "id"):
                call_id = call.id
            else:
                raise ValueError(f"Invalid call type: {type(call)}")
            where["call_id"] = call_id
        
        if feedback_type:
            where["feedback_type"] = feedback_type
        
        req = tsi.FeedbackQueryReq(
            project_id=self._project_id(),
            where=where if where else None,
            limit=limit,
            offset=offset,
        )
        
        res = await self.server.feedback_query(req)
        
        return [fb.model_dump() for fb in res.feedback]

    def ref(self, obj: Any) -> ObjectRef:
        """Get reference for an object (sync method, doesn't need async)."""
        cur_ref = get_ref(obj)
        if cur_ref is not None:
            return cur_ref
        raise ValueError("Object does not have a reference")

    async def delete_call(self, call: Union[str, CallRef]) -> None:
        """Delete a call (async version)."""
        call_id: str
        if isinstance(call, str):
            call_id = call
        elif isinstance(call, CallRef):
            call_id = call.id
        else:
            raise ValueError(f"Invalid call type: {type(call)}")
        
        req = tsi.CallsDeleteReq(
            project_id=self._project_id(),
            call_ids=[call_id],
        )
        
        await self.server.calls_delete(req)

    async def delete_object(self, obj: Union[str, ObjectRef]) -> None:
        """Delete an object (async version)."""
        if isinstance(obj, str):
            ref = parse_uri(obj)
            if not isinstance(ref, ObjectRef):
                raise ValueError(f"Invalid object reference: {obj}")
        else:
            ref = obj
        
        req = tsi.ObjDeleteReq(
            project_id=f"{ref.entity}/{ref.project}",
            object_id=ref.object_id,
            digest=ref._digest,
        )
        
        await self.server.obj_delete(req)

    async def close(self) -> None:
        """Close the client."""
        await self.server.close()