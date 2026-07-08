"""Base64 content conversion utilities for trace server.

This module handles automatic detection and replacement of base64 encoded content
with content objects stored in bucket storage.
"""

import hashlib
import json
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, TypeVar

from cachetools import LRUCache

from weave.shared.digest import compute_object_digest_result
from weave.shared.refs_internal import InternalObjectRef
from weave.trace_server.content.content import Content
from weave.trace_server.object_creation_utils import make_object_id
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallEndV2Req,
    CallStartReq,
    CompletedCallSchemaForInsert,
    FileCreateReq,
    ObjCreateReq,
    ObjSchemaForInsert,
    TraceServerInterface,
)
from weave.trace_server.tracing import traced

logger = logging.getLogger(__name__)

# Pattern to match data URIs with base64 encoded content
# Format: data:[content-type];base64,[base64_data]
DATA_URI_PATTERN = re.compile(r"^data:([^;]+);base64,([A-Za-z0-9+/=]+)$", re.IGNORECASE)

# Pattern to match standalone base64 strings
BASE64_PATTERN = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")

# Minimum string length we'll consider for auto-conversion to a Content object.
#
# Lifted from 1 KiB to 8 KiB: under the old threshold every long LLM output,
# serialized tool-call argument, and large system prompt in the 1-8 KiB range
# was put through ``is_data_uri`` + ``is_base64`` + (occasionally)
# ``Content.from_base64`` even though those strings are essentially never
# real binary payloads. Genuine multimodal blobs (PNG/JPEG/WebP/audio) start
# comfortably above 8 KiB once base64-encoded; small icons that happen to
# fall below 8 KiB now stay inline in ClickHouse, which is the pre-feature
# behaviour and is handled correctly by the existing storage path.
AUTO_CONVERSION_MIN_SIZE = 8192  # 8 KiB

# Per-pod memo of published content refs keyed by (project_id, sha256 of the raw
# base64/data-URI string). Agent payloads re-send the same blobs on every chat
# turn (e.g. screenshot history); a hit skips the decode, both file uploads, and
# the obj_create insert entirely and returns the previously published ref.
CONTENT_REF_CACHE_SIZE = 100_000
_content_ref_cache: LRUCache[tuple[str, str], str] = LRUCache(
    maxsize=CONTENT_REF_CACHE_SIZE
)
_content_ref_cache_lock = threading.Lock()


def _content_ref_cache_key(project_id: str, raw_val: str) -> tuple[str, str]:
    return (project_id, hashlib.sha256(raw_val.encode("utf-8")).hexdigest())


def _content_ref_cache_get(key: tuple[str, str]) -> str | None:
    with _content_ref_cache_lock:
        return _content_ref_cache.get(key)


def _content_ref_cache_put(key: tuple[str, str], ref: str) -> None:
    with _content_ref_cache_lock:
        _content_ref_cache[key] = ref


def _lookup_content_ref(
    cache_key: tuple[str, str], pending_objs: "PendingContentObjs | None"
) -> str | None:
    """Known ref for this content: the global cache of published refs first,
    then this request's queued-but-uncommitted objects.
    """
    if (cached := _content_ref_cache_get(cache_key)) is not None:
        return cached
    if pending_objs is not None:
        return pending_objs.get_ref(cache_key)
    return None


@dataclass
class _PendingContentEntry:
    project_id: str
    object_id: str
    cache_key: tuple[str, str]
    ref: str
    raw_val: str


