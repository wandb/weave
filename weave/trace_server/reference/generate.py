from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, NamedTuple

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.params import Header
from fastapi.responses import StreamingResponse

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_service import ServerInfoRes, TraceService
from weave.utils.project_id import to_project_id

SERVICE_TAG_NAME = "Service"
CALLS_TAG_NAME = "Calls"
OPS_TAG_NAME = "Ops"
OBJECTS_TAG_NAME = "Objects"
TABLES_TAG_NAME = "Tables"
REFS_TAG_NAME = "Refs"
FILES_TAG_NAME = "Files"
FEEDBACK_TAG_NAME = "Feedback"
COST_TAG_NAME = "Costs"
COMPLETIONS_TAG_NAME = "Completions"
ACTIONS_TAG_NAME = "Actions"
OTEL_TAG_NAME = "OpenTelemetry"
THREADS_TAG_NAME = "Threads"
OPS_TAG_NAME = "Ops"
DATASETS_TAG_NAME = "Datasets"
SCORERS_TAG_NAME = "Scorers"
EVALUATIONS_TAG_NAME = "Evaluations"
MODELS_TAG_NAME = "Models"
EVALUATION_RUNS_TAG_NAME = "Evaluation Runs"
PREDICTIONS_TAG_NAME = "Predictions"
SCORES_TAG_NAME = "Scores"


class AuthParams(NamedTuple):
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    auth: tuple[str, str] | None = None

    def __hash__(self) -> int:
        return hash(
            (
                tuple(self.headers.items()) if self.headers else None,
                tuple(self.cookies.items()) if self.cookies else None,
                self.auth,
            )
        )


class NoopTraceServer(tsi.FullTraceServerInterface): ...


class NoopTraceService:
    def __init__(self) -> None:
        # This type-ignore is safe, it's just used to instantiate a stub implementation
        # without having to redefine all of the methods (which would be pointless because
        # this is a stub that does nothing).
        self.trace_server_interface: tsi.FullTraceServerInterface = NoopTraceServer()  # type: ignore

    def server_info(self) -> ServerInfoRes:
        return ServerInfoRes(
            min_required_weave_python_version="0.0.1",
        )

    def read_root(self) -> dict[str, str]:
        return {"status": "ok"}


def noop_trace_server_factory(
    auth: AuthParams,
) -> TraceService:
    return NoopTraceService()


class ServiceDependency:
    """Factory for creating server dependencies with proper authorization."""

    def __init__(
        self,
        service_factory: Callable[[AuthParams], TraceService] = (
            noop_trace_server_factory
        ),
        auth_dependency: Callable[[], AuthParams] = lambda: AuthParams(),
    ):
        """Initialize with auth dependencies and server factory.

        Args:
            endpoint_auth_mapping: Dict mapping endpoint names directly to auth dependencies
            server_factory: Function that creates a server from auth params and endpoint name
        """
        self.auth_dependency = auth_dependency
        self.service_factory = service_factory

    def get_service(
        self,
    ) -> Callable[[AuthParams], TraceService]:
        """Get a server dependency with the appropriate auth for the operation."""

        def _get_server(
            auth_params: AuthParams = Depends(self.auth_dependency),  # noqa: B008
        ) -> TraceService:
            return self.service_factory(auth_params)

        return _get_server


