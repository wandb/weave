# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from . import shared
from .. import _compat
from .shared import (
    Expr as Expr,
    Operation as Operation,
    ConvertSpec as ConvertSpec,
    EqOperation as EqOperation,
    GtOperation as GtOperation,
    InOperation as InOperation,
    OrOperation as OrOperation,
    AndOperation as AndOperation,
    ContainsSpec as ContainsSpec,
    GteOperation as GteOperation,
    NotOperation as NotOperation,
    ConvertOperation as ConvertOperation,
    GetFieldOperator as GetFieldOperator,
    LiteralOperation as LiteralOperation,
    ContainsOperation as ContainsOperation,
)
from .call_end_params import CallEndParams as CallEndParams
from .server_info_res import ServerInfoRes as ServerInfoRes
from .call_read_params import CallReadParams as CallReadParams
from .call_start_params import CallStartParams as CallStartParams
from .call_usage_params import CallUsageParams as CallUsageParams
from .cost_purge_params import CostPurgeParams as CostPurgeParams
from .cost_query_params import CostQueryParams as CostQueryParams
from .file_stats_params import FileStatsParams as FileStatsParams
from .v2_op_list_params import V2OpListParams as V2OpListParams
from .v2_op_read_params import V2OpReadParams as V2OpReadParams
from .call_delete_params import CallDeleteParams as CallDeleteParams
from .call_read_response import CallReadResponse as CallReadResponse
from .call_update_params import CallUpdateParams as CallUpdateParams
from .cost_create_params import CostCreateParams as CostCreateParams
from .file_create_params import FileCreateParams as FileCreateParams
from .object_read_params import ObjectReadParams as ObjectReadParams
from .table_query_params import TableQueryParams as TableQueryParams
from .trace_usage_params import TraceUsageParams as TraceUsageParams
from .call_start_response import CallStartResponse as CallStartResponse
from .call_usage_response import CallUsageResponse as CallUsageResponse
from .cost_query_response import CostQueryResponse as CostQueryResponse
from .file_content_params import FileContentParams as FileContentParams
from .file_stats_response import FileStatsResponse as FileStatsResponse
from .object_query_params import ObjectQueryParams as ObjectQueryParams
from .table_create_params import TableCreateParams as TableCreateParams
from .table_update_params import TableUpdateParams as TableUpdateParams
from .v2_op_create_params import V2OpCreateParams as V2OpCreateParams
from .v2_op_delete_params import V2OpDeleteParams as V2OpDeleteParams
from .v2_op_read_response import V2OpReadResponse as V2OpReadResponse
from .call_delete_response import CallDeleteResponse as CallDeleteResponse
from .cost_create_response import CostCreateResponse as CostCreateResponse
from .file_create_response import FileCreateResponse as FileCreateResponse
from .object_create_params import ObjectCreateParams as ObjectCreateParams
from .object_delete_params import ObjectDeleteParams as ObjectDeleteParams
from .object_read_response import ObjectReadResponse as ObjectReadResponse
from .table_query_response import TableQueryResponse as TableQueryResponse
from .trace_usage_response import TraceUsageResponse as TraceUsageResponse
from .v2_model_list_params import V2ModelListParams as V2ModelListParams
from .v2_score_list_params import V2ScoreListParams as V2ScoreListParams
from .feedback_purge_params import FeedbackPurgeParams as FeedbackPurgeParams
from .feedback_query_params import FeedbackQueryParams as FeedbackQueryParams
from .object_query_response import ObjectQueryResponse as ObjectQueryResponse
from .ref_read_batch_params import RefReadBatchParams as RefReadBatchParams
from .table_create_response import TableCreateResponse as TableCreateResponse
from .table_update_response import TableUpdateResponse as TableUpdateResponse
from .v2_op_create_response import V2OpCreateResponse as V2OpCreateResponse
from .v2_op_delete_response import V2OpDeleteResponse as V2OpDeleteResponse
from .feedback_create_params import FeedbackCreateParams as FeedbackCreateParams
from .object_create_response import ObjectCreateResponse as ObjectCreateResponse
from .object_delete_response import ObjectDeleteResponse as ObjectDeleteResponse
from .v2_dataset_list_params import V2DatasetListParams as V2DatasetListParams
from .v2_model_create_params import V2ModelCreateParams as V2ModelCreateParams
from .v2_model_delete_params import V2ModelDeleteParams as V2ModelDeleteParams
from .v2_model_read_response import V2ModelReadResponse as V2ModelReadResponse
from .v2_score_create_params import V2ScoreCreateParams as V2ScoreCreateParams
from .v2_score_delete_params import V2ScoreDeleteParams as V2ScoreDeleteParams
from .v2_score_list_response import V2ScoreListResponse as V2ScoreListResponse
from .v2_score_read_response import V2ScoreReadResponse as V2ScoreReadResponse
from .call_query_stats_params import CallQueryStatsParams as CallQueryStatsParams
from .feedback_query_response import FeedbackQueryResponse as FeedbackQueryResponse
from .feedback_replace_params import FeedbackReplaceParams as FeedbackReplaceParams
from .ref_read_batch_response import RefReadBatchResponse as RefReadBatchResponse
from .v2_scorer_create_params import V2ScorerCreateParams as V2ScorerCreateParams
from .v2_scorer_delete_params import V2ScorerDeleteParams as V2ScorerDeleteParams
from .v2_scorer_read_response import V2ScorerReadResponse as V2ScorerReadResponse
from .call_stream_query_params import CallStreamQueryParams as CallStreamQueryParams
from .call_upsert_batch_params import CallUpsertBatchParams as CallUpsertBatchParams
from .feedback_create_response import FeedbackCreateResponse as FeedbackCreateResponse
from .table_query_stats_params import TableQueryStatsParams as TableQueryStatsParams
from .v2_dataset_create_params import V2DatasetCreateParams as V2DatasetCreateParams
from .v2_dataset_delete_params import V2DatasetDeleteParams as V2DatasetDeleteParams
from .v2_dataset_read_response import V2DatasetReadResponse as V2DatasetReadResponse
from .v2_model_create_response import V2ModelCreateResponse as V2ModelCreateResponse
from .v2_model_delete_response import V2ModelDeleteResponse as V2ModelDeleteResponse
from .v2_score_create_response import V2ScoreCreateResponse as V2ScoreCreateResponse
from .v2_score_delete_response import V2ScoreDeleteResponse as V2ScoreDeleteResponse
from .call_query_stats_response import CallQueryStatsResponse as CallQueryStatsResponse
from .feedback_replace_response import FeedbackReplaceResponse as FeedbackReplaceResponse
from .v2_prediction_list_params import V2PredictionListParams as V2PredictionListParams
from .v2_scorer_create_response import V2ScorerCreateResponse as V2ScorerCreateResponse
from .v2_scorer_delete_response import V2ScorerDeleteResponse as V2ScorerDeleteResponse
from .call_upsert_batch_response import CallUpsertBatchResponse as CallUpsertBatchResponse
from .table_query_stats_response import TableQueryStatsResponse as TableQueryStatsResponse
from .thread_stream_query_params import ThreadStreamQueryParams as ThreadStreamQueryParams
from .v2_dataset_create_response import V2DatasetCreateResponse as V2DatasetCreateResponse
from .v2_dataset_delete_response import V2DatasetDeleteResponse as V2DatasetDeleteResponse
from .v2_evaluation_create_params import V2EvaluationCreateParams as V2EvaluationCreateParams
from .v2_evaluation_delete_params import V2EvaluationDeleteParams as V2EvaluationDeleteParams
from .v2_evaluation_read_response import V2EvaluationReadResponse as V2EvaluationReadResponse
from .v2_prediction_create_params import V2PredictionCreateParams as V2PredictionCreateParams
from .v2_prediction_delete_params import V2PredictionDeleteParams as V2PredictionDeleteParams
from .v2_prediction_list_response import V2PredictionListResponse as V2PredictionListResponse
from .v2_prediction_read_response import V2PredictionReadResponse as V2PredictionReadResponse
from .feedback_batch_create_params import FeedbackBatchCreateParams as FeedbackBatchCreateParams
from .service_projects_info_params import ServiceProjectsInfoParams as ServiceProjectsInfoParams
from .v2_evaluation_create_response import V2EvaluationCreateResponse as V2EvaluationCreateResponse
from .v2_evaluation_delete_response import V2EvaluationDeleteResponse as V2EvaluationDeleteResponse
from .v2_evaluation_run_list_params import V2EvaluationRunListParams as V2EvaluationRunListParams
from .v2_prediction_create_response import V2PredictionCreateResponse as V2PredictionCreateResponse
from .v2_prediction_delete_response import V2PredictionDeleteResponse as V2PredictionDeleteResponse
from .v2_prediction_finish_response import V2PredictionFinishResponse as V2PredictionFinishResponse
from .feedback_batch_create_response import FeedbackBatchCreateResponse as FeedbackBatchCreateResponse
from .service_projects_info_response import ServiceProjectsInfoResponse as ServiceProjectsInfoResponse
from .table_query_stats_batch_params import TableQueryStatsBatchParams as TableQueryStatsBatchParams
from .v2_evaluation_run_create_params import V2EvaluationRunCreateParams as V2EvaluationRunCreateParams
from .v2_evaluation_run_delete_params import V2EvaluationRunDeleteParams as V2EvaluationRunDeleteParams
from .v2_evaluation_run_finish_params import V2EvaluationRunFinishParams as V2EvaluationRunFinishParams
from .v2_evaluation_run_list_response import V2EvaluationRunListResponse as V2EvaluationRunListResponse
from .v2_evaluation_run_read_response import V2EvaluationRunReadResponse as V2EvaluationRunReadResponse
from .table_create_from_digests_params import TableCreateFromDigestsParams as TableCreateFromDigestsParams
from .table_query_stats_batch_response import TableQueryStatsBatchResponse as TableQueryStatsBatchResponse
from .v2_evaluation_run_create_response import V2EvaluationRunCreateResponse as V2EvaluationRunCreateResponse
from .v2_evaluation_run_delete_response import V2EvaluationRunDeleteResponse as V2EvaluationRunDeleteResponse
from .v2_evaluation_run_finish_response import V2EvaluationRunFinishResponse as V2EvaluationRunFinishResponse
from .table_create_from_digests_response import TableCreateFromDigestsResponse as TableCreateFromDigestsResponse