@dataclass
class PendingContentObjs:
    """Content objects queued for one batched write.

    Tracks enough per object to dedupe repeats of the same content within the
    batch (`get_ref`), publish the global ref cache only once the whole batch
    has committed (`publish_refs`), and restore the original raw value
    wherever a skipped object's ref was embedded (`restore_map`).
    """

    objs: list[ObjSchemaForInsert] = field(default_factory=list)
    _entries: list[_PendingContentEntry] = field(default_factory=list)
    _ref_by_cache_key: dict[tuple[str, str], str] = field(default_factory=dict)
    _skipped: set[tuple[str, str]] = field(default_factory=set)

    def add(self, obj: ObjSchemaForInsert, ref: str, raw_val: str) -> None:
        cache_key = _content_ref_cache_key(obj.project_id, raw_val)
        self.objs.append(obj)
        self._entries.append(
            _PendingContentEntry(obj.project_id, obj.object_id, cache_key, ref, raw_val)
        )
        self._ref_by_cache_key[cache_key] = ref

    def get_ref(self, cache_key: tuple[str, str]) -> str | None:
        return self._ref_by_cache_key.get(cache_key)

    def mark_skipped(self, project_id: str, object_id: str) -> None:
        self._skipped.add((project_id, object_id))

    def restore_map(self) -> dict[str, str]:
        """Refs of skipped objects mapped to the raw values they replaced."""
        return {
            e.ref: e.raw_val
            for e in self._entries
            if (e.project_id, e.object_id) in self._skipped
        }

    def publish_refs(self) -> None:
        """Publish non-skipped refs to the global cache.

        Call only after the batch has fully committed (objects, files, and
        calls): a cache hit must always mean the ref resolves.
        """
        for e in self._entries:
            if (e.project_id, e.object_id) not in self._skipped:
                _content_ref_cache_put(e.cache_key, e.ref)


def is_base64(value: str) -> bool:
    """Huerestic to quickly check if a string is likely base64.
    We do not decode here because Content already does decode based 'true' validation
    Args:
        value: String to check
    Returns:
        True if the string is possibly valid base64
    """
    return BASE64_PATTERN.match(value) is not None


def is_data_uri(data_uri: str) -> bool:
    """Extract content type and decoded bytes from a data URI.

    Args:
        data_uri: Data URI string in format data:[content-type];base64,[data]

    Returns:
        bool: True is match, else false
    """
    return DATA_URI_PATTERN.match(data_uri) is not None


@traced(name="store_content_object")
def store_content_object(
    content_obj: Content,
    project_id: str,
    trace_server: TraceServerInterface,
) -> dict[str, Any]:
    """Create a proper Content object structure and store its files.

    Args:
        data: Raw byte content
        original_schema: The schema to restore the original base64 string
        mimetype: MIME type of the content
        project_id: Project ID for storage
        trace_server: Trace server instance for file storage

    Returns:
        Dict representing the Content object in the proper format
    """
    content_data = content_obj.data
    content_metadata = json.dumps(content_obj.model_dump(exclude={"data"})).encode(
        "utf-8"
    )

    # Create files in storage
    # 1. Store the actual content
    content_req = FileCreateReq(
        project_id=project_id, name="content", content=content_data
    )
    content_res = trace_server.file_create(content_req)

    # 2. Store the metadata
    metadata_req = FileCreateReq(
        project_id=project_id, name="metadata.json", content=content_metadata
    )
    metadata_res = trace_server.file_create(metadata_req)

    # We exclude the load op because it isn't possible to get from the server side
    return {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "weave.type_wrappers.Content.content.Content"},
        "files": {"content": content_res.digest, "metadata.json": metadata_res.digest},
    }


@traced(name="store_content_object_ref")
def store_content_object_ref(
    content_obj: Content,
    project_id: str,
    trace_server: TraceServerInterface,
    wb_user_id: str | None = None,
    pending_objs: PendingContentObjs | None = None,
    raw_val: str | None = None,
) -> str:
    """Store a Content object, publish it, and return its internal weave ref.

    ``store_content_object`` returns the inline ``CustomWeaveType`` dict (the
    object *value*); this publishes that value as a weave object so callers can
    embed a compact ``weave-trace-internal:///…`` ref in the payload instead of
    the inline object. The version is the server-computed object digest, so
    identical content dedupes to the same ref.

    When ``pending_objs`` is given, the object is queued there instead of
    being written via ``obj_create`` immediately, so a caller can batch many
    objects into one insert. ``raw_val`` (required in that mode) is the
    original string being replaced, kept so a skipped write can restore it.
    """
    obj_val = store_content_object(content_obj, project_id, trace_server)
    object_id = make_object_id(content_obj.filename, "content")
    if pending_objs is not None:
        if raw_val is None:
            raise ValueError("raw_val is required when queueing into pending_objs")
        digest = compute_object_digest_result(obj_val, None).digest
        ref = _content_ref(project_id, object_id, digest)
        pending_objs.add(
            ObjSchemaForInsert(
                project_id=project_id,
                object_id=object_id,
                val=obj_val,
                wb_user_id=wb_user_id,
                expected_digest=digest,
            ),
            ref,
            raw_val,
        )
        return ref
    res = trace_server.obj_create(
        ObjCreateReq(
            obj=ObjSchemaForInsert(
                project_id=project_id,
                object_id=object_id,
                val=obj_val,
                wb_user_id=wb_user_id,
            )
        )
    )
    return _content_ref(project_id, object_id, res.digest)