def generate_v2_routes(
    router: APIRouter, service_dependency: ServiceDependency
) -> APIRouter:
    """Generate object routes for the FastAPI app.

    Args:
        router: The router to add routes to
        service_dependency: The factory function to create a ServiceDependency.

    Returns:
        The router with object routes implemented
    """
    get_service = service_dependency.get_service()

    @router.post(
        "/{entity}/{project}/ops",
        tags=[OPS_TAG_NAME],
        operation_id="op_create",
    )
    def op_create(
        entity: str,
        project: str,
        body: tsi.OpCreateBody,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.OpCreateRes:
        """Create an op object."""
        project_id = to_project_id(entity, project)
        req = tsi.OpCreateReq(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.op_create(req)

    @router.get(
        "/{entity}/{project}/ops/{object_id}/versions/{digest}",
        tags=[OPS_TAG_NAME],
        operation_id="op_read",
    )
    def op_read(
        entity: str,
        project: str,
        object_id: str,
        digest: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.OpReadRes:
        """Get an op object."""
        project_id = to_project_id(entity, project)
        req = tsi.OpReadReq(project_id=project_id, object_id=object_id, digest=digest)
        return service.trace_server_interface.op_read(req)

    @router.get(
        "/{entity}/{project}/ops",
        tags=[OPS_TAG_NAME],
        operation_id="op_list",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/OpReadRes"},
                        }
                    }
                },
            }
        },
    )
    def op_list(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List op objects."""
        project_id = to_project_id(entity, project)
        req = tsi.OpListReq(project_id=project_id, limit=limit, offset=offset)
        return StreamingResponse(
            service.trace_server_interface.op_list(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/ops/{object_id}",
        tags=[OPS_TAG_NAME],
        operation_id="op_delete",
    )
    def op_delete(
        entity: str,
        project: str,
        object_id: str,
        digests: list[str] | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.OpDeleteRes:
        """Delete an op object. If digests are provided, only those versions are deleted. Otherwise, all versions are deleted."""
        project_id = to_project_id(entity, project)
        req = tsi.OpDeleteReq(
            project_id=project_id, object_id=object_id, digests=digests
        )
        return service.trace_server_interface.op_delete(req)

    @router.post(
        "/{entity}/{project}/datasets",
        tags=[DATASETS_TAG_NAME],
        operation_id="dataset_create",
    )
    def dataset_create(
        entity: str,
        project: str,
        body: tsi.DatasetCreateBody,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.DatasetCreateRes:
        """Create a dataset object."""
        project_id = to_project_id(entity, project)
        req = tsi.DatasetCreateReq(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.dataset_create(req)

    @router.get(
        "/{entity}/{project}/datasets/{object_id}/versions/{digest}",
        tags=[DATASETS_TAG_NAME],
        operation_id="dataset_read",
    )
    def dataset_read(
        entity: str,
        project: str,
        object_id: str,
        digest: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.DatasetReadRes:
        """Get a dataset object."""
        project_id = to_project_id(entity, project)
        req = tsi.DatasetReadReq(
            project_id=project_id, object_id=object_id, digest=digest
        )
        return service.trace_server_interface.dataset_read(req)

    @router.get(
        "/{entity}/{project}/datasets",
        tags=[DATASETS_TAG_NAME],
        operation_id="dataset_list",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/DatasetReadRes"},
                        }
                    }
                },
            }
        },
    )
    def dataset_list(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List dataset objects."""
        project_id = to_project_id(entity, project)
        req = tsi.DatasetListReq(project_id=project_id, limit=limit, offset=offset)
        return StreamingResponse(
            service.trace_server_interface.dataset_list(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/datasets/{object_id}",
        tags=[DATASETS_TAG_NAME],
        operation_id="dataset_delete",
    )
    def dataset_delete(
        entity: str,
        project: str,
        object_id: str,
        digests: list[str] | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.DatasetDeleteRes:
        """Delete a dataset object."""
        project_id = to_project_id(entity, project)
        req = tsi.DatasetDeleteReq(
            project_id=project_id, object_id=object_id, digests=digests
        )
        return service.trace_server_interface.dataset_delete(req)

    @router.post(
        "/{entity}/{project}/scorers",
        tags=[SCORERS_TAG_NAME],
        operation_id="scorer_create",
    )
    def scorer_create(
        entity: str,
        project: str,
        body: tsi.ScorerCreateBody,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScorerCreateRes:
        """Create a scorer object."""
        project_id = to_project_id(entity, project)
        req = tsi.ScorerCreateReq(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.scorer_create(req)

    @router.get(
        "/{entity}/{project}/scorers/{object_id}/versions/{digest}",
        tags=[SCORERS_TAG_NAME],
        operation_id="scorer_read",
    )
    def scorer_read(
        entity: str,
        project: str,
        object_id: str,
        digest: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScorerReadRes:
        """Get a scorer object."""
        project_id = to_project_id(entity, project)
        req = tsi.ScorerReadReq(
            project_id=project_id, object_id=object_id, digest=digest
        )
        return service.trace_server_interface.scorer_read(req)

    @router.get(
        "/{entity}/{project}/scorers",
        tags=[SCORERS_TAG_NAME],
        operation_id="scorer_list",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ScorerReadRes"},
                        }
                    }
                },
            }
        },
    )
    def scorer_list(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List scorer objects."""
        project_id = to_project_id(entity, project)
        req = tsi.ScorerListReq(project_id=project_id, limit=limit, offset=offset)
        return StreamingResponse(
            service.trace_server_interface.scorer_list(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/scorers/{object_id}",
        tags=[SCORERS_TAG_NAME],
        operation_id="scorer_delete",
    )
    def scorer_delete(
        entity: str,
        project: str,
        object_id: str,
        digests: list[str] | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScorerDeleteRes:
        """Delete a scorer object."""
        project_id = to_project_id(entity, project)
        req = tsi.ScorerDeleteReq(
            project_id=project_id, object_id=object_id, digests=digests
        )
        return service.trace_server_interface.scorer_delete(req)

    @router.post(
        "/{entity}/{project}/evaluations",
        tags=[EVALUATIONS_TAG_NAME],
        operation_id="evaluation_create",
    )
    def evaluation_create(
        req: tsi.EvaluationCreateReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationCreateRes:
        """Create an evaluation object."""
        return service.trace_server_interface.evaluation_create(req)

    @router.get(
        "/{entity}/{project}/evaluations/{object_id}/versions/{digest}",
        tags=[EVALUATIONS_TAG_NAME],
        operation_id="evaluation_read",
    )
    def evaluation_read(
        entity: str,
        project: str,
        object_id: str,
        digest: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationReadRes:
        """Get an evaluation object."""
        project_id = to_project_id(entity, project)
        req = tsi.EvaluationReadReq(
            project_id=project_id, object_id=object_id, digest=digest
        )
        return service.trace_server_interface.evaluation_read(req)

    @router.get(
        "/{entity}/{project}/evaluations",
        tags=[EVALUATIONS_TAG_NAME],
        operation_id="evaluation_list",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/EvaluationReadRes"},
                        }
                    }
                },
            }
        },
    )
    def evaluation_list(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List evaluation objects."""
        project_id = to_project_id(entity, project)
        req = tsi.EvaluationListReq(project_id=project_id, limit=limit, offset=offset)
        return StreamingResponse(
            service.trace_server_interface.evaluation_list(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/evaluations/{object_id}",
        tags=[EVALUATIONS_TAG_NAME],
        operation_id="evaluation_delete",
    )
    def evaluation_delete(
        entity: str,
        project: str,
        object_id: str,
        digests: list[str] | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationDeleteRes:
        """Delete an evaluation object."""
        project_id = to_project_id(entity, project)
        req = tsi.EvaluationDeleteReq(
            project_id=project_id, object_id=object_id, digests=digests
        )
        return service.trace_server_interface.evaluation_delete(req)

    @router.post(
        "/{entity}/{project}/evaluation_runs",
        tags=[EVALUATION_RUNS_TAG_NAME],
        operation_id="evaluation_run_create",
    )
    def evaluation_run_create(
        entity: str,
        project: str,
        body: tsi.EvaluationRunCreateBody,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationRunCreateRes:
        """Create an evaluation run."""
        project_id = to_project_id(entity, project)
        req = tsi.EvaluationRunCreateReq(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.evaluation_run_create(req)

    @router.get(
        "/{entity}/{project}/evaluation_runs/{evaluation_run_id}",
        tags=[EVALUATION_RUNS_TAG_NAME],
        operation_id="evaluation_run_read",
    )
    def evaluation_run_read(
        entity: str,
        project: str,
        evaluation_run_id: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationRunReadRes:
        """Get an evaluation run."""
        project_id = to_project_id(entity, project)
        req = tsi.EvaluationRunReadReq(
            project_id=project_id, evaluation_run_id=evaluation_run_id
        )
        return service.trace_server_interface.evaluation_run_read(req)

    @router.get(
        "/{entity}/{project}/evaluation_runs",
        tags=[EVALUATION_RUNS_TAG_NAME],
        operation_id="evaluation_run_list",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/EvaluationRunReadRes"
                            },
                        }
                    }
                },
            }
        },
    )
    def evaluation_run_list(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List evaluation runs."""
        project_id = to_project_id(entity, project)
        req = tsi.EvaluationRunListReq(
            project_id=project_id, limit=limit, offset=offset
        )
        return StreamingResponse(
            service.trace_server_interface.evaluation_run_list(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/evaluation_runs",
        tags=[EVALUATION_RUNS_TAG_NAME],
        operation_id="evaluation_run_delete",
    )
    def evaluation_run_delete(
        entity: str,
        project: str,
        evaluation_run_ids: list[str],
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationRunDeleteRes:
        """Delete evaluation runs."""
        project_id = to_project_id(entity, project)
        req = tsi.EvaluationRunDeleteReq(
            project_id=project_id, evaluation_run_ids=evaluation_run_ids
        )
        return service.trace_server_interface.evaluation_run_delete(req)

    @router.post(
        "/{entity}/{project}/evaluation_runs/{evaluation_run_id}/finish",
        tags=[EVALUATION_RUNS_TAG_NAME],
        operation_id="evaluation_run_finish",
    )
    def evaluation_run_finish(
        entity: str,
        project: str,
        evaluation_run_id: str,
        body: tsi.EvaluationRunFinishBody,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationRunFinishRes:
        """Finish an evaluation run."""
        project_id = to_project_id(entity, project)
        req = tsi.EvaluationRunFinishReq(
            project_id=project_id,
            evaluation_run_id=evaluation_run_id,
            **body.model_dump(),
        )
        return service.trace_server_interface.evaluation_run_finish(req)

    @router.post(
        "/{entity}/{project}/models",
        tags=[MODELS_TAG_NAME],
        operation_id="model_create",
    )
    def model_create(
        entity: str,
        project: str,
        body: tsi.ModelCreateBody,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ModelCreateRes:
        """Create a model object."""
        project_id = to_project_id(entity, project)
        req = tsi.ModelCreateReq(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.model_create(req)

    @router.get(
        "/{entity}/{project}/models/{object_id}/versions/{digest}",
        tags=[MODELS_TAG_NAME],
        operation_id="model_read",
    )
    def model_read(
        entity: str,
        project: str,
        object_id: str,
        digest: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ModelReadRes:
        """Get a model object."""
        project_id = to_project_id(entity, project)
        req = tsi.ModelReadReq(
            project_id=project_id, object_id=object_id, digest=digest
        )
        return service.trace_server_interface.model_read(req)

    @router.get(
        "/{entity}/{project}/models",
        tags=[MODELS_TAG_NAME],
        operation_id="model_list",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ModelReadRes"},
                        }
                    }
                },
            }
        },
    )
    def model_list(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List model objects."""
        project_id = to_project_id(entity, project)
        req = tsi.ModelListReq(project_id=project_id, limit=limit, offset=offset)
        return StreamingResponse(
            service.trace_server_interface.model_list(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/models/{object_id}",
        tags=[MODELS_TAG_NAME],
        operation_id="model_delete",
    )
    def model_delete(
        entity: str,
        project: str,
        object_id: str,
        digests: list[str] | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ModelDeleteRes:
        """Delete a model object. If digests are provided, only those versions are deleted. Otherwise, all versions are deleted."""
        project_id = to_project_id(entity, project)
        req = tsi.ModelDeleteReq(
            project_id=project_id, object_id=object_id, digests=digests
        )
        return service.trace_server_interface.model_delete(req)

    # Prediction Routes

    @router.post(
        "/{entity}/{project}/predictions",
        tags=[PREDICTIONS_TAG_NAME],
        operation_id="prediction_create",
    )
    def prediction_create(
        entity: str,
        project: str,
        body: tsi.PredictionCreateBody,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.PredictionCreateRes:
        """Create a prediction."""
        project_id = to_project_id(entity, project)
        req = tsi.PredictionCreateReq(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.prediction_create(req)

    @router.get(
        "/{entity}/{project}/predictions/{prediction_id}",
        tags=[PREDICTIONS_TAG_NAME],
        operation_id="prediction_read",
    )
    def prediction_read(
        entity: str,
        project: str,
        prediction_id: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.PredictionReadRes:
        """Get a prediction."""
        project_id = to_project_id(entity, project)
        req = tsi.PredictionReadReq(project_id=project_id, prediction_id=prediction_id)
        return service.trace_server_interface.prediction_read(req)

    @router.get(
        "/{entity}/{project}/predictions",
        tags=[PREDICTIONS_TAG_NAME],
        operation_id="prediction_list",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/PredictionReadRes"},
                        }
                    }
                },
            }
        },
    )
    def prediction_list(
        entity: str,
        project: str,
        evaluation_run_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List predictions."""
        project_id = to_project_id(entity, project)
        req = tsi.PredictionListReq(
            project_id=project_id,
            evaluation_run_id=evaluation_run_id,
            limit=limit,
            offset=offset,
        )
        return StreamingResponse(
            service.trace_server_interface.prediction_list(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/predictions",
        tags=[PREDICTIONS_TAG_NAME],
        operation_id="prediction_delete",
    )
    def prediction_delete(
        entity: str,
        project: str,
        prediction_ids: list[str],
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.PredictionDeleteRes:
        """Delete predictions."""
        project_id = to_project_id(entity, project)
        req = tsi.PredictionDeleteReq(
            project_id=project_id, prediction_ids=prediction_ids
        )
        return service.trace_server_interface.prediction_delete(req)

    @router.post(
        "/{entity}/{project}/predictions/{prediction_id}/finish",
        tags=[PREDICTIONS_TAG_NAME],
        operation_id="prediction_finish",
    )
    def prediction_finish(
        entity: str,
        project: str,
        prediction_id: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.PredictionFinishRes:
        """Finish a prediction."""
        print(
            f"DEBUG REST: prediction_finish called with prediction_id={prediction_id}"
        )
        project_id = to_project_id(entity, project)
        req = tsi.PredictionFinishReq(
            project_id=project_id, prediction_id=prediction_id
        )
        print("DEBUG REST: calling trace_server_interface.prediction_finish")
        result = service.trace_server_interface.prediction_finish(req)
        print(f"DEBUG REST: prediction_finish completed, success={result.success}")
        return result

    # Score Routes

    @router.post(
        "/{entity}/{project}/scores",
        tags=[SCORES_TAG_NAME],
        operation_id="score_create",
    )
    def score_create(
        entity: str,
        project: str,
        body: tsi.ScoreCreateBody,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScoreCreateRes:
        """Create a score."""
        project_id = to_project_id(entity, project)
        req = tsi.ScoreCreateReq(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.score_create(req)

    @router.get(
        "/{entity}/{project}/scores/{score_id}",
        tags=[SCORES_TAG_NAME],
        operation_id="score_read",
    )
    def score_read(
        entity: str,
        project: str,
        score_id: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScoreReadRes:
        """Get a score."""
        project_id = to_project_id(entity, project)
        req = tsi.ScoreReadReq(project_id=project_id, score_id=score_id)
        return service.trace_server_interface.score_read(req)

    @router.get(
        "/{entity}/{project}/scores",
        tags=[SCORES_TAG_NAME],
        operation_id="score_list",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ScoreReadRes"},
                        }
                    }
                },
            }
        },
    )
    def score_list(
        entity: str,
        project: str,
        evaluation_run_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List scores."""
        project_id = to_project_id(entity, project)
        req = tsi.ScoreListReq(
            project_id=project_id,
            evaluation_run_id=evaluation_run_id,
            limit=limit,
            offset=offset,
        )
        return StreamingResponse(
            service.trace_server_interface.score_list(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/scores",
        tags=[SCORES_TAG_NAME],
        operation_id="score_delete",
    )
    def score_delete(
        entity: str,
        project: str,
        score_ids: list[str],
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScoreDeleteRes:
        """Delete scores."""
        project_id = to_project_id(entity, project)
        req = tsi.ScoreDeleteReq(project_id=project_id, score_ids=score_ids)
        return service.trace_server_interface.score_delete(req)

    return router


def generate_routes(
    router: APIRouter, service_dependency: ServiceDependency
) -> APIRouter:
    """Generate a FastAPI app from a TraceServerInterface implementation using dependencies.

    Args:
        router: The router to add routes to
        server_dependency: The factory function to create a ServerDependency.  This function
            should return a class that implements TraceServerInterface and handle any
            necessary auth before returning the server.

    Returns:
        The router with all routes implemented
    """
    get_service = service_dependency.get_service()

    # This order is done to minimize diff to the current OpenAPI spec.  Once everything
    # settles, we should refactor this to be in the order of the TraceServerInterface.
    # Commented out blocks are technically not defined on the interface yet and thus
    # not part of the official spec.

    @router.get("/server_info", tags=[SERVICE_TAG_NAME])
    def server_info(
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> ServerInfoRes:
        return service.server_info()

    @router.get("/health", tags=[SERVICE_TAG_NAME])
    def read_root(
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> dict[str, str]:
        return service.read_root()

    @router.post("/otel/v1/trace", tags=[OTEL_TAG_NAME])
    def export_trace(
        req: tsi.OtelExportReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.OtelExportRes:
        return service.trace_server_interface.otel_export(req)

    @router.post("/call/start", tags=[CALLS_TAG_NAME])
    def call_start(
        req: tsi.CallStartReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CallStartRes:
        return service.trace_server_interface.call_start(req)

    @router.post("/call/end", tags=[CALLS_TAG_NAME])
    def call_end(
        req: tsi.CallEndReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CallEndRes:
        return service.trace_server_interface.call_end(req)

    @router.post("/call/upsert_batch", tags=[CALLS_TAG_NAME])
    def call_start_batch(
        req: tsi.CallCreateBatchReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CallCreateBatchRes:
        return service.trace_server_interface.call_start_batch(req)

    @router.post("/calls/delete", tags=[CALLS_TAG_NAME])
    def calls_delete(
        req: tsi.CallsDeleteReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CallsDeleteRes:
        return service.trace_server_interface.calls_delete(req)

    @router.post("/call/update", tags=[CALLS_TAG_NAME])
    def call_update(
        req: tsi.CallUpdateReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CallUpdateRes:
        return service.trace_server_interface.call_update(req)

    @router.post("/call/read", tags=[CALLS_TAG_NAME])
    def call_read(
        req: tsi.CallReadReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CallReadRes:
        return service.trace_server_interface.call_read(req)

    @router.post("/calls/query_stats", tags=[CALLS_TAG_NAME])
    def calls_query_stats(
        req: tsi.CallsQueryStatsReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CallsQueryStatsRes:
        return service.trace_server_interface.calls_query_stats(req)

    @router.post(
        "/calls/stream_query",
        tags=[CALLS_TAG_NAME],
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/CallSchema"},
                        }
                    }
                },
            }
        },
    )
    def calls_query_stream(
        req: tsi.CallsQueryReq,
        service: TraceService = Depends(get_service),  # noqa: B008
        accept: Annotated[str, Header()] = "application/jsonl",
    ) -> StreamingResponse:
        return StreamingResponse(
            service.trace_server_interface.calls_query_stream(req), media_type=accept
        )

    @router.post("/calls/query", tags=[CALLS_TAG_NAME], include_in_schema=False)
    def calls_query(
        req: tsi.CallsQueryReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CallsQueryRes:
        return service.trace_server_interface.calls_query(req)

    @router.post("/obj/create", tags=[OBJECTS_TAG_NAME])
    def obj_create(
        req: tsi.ObjCreateReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ObjCreateRes:
        return service.trace_server_interface.obj_create(req)

    @router.post("/obj/read", tags=[OBJECTS_TAG_NAME])
    def obj_read(
        req: tsi.ObjReadReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ObjReadRes:
        return service.trace_server_interface.obj_read(req)

    @router.post("/objs/query", tags=[OBJECTS_TAG_NAME])
    def objs_query(
        req: tsi.ObjQueryReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ObjQueryRes:
        return service.trace_server_interface.objs_query(req)

    @router.post("/obj/delete", tags=[OBJECTS_TAG_NAME])
    def obj_delete(
        req: tsi.ObjDeleteReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ObjDeleteRes:
        return service.trace_server_interface.obj_delete(req)

    @router.post("/table/create", tags=[TABLES_TAG_NAME])
    def table_create(
        req: tsi.TableCreateReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.TableCreateRes:
        return service.trace_server_interface.table_create(req)

    @router.post("/table/update", tags=[TABLES_TAG_NAME])
    def table_update(
        req: tsi.TableUpdateReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.TableUpdateRes:
        return service.trace_server_interface.table_update(req)

    @router.post("/table/query", tags=[TABLES_TAG_NAME])
    def table_query(
        req: tsi.TableQueryReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.TableQueryRes:
        return service.trace_server_interface.table_query(req)

    @router.post(
        "/table/query_stream",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                        }
                    }
                },
            }
        },
    )
    def table_query_stream(
        req: tsi.TableQueryReq,
        service: TraceService = Depends(get_service),  # noqa: B008
        accept: Annotated[str, Header()] = "application/jsonl",
    ) -> StreamingResponse:
        return StreamingResponse(
            service.trace_server_interface.table_query_stream(req), media_type=accept
        )

    @router.post("/table/query_stats", tags=[TABLES_TAG_NAME])
    def table_query_stats(
        req: tsi.TableQueryStatsReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.TableQueryStatsRes:
        return service.trace_server_interface.table_query_stats(req)

    @router.post("/refs/read_batch", tags=[REFS_TAG_NAME])
    def refs_read_batch(
        req: tsi.RefsReadBatchReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.RefsReadBatchRes:
        return service.trace_server_interface.refs_read_batch(req)

    @router.post("/file/create", tags=[FILES_TAG_NAME])
    @router.post("/files/create", tags=[FILES_TAG_NAME], include_in_schema=False)
    async def file_create(
        project_id: Annotated[str, Form()],
        file: UploadFile,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.FileCreateRes:
        req = tsi.FileCreateReq(
            project_id=project_id,
            name=file.filename or "<unnamed_file>",
            content=await file.read(),
        )
        return service.trace_server_interface.file_create(req)

    @router.post(
        "/file/content",
        tags=[FILES_TAG_NAME],
        response_class=StreamingResponse,
        responses={
            200: {
                "content": {"application/octet-stream": {}},
                "description": "Binary file content stream",
            }
        },
    )
    @router.post("/files/content", tags=[FILES_TAG_NAME], include_in_schema=False)
    def file_content(
        req: tsi.FileContentReadReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        res = service.trace_server_interface.file_content_read(req)
        return StreamingResponse(
            iter([res.content]), media_type="application/octet-stream"
        )

    @router.post("/cost/create", tags=[COST_TAG_NAME])
    def cost_create(
        req: tsi.CostCreateReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CostCreateRes:
        return service.trace_server_interface.cost_create(req)

    @router.post("/cost/query", tags=[COST_TAG_NAME])
    def cost_query(
        req: tsi.CostQueryReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CostQueryRes:
        return service.trace_server_interface.cost_query(req)

    @router.post("/cost/purge", tags=[COST_TAG_NAME])
    def cost_purge(
        req: tsi.CostPurgeReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CostPurgeRes:
        return service.trace_server_interface.cost_purge(req)

    @router.post("/feedback/create", tags=[FEEDBACK_TAG_NAME])
    def feedback_create(
        req: tsi.FeedbackCreateReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.FeedbackCreateRes:
        """Add feedback to a call or object."""
        return service.trace_server_interface.feedback_create(req)

    @router.post("/feedback/query", tags=[FEEDBACK_TAG_NAME])
    def feedback_query(
        req: tsi.FeedbackQueryReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.FeedbackQueryRes:
        """Query for feedback."""
        return service.trace_server_interface.feedback_query(req)

    @router.post("/feedback/purge", tags=[FEEDBACK_TAG_NAME])
    def feedback_purge(
        req: tsi.FeedbackPurgeReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.FeedbackPurgeRes:
        """Permanently delete feedback."""
        return service.trace_server_interface.feedback_purge(req)

    @router.post("/feedback/replace", tags=[FEEDBACK_TAG_NAME])
    def feedback_replace(
        req: tsi.FeedbackReplaceReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.FeedbackReplaceRes:
        return service.trace_server_interface.feedback_replace(req)

    @router.post(
        "/actions/execute_batch", tags=[ACTIONS_TAG_NAME], include_in_schema=False
    )
    def actions_execute_batch(
        req: tsi.ActionsExecuteBatchReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ActionsExecuteBatchRes:
        return service.trace_server_interface.actions_execute_batch(req)

    @router.post("/completions/create", tags=[COMPLETIONS_TAG_NAME])
    def completions_create(
        req: tsi.CompletionsCreateReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.CompletionsCreateRes:
        return service.trace_server_interface.completions_create(req)

    @router.post(
        "/completions/create_stream",
        tags=[COMPLETIONS_TAG_NAME],
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                        }
                    }
                },
            }
        },
    )
    def completions_create_stream(
        req: tsi.CompletionsCreateReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        return StreamingResponse(
            service.trace_server_interface.completions_create_stream(req),
            media_type="application/jsonl",
        )

    # TODO: This is mislabeled in the core impl.  Keeping it the same here for now.
    @router.post("/project/stats", tags=["project"], include_in_schema=False)
    def project_stats(
        req: tsi.ProjectStatsReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ProjectStatsRes:
        return service.trace_server_interface.project_stats(req)

    @router.post(
        "/threads/stream_query",
        tags=[THREADS_TAG_NAME],
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                        }
                    }
                },
            }
        },
    )
    def threads_query_stream(
        req: tsi.ThreadsQueryReq,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        return StreamingResponse(
            service.trace_server_interface.threads_query_stream(req),
            media_type="application/jsonl",
        )

    return router