# Rebuild cyclical models only after all modules are imported.
# This ensures that, when building the deferred (due to cyclical references) model schema,
# Pydantic can resolve the necessary references.
# See: https://github.com/pydantic/pydantic/issues/11250 for more context.
if _compat.PYDANTIC_V1:
    shared.and_operation.AndOperation.update_forward_refs()  # type: ignore
    shared.contains_operation.ContainsOperation.update_forward_refs()  # type: ignore
    shared.contains_spec.ContainsSpec.update_forward_refs()  # type: ignore
    shared.convert_operation.ConvertOperation.update_forward_refs()  # type: ignore
    shared.convert_spec.ConvertSpec.update_forward_refs()  # type: ignore
    shared.literal_operation.LiteralOperation.update_forward_refs()  # type: ignore
    shared.or_operation.OrOperation.update_forward_refs()  # type: ignore
else:
    shared.and_operation.AndOperation.model_rebuild(_parent_namespace_depth=0)
    shared.contains_operation.ContainsOperation.model_rebuild(_parent_namespace_depth=0)
    shared.contains_spec.ContainsSpec.model_rebuild(_parent_namespace_depth=0)
    shared.convert_operation.ConvertOperation.model_rebuild(_parent_namespace_depth=0)
    shared.convert_spec.ConvertSpec.model_rebuild(_parent_namespace_depth=0)
    shared.literal_operation.LiteralOperation.model_rebuild(_parent_namespace_depth=0)
    shared.or_operation.OrOperation.model_rebuild(_parent_namespace_depth=0)