def _content_ref(project_id: str, object_id: str, digest: str) -> str:
    # Coerce to a plain ``str``: ``.uri`` is a str subclass (``_CallableStr``)
    # that exact-type checks (JSON/serialization/ref extraction) can reject.
    return str(
        InternalObjectRef(project_id=project_id, name=object_id, version=digest).uri
    )


T = TypeVar("T")


def replace_base64_with_content_objects(
    vals: T,
    project_id: str,
    trace_server: TraceServerInterface,
    wb_user_id: str | None = None,
    pending_objs: PendingContentObjs | None = None,
) -> T:
    """Recursively replace base64 content with Content objects.

    Follows the same pattern as extract_refs_from_values, visiting all values
    and replacing base64 content where found.

    Args:
        vals: Value to process (can be dict, list, or primitive)
        project_id: Project ID for storage
        trace_server: Trace server instance for file storage

    Returns:
        Tuple of (processed_value, list_of_created_refs)
    """

    def _visit_children(items: Any, original: Any, cls: type) -> Any:
        # Walk one level of a collection's children. We allocate a shallow
        # copy of ``original`` (via ``cls(original)``) only on the first
        # child whose subtree returned a new identity, and write subsequent
        # replacements through that copy. When no child changes, the copy
        # is never built and we return ``original`` itself — so any clean
        # no-binary subtree round-trips by identity, not by value.
        copy = None
        for k, v in items:
            new_v = _visit(v)
            if new_v is not v:
                if copy is None:
                    copy = cls(original)
                copy[k] = new_v
        return original if copy is None else copy

    def _visit(val: Any) -> Any:
        # Trace payloads are dominated by deeply-nested chat histories with
        # zero binary content, so the previous "always allocate a fresh
        # dict/list at every level" path was doing a full structural copy
        # of every request for no reason. The shared ``_visit_children``
        # helper keeps the identity-preserving recipe in one place for
        # both collection shapes.
        if isinstance(val, dict):
            return _visit_children(val.items(), val, dict)
        if isinstance(val, list):
            return _visit_children(enumerate(val), val, list)
        if isinstance(val, str) and len(val) > AUTO_CONVERSION_MIN_SIZE:
            # Check for data URI pattern first
            if is_data_uri(val):
                cache_key = _content_ref_cache_key(project_id, val)
                if (known := _lookup_content_ref(cache_key, pending_objs)) is not None:
                    return known
                try:
                    # Publish the content and replace the base64 with its ref.
                    ref = store_content_object_ref(
                        Content.from_data_url(val),
                        project_id,
                        trace_server,
                        wb_user_id,
                        pending_objs,
                        raw_val=val,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to create and store content from data URI with error %s",
                        e,
                    )
                else:
                    # In batch mode the global cache is published only after
                    # the batch commits; pending_objs serves intra-batch hits.
                    if pending_objs is None:
                        _content_ref_cache_put(cache_key, ref)
                    return ref

            if is_base64(val):
                cache_key = _content_ref_cache_key(project_id, val)
                if (known := _lookup_content_ref(cache_key, pending_objs)) is not None:
                    return known
                try:
                    # All we care about here is if this is an object that we can handle in some way.
                    # 'aaaa' is valid base64 and will come out as text/plain
                    # More complicated false positives or failed detections will show 'application/octet-stream'
                    # The uncovered scenario is if a user has encoded a plaintext document as Base64
                    # We don't handle text content objects in a special way on the clients, so this is acceptable.
                    content: Content[Any] = Content.from_base64(val)
                    if content.mimetype not in {
                        "text/plain",
                        "application/octet-stream",
                    }:
                        ref = store_content_object_ref(
                            content,
                            project_id,
                            trace_server,
                            wb_user_id,
                            pending_objs,
                            raw_val=val,
                        )
                        if pending_objs is None:
                            _content_ref_cache_put(cache_key, ref)
                        return ref
                except Exception as e:
                    logger.warning(
                        "Failed to create content from standalone base64: %s", e
                    )

            return val
        return val

    return _visit(vals)


