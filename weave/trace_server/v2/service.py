"""Trace service implementation (Tier 2) — business logic.

Consumes StorageInterface for data access. Handles:
  - Request validation and processing
  - ID translation (external ↔ internal) via IdConverter
  - Content digesting (files, objects)
  - Orchestration (op_create = file + object + read-back)
  - Converts API Req/Res types ↔ internal row types

This is the code that currently lives scattered inside
ClickHouseTraceServer.call_start, .obj_create, .op_create, etc.
Extracted here as a standalone service that composes with any storage.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from typing import Any

from weave.trace_server import object_creation_utils
from weave.trace_server.external_to_internal_trace_server_adapter import (
    IdConverter,
)
from weave.trace_server.service_interface import (
    EnsureProjectExistsRes,
    ProjectsInfoReq,
    ProjectsInfoRes,
    ServerInfoRes,
)
from weave.trace_server.trace_server_interface import (
    AliasesListReq,
    AliasesListRes,
    CallEndReq,
    CallEndRes,
    CallReadReq,
    CallReadRes,
    CallSchema,
    CallsDeleteReq,
    CallsDeleteRes,
    CallsQueryReq,
    CallsQueryStatsReq,
    CallsQueryStatsRes,
    CallStartReq,
    CallStartRes,
    CallStartV2Req,
    CallStartV2Res,
    CallsUpsertCompleteReq,
    CallsUpsertCompleteRes,
    CallUpdateReq,
    CallUpdateRes,
    CostCreateReq,
    CostCreateRes,
    CostPurgeReq,
    CostPurgeRes,
    CostQueryReq,
    CostQueryRes,
    DatasetCreateReq,
    DatasetCreateRes,
    DatasetDeleteReq,
    DatasetDeleteRes,
    DatasetListReq,
    DatasetReadReq,
    DatasetReadRes,
    EvalResultsQueryReq,
    EvalResultsQueryRes,
    EvaluationCreateReq,
    EvaluationCreateRes,
    EvaluationDeleteReq,
    EvaluationDeleteRes,
    EvaluationListReq,
    EvaluationReadReq,
    EvaluationReadRes,
    EvaluationRunCreateReq,
    EvaluationRunCreateRes,
    EvaluationRunDeleteReq,
    EvaluationRunDeleteRes,
    EvaluationRunFinishReq,
    EvaluationRunFinishRes,
    EvaluationRunListReq,
    EvaluationRunReadReq,
    EvaluationRunReadRes,
    FeedbackCreateReq,
    FeedbackCreateRes,
    FileContentReadReq,
    FileContentReadRes,
    FileCreateReq,
    FileCreateRes,
    ModelCreateReq,
    ModelCreateRes,
    ModelDeleteReq,
    ModelDeleteRes,
    ModelListReq,
    ModelReadReq,
    ModelReadRes,
    ObjAddTagsReq,
    ObjAddTagsRes,
    ObjCreateReq,
    ObjCreateRes,
    ObjDeleteReq,
    ObjDeleteRes,
    ObjQueryReq,
    ObjQueryRes,
    ObjReadReq,
    ObjReadRes,
    ObjRemoveAliasesReq,
    ObjRemoveAliasesRes,
    ObjRemoveTagsReq,
    ObjRemoveTagsRes,
    ObjSetAliasesReq,
    ObjSetAliasesRes,
    OpCreateReq,
    OpCreateRes,
    OpDeleteReq,
    OpDeleteRes,
    OpListReq,
    OpReadReq,
    OpReadRes,
    PredictionCreateReq,
    PredictionCreateRes,
    PredictionDeleteReq,
    PredictionDeleteRes,
    PredictionFinishReq,
    PredictionFinishRes,
    PredictionListReq,
    PredictionReadReq,
    PredictionReadRes,
    RefsReadBatchReq,
    RefsReadBatchRes,
    ScoreCreateReq,
    ScoreCreateRes,
    ScoreDeleteReq,
    ScoreDeleteRes,
    ScoreListReq,
    ScoreReadReq,
    ScoreReadRes,
    ScorerCreateReq,
    ScorerCreateRes,
    ScorerDeleteReq,
    ScorerDeleteRes,
    ScorerListReq,
    ScorerReadReq,
    ScorerReadRes,
    TableCreateFromDigestsReq,
    TableCreateFromDigestsRes,
    TableCreateReq,
    TableCreateRes,
    TableQueryReq,
    TableQueryRes,
    TableQueryStatsReq,
    TableQueryStatsRes,
    TableUpdateReq,
    TableUpdateRes,
    TagsListReq,
    TagsListRes,
)
from weave.trace_server.v2.storage_interface import (
    CallCompleteRow,
    CallRow,
    FeedbackRow,
    FileRow,
    ObjectRow,
    StorageInterface,
)


def _compute_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class TraceService:
    """Business logic layer. Validates, processes, orchestrates.

    Accepts API request types, translates IDs if an IdConverter is
    provided, converts to internal row types, delegates to storage.
    """

    def __init__(
        self,
        storage: StorageInterface,
        id_converter: IdConverter | None = None,
    ) -> None:
        self._storage = storage
        self._idc = id_converter

    def _ext_project(self, project_id: str) -> str:
        """Translate external project_id to internal, if converter present."""
        if self._idc is not None:
            return self._idc.ext_to_int_project_id(project_id)
        return project_id

    # ── Service ──────────────────────────────────────────────────────

    def server_info(self) -> ServerInfoRes:
        return ServerInfoRes(
            min_required_weave_python_version="0.0.0",
            trace_server_version="v2",
        )

    def ensure_project_exists(
        self, entity: str, project: str
    ) -> EnsureProjectExistsRes:
        # In production, delegates to wandb_interface.project_creator
        return EnsureProjectExistsRes(project_name=project)

    def projects_info(self, req: ProjectsInfoReq) -> list[ProjectsInfoRes]:
        return []

    # ── Calls ────────────────────────────────────────────────────────

    def call_start(self, req: CallStartReq) -> CallStartRes:
        start = req.start
        if start.id is None:
            raise ValueError("id is required")
        if start.trace_id is None:
            raise ValueError("trace_id is required")

        project_id = self._ext_project(start.project_id)

        # Business logic: convert API request → internal row
        row = CallRow(
            project_id=project_id,
            id=start.id,
            trace_id=start.trace_id,
            parent_id=start.parent_id,
            op_name=start.op_name,
            display_name=start.display_name,
            started_at=start.started_at.isoformat() if start.started_at else None,
            inputs=start.inputs,
            wb_run_id=start.wb_run_id,
            wb_user_id=start.wb_user_id,
        )

        # Storage: raw insert
        self._storage.insert_call(row)

        return CallStartRes(id=start.id, trace_id=start.trace_id)

    def call_end(self, req: CallEndReq) -> CallEndRes:
        end = req.end
        project_id = self._ext_project(end.project_id)

        updates: dict[str, Any] = {
            "ended_at": end.ended_at.isoformat() if end.ended_at else None,
            "exception": end.exception,
            "summary": json.dumps(end.summary) if end.summary else None,
        }
        if end.output is not None:
            updates["output"] = json.dumps(end.output)

        self._storage.update_call(project_id, end.id, updates)
        return CallEndRes()

    def call_start_v2(self, req: CallStartV2Req) -> CallStartV2Res:
        # V2 start — same as call_start but for eager ops
        res = self.call_start(CallStartReq(start=req.start))
        return CallStartV2Res(id=res.id, trace_id=res.trace_id)

    def calls_complete(
        self, req: CallsUpsertCompleteReq
    ) -> CallsUpsertCompleteRes:
        for item in req.batch:
            project_id = self._ext_project(item.project_id)
            row = CallCompleteRow(
                project_id=project_id,
                id=item.id,
                trace_id=item.trace_id,
                parent_id=item.parent_id,
                op_name=item.op_name,
                started_at=item.started_at.isoformat() if item.started_at else None,
                ended_at=item.ended_at.isoformat() if item.ended_at else None,
                inputs=item.inputs,
                output=item.output,
                summary=item.summary,
                exception=item.exception,
                wb_run_id=item.wb_run_id,
                wb_user_id=item.wb_user_id,
            )
            self._storage.insert_call_complete(row)
        return CallsUpsertCompleteRes()

    def call_read(self, req: CallReadReq) -> CallReadRes:
        project_id = self._ext_project(req.project_id)
        row = self._storage.query_calls(
            project_id, filters={"id": req.id}, limit=1
        )
        if not row.rows:
            return CallReadRes(call=None)
        return CallReadRes(call=CallSchema(**row.rows[0]))

    def call_update(self, req: CallUpdateReq) -> CallUpdateRes:
        project_id = self._ext_project(req.project_id)
        self._storage.update_call(project_id, req.call_id, req.updates)
        return CallUpdateRes()

    def calls_query_stream(
        self, req: CallsQueryReq
    ) -> Iterator[CallSchema]:
        project_id = self._ext_project(req.project_id)
        for row in self._storage.query_calls_stream(project_id):
            yield CallSchema(**row)

    def calls_query_stats(
        self, req: CallsQueryStatsReq
    ) -> CallsQueryStatsRes:
        project_id = self._ext_project(req.project_id)
        result = self._storage.query_calls(project_id)
        return CallsQueryStatsRes(count=len(result.rows))

    def calls_delete(self, req: CallsDeleteReq) -> CallsDeleteRes:
        project_id = self._ext_project(req.project_id)
        self._storage.delete_calls(project_id, req.call_ids)
        return CallsDeleteRes()

    # ── Objects ──────────────────────────────────────────────────────

    def obj_create(self, req: ObjCreateReq) -> ObjCreateRes:
        obj = req.obj
        project_id = self._ext_project(obj.project_id)

        # Business logic: compute digest from value
        val_json = json.dumps(obj.val, sort_keys=True)
        digest = hashlib.sha256(val_json.encode()).hexdigest()

        row = ObjectRow(
            project_id=project_id,
            object_id=obj.object_id,
            kind="object",
            val=obj.val,
            digest=digest,
            wb_user_id=obj.wb_user_id,
        )

        self._storage.insert_object(row)
        return ObjCreateRes(digest=digest, object_id=obj.object_id)

    def obj_read(self, req: ObjReadReq) -> ObjReadRes:
        project_id = self._ext_project(req.project_id)
        row = self._storage.read_object(
            project_id,
            req.object_id,
            digest=req.digest,
            version_index=req.version_index,
        )
        if row is None:
            return ObjReadRes(obj=None)
        return ObjReadRes(obj=row)

    def obj_delete(self, req: ObjDeleteReq) -> ObjDeleteRes:
        project_id = self._ext_project(req.project_id)
        self._storage.delete_object(
            project_id, req.object_id, req.digests
        )
        return ObjDeleteRes()

    def objs_query(self, req: ObjQueryReq) -> ObjQueryRes:
        project_id = self._ext_project(req.project_id)
        rows = self._storage.query_objects(project_id)
        return ObjQueryRes(objs=rows)

    def obj_add_tags(self, req: ObjAddTagsReq) -> ObjAddTagsRes:
        project_id = self._ext_project(req.project_id)
        self._storage.insert_tags(project_id, req.object_id, req.tags)
        return ObjAddTagsRes()

    def obj_remove_tags(self, req: ObjRemoveTagsReq) -> ObjRemoveTagsRes:
        project_id = self._ext_project(req.project_id)
        self._storage.remove_tags(project_id, req.object_id, req.tags)
        return ObjRemoveTagsRes()

    def obj_set_aliases(self, req: ObjSetAliasesReq) -> ObjSetAliasesRes:
        project_id = self._ext_project(req.project_id)
        self._storage.insert_aliases(project_id, req.object_id, req.aliases)
        return ObjSetAliasesRes()

    def obj_remove_aliases(
        self, req: ObjRemoveAliasesReq
    ) -> ObjRemoveAliasesRes:
        project_id = self._ext_project(req.project_id)
        self._storage.remove_aliases(
            project_id, req.object_id, req.aliases
        )
        return ObjRemoveAliasesRes()

    def tags_list(self, req: TagsListReq) -> TagsListRes:
        project_id = self._ext_project(req.project_id)
        tags = self._storage.query_tags(project_id)
        return TagsListRes(tags=tags)

    def aliases_list(self, req: AliasesListReq) -> AliasesListRes:
        project_id = self._ext_project(req.project_id)
        aliases = self._storage.query_aliases(project_id)
        return AliasesListRes(aliases=aliases)

    # ── Tables ───────────────────────────────────────────────────────

    def table_create(self, req: TableCreateReq) -> TableCreateRes:
        project_id = self._ext_project(req.table.project_id)
        # Simplified — production does row digesting
        from weave.trace_server.v2.storage_interface import TableRowData

        rows = [
            TableRowData(project_id=project_id, digest="", val=r.val)
            for r in req.table.rows
        ]
        digest = self._storage.insert_table(project_id, rows)
        return TableCreateRes(digest=digest)

    def table_create_from_digests(
        self, req: TableCreateFromDigestsReq
    ) -> TableCreateFromDigestsRes:
        raise NotImplementedError("table_create_from_digests")

    def table_update(self, req: TableUpdateReq) -> TableUpdateRes:
        project_id = self._ext_project(req.project_id)
        new_digest = self._storage.update_table(
            project_id, req.base_digest, req.updates
        )
        return TableUpdateRes(digest=new_digest)

    def table_query(self, req: TableQueryReq) -> TableQueryRes:
        project_id = self._ext_project(req.project_id)
        result = self._storage.query_table(project_id, req.digest)
        return TableQueryRes(rows=result.rows)

    def table_query_stats(
        self, req: TableQueryStatsReq
    ) -> TableQueryStatsRes:
        project_id = self._ext_project(req.project_id)
        stats = self._storage.query_table_stats(project_id, req.digest)
        return TableQueryStatsRes(count=stats.get("count", 0))

    def refs_read_batch(self, req: RefsReadBatchReq) -> RefsReadBatchRes:
        vals = self._storage.read_refs_batch(req.refs)
        return RefsReadBatchRes(vals=vals)

    # ── Files ────────────────────────────────────────────────────────

    def file_create(self, req: FileCreateReq) -> FileCreateRes:
        digest = _compute_digest(req.content)
        row = FileRow(
            project_id=self._ext_project(req.project_id),
            name=req.name,
            digest=digest,
            content=req.content,
        )
        self._storage.insert_file(row)
        return FileCreateRes(digest=digest)

    def file_content_read(
        self, req: FileContentReadReq
    ) -> FileContentReadRes:
        project_id = self._ext_project(req.project_id)
        content = self._storage.read_file(project_id, req.digest)
        return FileContentReadRes(content=content)

    # ── Feedback ─────────────────────────────────────────────────────

    def feedback_create(self, req: FeedbackCreateReq) -> FeedbackCreateRes:
        project_id = self._ext_project(req.project_id)
        row = FeedbackRow(
            project_id=project_id,
            weave_ref=req.weave_ref,
            feedback_type=req.feedback_type,
            payload=req.payload,
            wb_user_id=req.wb_user_id,
        )
        feedback_id = self._storage.insert_feedback(row)
        return FeedbackCreateRes(
            id=feedback_id, created_at="", wb_user_id=req.wb_user_id or ""
        )

    # ── Costs ────────────────────────────────────────────────────────

    def cost_create(self, req: CostCreateReq) -> CostCreateRes:
        project_id = self._ext_project(req.project_id)
        self._storage.insert_cost(project_id, req.costs)
        return CostCreateRes(ids=[])

    def cost_purge(self, req: CostPurgeReq) -> CostPurgeRes:
        project_id = self._ext_project(req.project_id)
        self._storage.purge_costs(project_id, req.cost_ids)
        return CostPurgeRes()

    def cost_query(self, req: CostQueryReq) -> CostQueryRes:
        project_id = self._ext_project(req.project_id)
        results = self._storage.query_costs(project_id)
        return CostQueryRes(results=results)

    # ── Object API (orchestrated operations) ─────────────────────────

    def op_create(self, req: OpCreateReq) -> OpCreateRes:
        """Orchestrates: create file → build payload → create object → read back."""
        project_id = self._ext_project(req.project_id)

        # 1. Create the source file
        source_code = req.source_code or object_creation_utils.PLACEHOLDER_OP_SOURCE
        file_res = self.file_create(
            FileCreateReq(
                project_id=project_id,
                name=object_creation_utils.OP_SOURCE_FILE_NAME,
                content=source_code.encode("utf-8"),
            )
        )

        # 2. Build structured op payload
        op_val = object_creation_utils.build_op_val(file_res.digest)
        object_id = object_creation_utils.make_object_id(req.name, "Op")

        # 3. Create the object
        from weave.trace_server.trace_server_interface import ObjSchemaForInsert

        obj_res = self.obj_create(
            ObjCreateReq(
                obj=ObjSchemaForInsert(
                    project_id=project_id,
                    object_id=object_id,
                    val=op_val,
                    wb_user_id=None,
                )
            )
        )

        return OpCreateRes(
            digest=obj_res.digest,
            object_id=object_id,
            version_index=0,
        )

    def op_read(self, req: OpReadReq) -> OpReadRes:
        raise NotImplementedError("op_read")

    def op_list(self, req: OpListReq) -> Iterator[OpReadRes]:
        raise NotImplementedError("op_list")

    def op_delete(self, req: OpDeleteReq) -> OpDeleteRes:
        raise NotImplementedError("op_delete")

    def dataset_create(self, req: DatasetCreateReq) -> DatasetCreateRes:
        raise NotImplementedError("dataset_create")

    def dataset_read(self, req: DatasetReadReq) -> DatasetReadRes:
        raise NotImplementedError("dataset_read")

    def dataset_list(self, req: DatasetListReq) -> Iterator[DatasetReadRes]:
        raise NotImplementedError("dataset_list")

    def dataset_delete(self, req: DatasetDeleteReq) -> DatasetDeleteRes:
        raise NotImplementedError("dataset_delete")

    def scorer_create(self, req: ScorerCreateReq) -> ScorerCreateRes:
        raise NotImplementedError("scorer_create")

    def scorer_read(self, req: ScorerReadReq) -> ScorerReadRes:
        raise NotImplementedError("scorer_read")

    def scorer_list(self, req: ScorerListReq) -> Iterator[ScorerReadRes]:
        raise NotImplementedError("scorer_list")

    def scorer_delete(self, req: ScorerDeleteReq) -> ScorerDeleteRes:
        raise NotImplementedError("scorer_delete")

    def evaluation_create(
        self, req: EvaluationCreateReq
    ) -> EvaluationCreateRes:
        raise NotImplementedError("evaluation_create")

    def evaluation_read(self, req: EvaluationReadReq) -> EvaluationReadRes:
        raise NotImplementedError("evaluation_read")

    def evaluation_list(
        self, req: EvaluationListReq
    ) -> Iterator[EvaluationReadRes]:
        raise NotImplementedError("evaluation_list")

    def evaluation_delete(
        self, req: EvaluationDeleteReq
    ) -> EvaluationDeleteRes:
        raise NotImplementedError("evaluation_delete")

    def model_create(self, req: ModelCreateReq) -> ModelCreateRes:
        raise NotImplementedError("model_create")

    def model_read(self, req: ModelReadReq) -> ModelReadRes:
        raise NotImplementedError("model_read")

    def model_list(self, req: ModelListReq) -> Iterator[ModelReadRes]:
        raise NotImplementedError("model_list")

    def model_delete(self, req: ModelDeleteReq) -> ModelDeleteRes:
        raise NotImplementedError("model_delete")

    def evaluation_run_create(
        self, req: EvaluationRunCreateReq
    ) -> EvaluationRunCreateRes:
        raise NotImplementedError("evaluation_run_create")

    def evaluation_run_read(
        self, req: EvaluationRunReadReq
    ) -> EvaluationRunReadRes:
        raise NotImplementedError("evaluation_run_read")

    def evaluation_run_list(
        self, req: EvaluationRunListReq
    ) -> Iterator[EvaluationRunReadRes]:
        raise NotImplementedError("evaluation_run_list")

    def evaluation_run_delete(
        self, req: EvaluationRunDeleteReq
    ) -> EvaluationRunDeleteRes:
        raise NotImplementedError("evaluation_run_delete")

    def evaluation_run_finish(
        self, req: EvaluationRunFinishReq
    ) -> EvaluationRunFinishRes:
        raise NotImplementedError("evaluation_run_finish")

    def prediction_create(
        self, req: PredictionCreateReq
    ) -> PredictionCreateRes:
        raise NotImplementedError("prediction_create")

    def prediction_read(self, req: PredictionReadReq) -> PredictionReadRes:
        raise NotImplementedError("prediction_read")

    def prediction_list(
        self, req: PredictionListReq
    ) -> Iterator[PredictionReadRes]:
        raise NotImplementedError("prediction_list")

    def prediction_delete(
        self, req: PredictionDeleteReq
    ) -> PredictionDeleteRes:
        raise NotImplementedError("prediction_delete")

    def prediction_finish(
        self, req: PredictionFinishReq
    ) -> PredictionFinishRes:
        raise NotImplementedError("prediction_finish")

    def score_create(self, req: ScoreCreateReq) -> ScoreCreateRes:
        raise NotImplementedError("score_create")

    def score_read(self, req: ScoreReadReq) -> ScoreReadRes:
        raise NotImplementedError("score_read")

    def score_list(self, req: ScoreListReq) -> Iterator[ScoreReadRes]:
        raise NotImplementedError("score_list")

    def score_delete(self, req: ScoreDeleteReq) -> ScoreDeleteRes:
        raise NotImplementedError("score_delete")

    def eval_results_query(
        self, req: EvalResultsQueryReq
    ) -> EvalResultsQueryRes:
        raise NotImplementedError("eval_results_query")
