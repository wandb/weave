"""ClickHouse handler for the dataset_sources provenance system.

The SQL construction lives in
``query_builder.dataset_sources_query_builder``; this module wires those
builders to the trace server's bound callables (``_query``/``_insert``) plus the
``table_routing_resolver`` and ``ch_client``, and hydrates result rows into
dataset_sources schemas. It mirrors the ``agents/clickhouse.py`` precedent: the
public ``TraceServerInterface`` methods on ``ClickHouseTraceServer`` stay thin
delegators to this handler.

Every symbol below is imported from its ORIGINAL definition site (query
builders, errors, clickhouse utilities, sentinel values, orm). Nothing here
imports ``clickhouse_trace_server_batched``, so ``batched.py`` can import this
module at the top alongside the agents handlers without an import cycle.
"""

from __future__ import annotations

import datetime
import json
import logging
from collections.abc import Callable
from typing import Any

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.ch_sentinel_values import SENTINEL_EPOCH
from weave.trace_server.clickhouse.utilities import ensure_datetimes_have_tz
from weave.trace_server.errors import InvalidRequest, RequestTooLarge
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_builder import (
    make_spans_existence_query,
)
from weave.trace_server.query_builder.annotation_queues_query_builder import (
    make_queue_add_calls_fetch_calls_query,
)
from weave.trace_server.query_builder.dataset_sources_query_builder import (
    DATASET_SOURCES_INSERT_COLUMNS,
    deterministic_link_id,
    make_dataset_sources_select,
    make_link_state_by_ids_query,
    make_link_state_query,
    make_source_datasets_select,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DatasetSourcesHandler:
    """Wires dataset_sources query builders to the trace server's callables."""

    def __init__(
        self,
        query: Callable[..., Any],
        insert: Callable[..., Any],
        table_routing_resolver: Any,
        ch_client: Any,
    ) -> None:
        self._query = query
        self._insert = insert
        self.table_routing_resolver = table_routing_resolver
        self.ch_client = ch_client

    def link(self, req: tsi.DatasetSourcesLinkReq) -> tsi.DatasetSourcesLinkRes:
        """Link dataset rows to provenance sources (calls/spans).

        Insert-only write: link, relink, and restore are all INSERTs of a new
        ReplacingMergeTree version with a fresh updated_at. The deterministic id
        keeps relink idempotent.
        """
        # Flatten to (row_digest, SourceRef) tuples preserving input order.
        flat: list[tuple[str, tsi.SourceRef, dict[str, Any] | None]] = []
        for payload in req.links:
            for source in payload.sources:
                flat.append((payload.row_digest, source, payload.link_metadata))

        if len(flat) > tsi.MAX_DATASET_SOURCE_LINKS_PER_REQUEST:
            raise RequestTooLarge(
                f"dataset_sources_link accepts at most "
                f"{tsi.MAX_DATASET_SOURCE_LINKS_PER_REQUEST} links per request, "
                f"got {len(flat)}"
            )

        if not flat:
            return tsi.DatasetSourcesLinkRes(entries=[])

        # D4 write-layer invariants: a conversation spans traces, so its identity
        # is the conversation_id alone (source_trace_id=''); calls/spans need the
        # trace in their key ('' would collapse distinct edges). source_kind in
        # the key is the firewall that keeps a conversation link from colliding
        # with a call/span link.
        for _row_digest, source, _meta in flat:
            if source.source_kind == tsi.SourceKind.CONVERSATION:
                if source.source_trace_id != "":
                    raise InvalidRequest(
                        "dataset_sources_link: conversation links must carry "
                        f"source_trace_id='' (got {source.source_trace_id!r}); a "
                        "conversation spans traces."
                    )
            elif source.source_kind == tsi.SourceKind.SPAN:  # noqa: SIM102
                # A span's identity is (trace_id, span_id); the trace_id is the
                # lookup key, so it must be supplied.
                if source.source_trace_id == "":
                    raise InvalidRequest(
                        "dataset_sources_link: span links require a non-empty "
                        "source_trace_id (identity is (trace_id, span_id))."
                    )
            # CALL: source_trace_id is redundant for identity (call_id is
            # globally unique) and is derived authoritatively below, so the
            # client need not supply it.

        # Validate source existence + fetch cached display fields, split by kind.
        # Maps source_id -> (source_display_name, source_started_at, trace_id).
        # Conversation links are ASSERTED (D3): no backing table, so no existence
        # check and no cached source fields are fetched.
        call_fields = self._fetch_call_source_fields(req.project_id, flat)
        span_fields = self._fetch_span_source_fields(req.project_id, flat)

        # Detect any missing call/span sources -> fail fast, no partial writes.
        missing: list[tuple[str, str]] = []
        for _row_digest, source, _meta in flat:
            if source.source_kind == tsi.SourceKind.CALL:
                if source.source_id not in call_fields:
                    missing.append((source.source_kind.value, source.source_id))
            elif source.source_kind == tsi.SourceKind.SPAN:
                key = (source.source_trace_id, source.source_id)
                if key not in span_fields:
                    missing.append((source.source_kind.value, source.source_id))
        if missing:
            # Dedup while preserving order.
            unique_missing = list(dict.fromkeys(missing))
            raise InvalidRequest(
                "dataset_sources_link: the following sources were not found in "
                f"project {req.project_id!r}: {unique_missing}"
            )

        now = datetime.datetime.now(datetime.timezone.utc)

        # Optionally look up prior link state for created/created_at semantics.
        prior_state: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        if req.include_created_status:
            prior_state = self._fetch_dataset_link_state(
                req.project_id, req.dataset_object_id, flat
            )

        rows: list[list[Any]] = []
        entries: list[tsi.DatasetSourcesLinkResEntry] = []
        for row_digest, source, meta in flat:
            kind = source.source_kind.value
            if source.source_kind == tsi.SourceKind.CALL:
                # trace_id is authoritative from the call record; the client
                # value is ignored (redundant for call identity).
                display_name, started_at, source_trace_id = call_fields[
                    source.source_id
                ]
            elif source.source_kind == tsi.SourceKind.SPAN:
                # The client trace_id IS the validated span lookup key.
                key = (source.source_trace_id, source.source_id)
                display_name, started_at = span_fields[key]
                source_trace_id = source.source_trace_id
            else:
                # Conversation: asserted link, no cached fields, no trace.
                display_name, started_at, source_trace_id = "", now, ""

            link_id = deterministic_link_id(
                req.project_id,
                req.dataset_object_id,
                row_digest,
                kind,
                source.source_id,
                source_trace_id,
            )

            logical_key = (row_digest, kind, source.source_id, source_trace_id)
            created: bool | None
            created_at = now
            if req.include_created_status:
                prior = prior_state.get(logical_key)
                # created=False means an existing row (live or tombstoned) was
                # matched; a soft-deleted link being relinked is a RESTORE, not
                # a create. created_at carries forward to preserve first_seen.
                created = prior is None
                if prior is not None and prior.get("created_at") is not None:
                    created_at = prior["created_at"]
            else:
                # Blind write: no lookup ran; created is "not requested" (None)
                # and created_at is refreshed to now.
                created = None

            link_metadata_str = json.dumps(meta) if meta is not None else ""

            rows.append(
                [
                    link_id,
                    req.project_id,
                    req.dataset_object_id,
                    row_digest,
                    kind,
                    source.source_id,
                    source_trace_id,
                    started_at,
                    display_name,
                    link_metadata_str,
                    req.wb_user_id or "",
                    created_at,
                    now,
                    SENTINEL_EPOCH,  # deleted_at sentinel (epoch = live)
                ]
            )
            entries.append(
                tsi.DatasetSourcesLinkResEntry(link_id=link_id, created=created)
            )

        # dataset_digest is audit-only (never stored on the rows): record
        # which dataset version these links were asserted against.
        logger.info(
            "dataset_sources_link",
            extra={
                "project_id": req.project_id,
                "dataset_object_id": req.dataset_object_id,
                "dataset_digest": req.dataset_digest,
                "added_by": req.wb_user_id or "",
                "link_count": len(rows),
            },
        )

        self._insert(
            "dataset_sources",
            rows,
            column_names=DATASET_SOURCES_INSERT_COLUMNS,
        )

        return tsi.DatasetSourcesLinkRes(entries=entries)

    def _fetch_call_source_fields(
        self,
        project_id: str,
        flat: list[tuple[str, tsi.SourceRef, dict[str, Any] | None]],
    ) -> dict[str, tuple[str, datetime.datetime, str]]:
        """Fetch (display_name, started_at, trace_id) for each linked call.

        Reuses the calls-owned ``make_queue_add_calls_fetch_calls_query`` (the
        provenance feature owns no SQL against calls_merged). Returns a map
        keyed by call_id; calls not present are simply absent (-> missing).
        """
        call_ids = sorted(
            {
                source.source_id
                for _rd, source, _meta in flat
                if source.source_kind == tsi.SourceKind.CALL
            }
        )
        if not call_ids:
            return {}
        read_table = self.table_routing_resolver.resolve_read_table(
            project_id, self.ch_client
        )
        pb = ParamBuilder()
        query = make_queue_add_calls_fetch_calls_query(
            project_id=project_id,
            call_ids=call_ids,
            pb=pb,
            read_table=read_table,
        )
        result = self._query(query, parameters=pb.get_params())
        out: dict[str, tuple[str, datetime.datetime, str]] = {}
        for row in result.named_results():
            out[row["id"]] = (
                row["op_name"] or "",
                row["started_at"],
                row["trace_id"] or "",
            )
        return out

    def _fetch_span_source_fields(
        self,
        project_id: str,
        flat: list[tuple[str, tsi.SourceRef, dict[str, Any] | None]],
    ) -> dict[tuple[str, str], tuple[str, datetime.datetime]]:
        """Fetch (span_name, started_at) for each linked span.

        Uses the agents-owned ``make_spans_existence_query`` (the spans table
        belongs to the agents module). Returns a map keyed by
        (trace_id, span_id); spans not present are absent (-> missing).
        """
        span_keys = sorted(
            {
                (source.source_trace_id, source.source_id)
                for _rd, source, _meta in flat
                if source.source_kind == tsi.SourceKind.SPAN
            }
        )
        if not span_keys:
            return {}
        pb = ParamBuilder()
        query = make_spans_existence_query(pb, project_id, span_keys)
        result = self._query(query, parameters=pb.get_params())
        out: dict[tuple[str, str], tuple[str, datetime.datetime]] = {}
        for row in result.named_results():
            out[row["trace_id"], row["span_id"]] = (
                row["span_name"] or "",
                row["started_at"],
            )
        return out

    def _fetch_dataset_link_state(
        self,
        project_id: str,
        dataset_object_id: str,
        flat: list[tuple[str, tsi.SourceRef, dict[str, Any] | None]],
    ) -> dict[tuple[str, str, str, str], dict[str, Any]]:
        """Collapsed link state keyed by (row_digest, kind, source_id, trace_id).

        source_trace_id is part of the logical key (D1): two spans sharing a
        span_id across different traces on the same row_digest are distinct
        links and must not alias in the prior-state lookup.
        """
        logical_keys = sorted(
            {(row_digest, source.source_id) for row_digest, source, _meta in flat}
        )
        pb = ParamBuilder()
        query = make_link_state_query(project_id, dataset_object_id, logical_keys, pb)
        result = self._query(query, parameters=pb.get_params())
        out: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for row in result.named_results():
            out[
                row["row_digest"],
                row["source_kind"],
                row["source_id"],
                row["source_trace_id"],
            ] = row
        return out

    def link_delete(
        self, req: tsi.DatasetSourcesLinkDeleteReq
    ) -> tsi.DatasetSourcesLinkDeleteRes:
        """Soft-delete links by id via insert-only tombstone versions."""
        if not req.link_ids:
            return tsi.DatasetSourcesLinkDeleteRes(entries=[])

        pb = ParamBuilder()
        query = make_link_state_by_ids_query(req.project_id, req.link_ids, pb)
        result = self._query(query, parameters=pb.get_params())
        by_id: dict[str, dict[str, Any]] = {
            row["id"]: row for row in result.named_results()
        }

        # Any requested id not found (project-scoped query) -> fail fast.
        missing = [lid for lid in req.link_ids if lid not in by_id]
        if missing:
            raise InvalidRequest(
                "dataset_sources_link_delete: the following link ids were not "
                f"found in project {req.project_id!r}: {missing}"
            )

        now = datetime.datetime.now(datetime.timezone.utc)
        rows: list[list[Any]] = []
        entries: list[tsi.DatasetSourcesLinkDeleteResEntry] = []
        for link_id in req.link_ids:
            row = by_id[link_id]
            if ensure_datetimes_have_tz(row["deleted_at"]) != SENTINEL_EPOCH:
                # Already soft-deleted (deleted_at past the sentinel epoch).
                entries.append(
                    tsi.DatasetSourcesLinkDeleteResEntry(link_id=link_id, deleted=False)
                )
                continue
            # Tombstone version: same logical key + id, carry forward created_at
            # and cached source fields, fresh updated_at, deleted_at=now.
            rows.append(
                [
                    link_id,
                    row["project_id"],
                    row["dataset_object_id"],
                    row["row_digest"],
                    row["source_kind"],
                    row["source_id"],
                    row["source_trace_id"],
                    row["source_started_at"],
                    row["source_display_name"],
                    row["link_metadata"],
                    row["added_by"],
                    row["created_at"],
                    now,
                    now,  # deleted_at
                ]
            )
            entries.append(
                tsi.DatasetSourcesLinkDeleteResEntry(link_id=link_id, deleted=True)
            )

        if rows:
            self._insert(
                "dataset_sources",
                rows,
                column_names=DATASET_SOURCES_INSERT_COLUMNS,
            )

        return tsi.DatasetSourcesLinkDeleteRes(entries=entries)

    def query(self, req: tsi.DatasetSourcesQueryReq) -> tsi.DatasetSourcesQueryRes:
        """Forward query: dataset -> sources."""
        pb = ParamBuilder()
        query = make_dataset_sources_select(
            req.project_id,
            req.dataset_object_id,
            pb,
            row_digests=req.row_digests,
            source_kinds=(
                [k.value for k in req.source_kinds]
                if req.source_kinds is not None
                else None
            ),
            include_deleted=req.include_deleted,
            limit=req.limit,
            offset=req.offset,
        )
        result = self._query(query, parameters=pb.get_params())
        links = [_dataset_source_link_from_row(row) for row in result.named_results()]
        return tsi.DatasetSourcesQueryRes(links=links)

    def source_datasets_query(
        self, req: tsi.SourceDatasetsQueryReq
    ) -> tsi.SourceDatasetsQueryRes:
        """Reverse query: sources -> datasets."""
        if not req.sources:
            return tsi.SourceDatasetsQueryRes(memberships=[])

        sources = [
            (s.source_kind.value, s.source_id, s.source_trace_id) for s in req.sources
        ]
        pb = ParamBuilder()
        query = make_source_datasets_select(
            req.project_id,
            sources,
            pb,
            include_deleted=req.include_deleted,
            row_digests_cap=tsi.MAX_ROW_DIGESTS_PER_RESULT,
        )
        result = self._query(query, parameters=pb.get_params())
        memberships = []
        for row in result.named_results():
            total = int(row["row_digests_total_count"])
            memberships.append(
                tsi.SourceDatasetMembership(
                    source_kind=tsi.SourceKind(row["source_kind"]),
                    source_id=row["source_id"],
                    source_trace_id=row["source_trace_id"],
                    dataset_object_id=row["dataset_object_id"],
                    row_digests=list(row["row_digests"]),
                    row_digests_truncated=total > tsi.MAX_ROW_DIGESTS_PER_RESULT,
                    row_digests_total_count=total,
                    first_seen_at=row["first_seen_at"],
                )
            )
        return tsi.SourceDatasetsQueryRes(memberships=memberships)


def _dataset_source_link_from_row(row: dict[str, Any]) -> tsi.DatasetSourceLinkSchema:
    """Hydrate a DatasetSourceLinkSchema from an argMax-collapsed query row.

    link_metadata is stored as a JSON string ('' for None); deserialize to a
    dict (None when empty).
    """
    raw_metadata = row.get("link_metadata") or ""
    link_metadata = json.loads(raw_metadata) if raw_metadata else None
    # Sentinels map back to None: '' added_by and the 1970 epoch deleted_at are
    # the non-nullable stand-ins for "no user" / "live".
    deleted_at = ensure_datetimes_have_tz(row["deleted_at"])
    return tsi.DatasetSourceLinkSchema(
        id=row["id"],
        row_digest=row["row_digest"],
        source_kind=tsi.SourceKind(row["source_kind"]),
        source_id=row["source_id"],
        source_trace_id=row["source_trace_id"],
        source_started_at=row["source_started_at"],
        source_display_name=row["source_display_name"],
        link_metadata=link_metadata,
        added_by=row["added_by"] or None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=None if deleted_at == SENTINEL_EPOCH else deleted_at,
    )