R = TypeVar("R", bound=CallStartReq | CallEndReq | CallEndV2Req)


def process_call_req_to_content(
    req: R,
    trace_server: TraceServerInterface,
) -> R:
    """Process call inputs/outputs to replace base64 content.

    This is the main entry point for processing trace data before insertion.

    Args:
        req: Call request (start, end, or end v2)
        trace_server: Trace server instance

    Returns:
        Request with base64 content replaced by Content objects.
    """
    if isinstance(req, CallStartReq):
        req.start.inputs = replace_base64_with_content_objects(
            req.start.inputs,
            req.start.project_id,
            trace_server,
            req.start.wb_user_id,
        )
    elif isinstance(req, (CallEndReq, CallEndV2Req)):
        # NOTE: EndedCallSchemaForInsert has no ``wb_user_id`` field, so Content
        # objects created from base64 in a call-end ``output`` cannot be
        # user-attributed on this path without a schema change. This falls back
        # to the ``wb_user_id=None`` default (unattributed) — see the report /
        # PR discussion for the required follow-up.
        req.end.output = replace_base64_with_content_objects(
            req.end.output, req.end.project_id, trace_server
        )

    return req


def process_complete_call_to_content(
    complete_call: CompletedCallSchemaForInsert,
    trace_server: TraceServerInterface,
    pending_objs: PendingContentObjs | None = None,
) -> CompletedCallSchemaForInsert:
    """Process a complete call to replace base64 content in inputs and outputs.

    Args:
        complete_call: Complete call schema with both inputs and outputs.
        trace_server: Trace server instance for file storage.
        pending_objs: When given, content objects are queued here instead of
            being written immediately, so a caller can batch the writes.

    Returns:
        CompletedCallSchemaForInsert with base64 content replaced by Content objects.
    """
    complete_call.inputs = replace_base64_with_content_objects(
        complete_call.inputs,
        complete_call.project_id,
        trace_server,
        complete_call.wb_user_id,
        pending_objs,
    )
    complete_call.output = replace_base64_with_content_objects(
        complete_call.output,
        complete_call.project_id,
        trace_server,
        complete_call.wb_user_id,
        pending_objs,
    )
    return complete_call


def restore_raw_content_values(
    complete_call: CompletedCallSchemaForInsert,
    raw_by_ref: dict[str, str],
) -> CompletedCallSchemaForInsert:
    """Replace embedded content refs with the raw values they came from.

    Used when a queued content object was skipped at flush time (name/type
    collision): the call payload keeps the original inline value instead of
    a ref that resolves to nothing.
    """
    complete_call.inputs = _restore_refs(complete_call.inputs, raw_by_ref)
    complete_call.output = _restore_refs(complete_call.output, raw_by_ref)
    return complete_call


def _restore_refs(val: Any, raw_by_ref: dict[str, str]) -> Any:
    if isinstance(val, dict):
        return {k: _restore_refs(v, raw_by_ref) for k, v in val.items()}
    if isinstance(val, list):
        return [_restore_refs(v, raw_by_ref) for v in val]
    if isinstance(val, str):
        return raw_by_ref.get(val, val)
    return val


def replace_base64_in_raw_messages(
    raw: Any,
    project_id: str,
    trace_server: TraceServerInterface,
    wb_user_id: str | None = None,
) -> Any:
    """Strip inline base64 / base64 data-URIs from raw GenAI message payloads.

    Mirrors the non-OTel calls path (``replace_base64_with_content_objects``
    applied to ``inputs``/``output``) for the OTel *agents* path, where the
    message payload frequently arrives as a JSON-encoded string. The string is
    parsed into structured form first so that any inline base64 becomes a leaf
    value the walker can detect, then the shared conversion runs.

    Returns the (possibly converted) structured messages, or the input
    unchanged when it is neither a message container nor JSON-decodable.
    """
    if not isinstance(raw, (str, list, dict)):
        return raw
    parsed = raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    return replace_base64_with_content_objects(
        parsed, project_id, trace_server, wb_user_id
    )
