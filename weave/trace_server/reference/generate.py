from __future__ import annotations

from typing import Annotated, Callable, NamedTuple

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.params import Header
from fastapi.responses import StreamingResponse

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.trace_service import ServerInfoRes, TraceService

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
V2_OPS_TAG_NAME = "V2 -- Ops"
V2_DATASETS_TAG_NAME = "V2 -- Datasets"
V2_SCORERS_TAG_NAME = "V2 -- Scorers"
V2_EVALUATIONS_TAG_NAME = "V2 -- Evaluations"
V2_MODELS_TAG_NAME = "V2 -- Models"
V2_EVALUATION_RUNS_TAG_NAME = "V2 -- Evaluation Runs"
V2_PREDICTIONS_TAG_NAME = "V2 -- Predictions"
V2_SCORES_TAG_NAME = "V2 -- Scores"


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


def generate_routes_v2(
    router: APIRouter, service_dependency: ServiceDependency
) -> APIRouter:
    """Generate v2 ops routes for the FastAPI app.

    Args:
        router: The router to add routes to
        service_dependency: The factory function to create a ServiceDependency.

    Returns:
        The router with v2 ops routes implemented
    """
    get_service = service_dependency.get_service()

    @router.post(
        "/{entity}/{project}/ops",
        tags=[V2_OPS_TAG_NAME],
        operation_id="op_create_v2",
    )
    def op_create_v2(
        entity: str,
        project: str,
        body: tsi.OpCreateV2Body,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.OpCreateV2Res:
        """Create an op object."""
        project_id = f"{entity}/{project}"
        req = tsi.OpCreateV2Req(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.op_create_v2(req)

    @router.get(
        "/{entity}/{project}/ops/{object_id}/versions/{digest}",
        tags=[V2_OPS_TAG_NAME],
        operation_id="op_read_v2",
    )
    def op_read_v2(
        entity: str,
        project: str,
        object_id: str,
        digest: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.OpReadV2Res:
        """Get an op object."""
        project_id = f"{entity}/{project}"
        req = tsi.OpReadV2Req(project_id=project_id, object_id=object_id, digest=digest)
        return service.trace_server_interface.op_read_v2(req)

    @router.get(
        "/{entity}/{project}/ops",
        tags=[V2_OPS_TAG_NAME],
        operation_id="op_list_v2",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/OpReadV2Res"},
                        }
                    }
                },
            }
        },
    )
    def op_list_v2(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List op objects."""
        project_id = f"{entity}/{project}"
        req = tsi.OpListV2Req(project_id=project_id, limit=limit, offset=offset)
        return StreamingResponse(
            service.trace_server_interface.op_list_v2(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/ops/{object_id}",
        tags=[V2_OPS_TAG_NAME],
        operation_id="op_delete_v2",
    )
    def op_delete_v2(
        entity: str,
        project: str,
        object_id: str,
        digests: list[str] | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.OpDeleteV2Res:
        """Delete an op object. If digests are provided, only those versions are deleted. Otherwise, all versions are deleted."""
        project_id = f"{entity}/{project}"
        req = tsi.OpDeleteV2Req(
            project_id=project_id, object_id=object_id, digests=digests
        )
        return service.trace_server_interface.op_delete_v2(req)

    @router.post(
        "/{entity}/{project}/datasets",
        tags=[V2_DATASETS_TAG_NAME],
        operation_id="dataset_create_v2",
    )
    def dataset_create_v2(
        entity: str,
        project: str,
        body: tsi.DatasetCreateV2Body,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.DatasetCreateV2Res:
        """Create a dataset object."""
        project_id = f"{entity}/{project}"
        req = tsi.DatasetCreateV2Req(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.dataset_create_v2(req)

    @router.get(
        "/{entity}/{project}/datasets/{object_id}/versions/{digest}",
        tags=[V2_DATASETS_TAG_NAME],
        operation_id="dataset_read_v2",
    )
    def dataset_read_v2(
        entity: str,
        project: str,
        object_id: str,
        digest: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.DatasetReadV2Res:
        """Get a dataset object."""
        project_id = f"{entity}/{project}"
        req = tsi.DatasetReadV2Req(
            project_id=project_id, object_id=object_id, digest=digest
        )
        return service.trace_server_interface.dataset_read_v2(req)

    @router.get(
        "/{entity}/{project}/datasets",
        tags=[V2_DATASETS_TAG_NAME],
        operation_id="dataset_list_v2",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/DatasetReadV2Res"},
                        }
                    }
                },
            }
        },
    )
    def dataset_list_v2(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List dataset objects."""
        project_id = f"{entity}/{project}"
        req = tsi.DatasetListV2Req(project_id=project_id, limit=limit, offset=offset)
        return StreamingResponse(
            service.trace_server_interface.dataset_list_v2(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/datasets/{object_id}",
        tags=[V2_DATASETS_TAG_NAME],
        operation_id="dataset_delete_v2",
    )
    def dataset_delete_v2(
        entity: str,
        project: str,
        object_id: str,
        digests: list[str] | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.DatasetDeleteV2Res:
        """Delete a dataset object."""
        project_id = f"{entity}/{project}"
        req = tsi.DatasetDeleteV2Req(
            project_id=project_id, object_id=object_id, digests=digests
        )
        return service.trace_server_interface.dataset_delete_v2(req)

    @router.post(
        "/{entity}/{project}/scorers",
        tags=[V2_SCORERS_TAG_NAME],
        operation_id="scorer_create_v2",
    )
    def scorer_create_v2(
        entity: str,
        project: str,
        body: tsi.ScorerCreateV2Body,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScorerCreateV2Res:
        """Create a scorer object."""
        project_id = f"{entity}/{project}"
        req = tsi.ScorerCreateV2Req(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.scorer_create_v2(req)

    @router.get(
        "/{entity}/{project}/scorers/{object_id}/versions/{digest}",
        tags=[V2_SCORERS_TAG_NAME],
        operation_id="scorer_read_v2",
    )
    def scorer_read_v2(
        entity: str,
        project: str,
        object_id: str,
        digest: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScorerReadV2Res:
        """Get a scorer object."""
        project_id = f"{entity}/{project}"
        req = tsi.ScorerReadV2Req(
            project_id=project_id, object_id=object_id, digest=digest
        )
        return service.trace_server_interface.scorer_read_v2(req)

    @router.get(
        "/{entity}/{project}/scorers",
        tags=[V2_SCORERS_TAG_NAME],
        operation_id="scorer_list_v2",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ScorerReadV2Res"},
                        }
                    }
                },
            }
        },
    )
    def scorer_list_v2(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List scorer objects."""
        project_id = f"{entity}/{project}"
        req = tsi.ScorerListV2Req(project_id=project_id, limit=limit, offset=offset)
        return StreamingResponse(
            service.trace_server_interface.scorer_list_v2(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/scorers/{object_id}",
        tags=[V2_SCORERS_TAG_NAME],
        operation_id="scorer_delete_v2",
    )
    def scorer_delete_v2(
        entity: str,
        project: str,
        object_id: str,
        digests: list[str] | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScorerDeleteV2Res:
        """Delete a scorer object."""
        project_id = f"{entity}/{project}"
        req = tsi.ScorerDeleteV2Req(
            project_id=project_id, object_id=object_id, digests=digests
        )
        return service.trace_server_interface.scorer_delete_v2(req)

    @router.post(
        "/{entity}/{project}/evaluations",
        tags=[V2_EVALUATIONS_TAG_NAME],
        operation_id="evaluation_create_v2",
    )
    def evaluation_create_v2(
        req: tsi.EvaluationCreateV2Req,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationCreateV2Res:
        """Create an evaluation object."""
        return service.trace_server_interface.evaluation_create_v2(req)

    @router.get(
        "/{entity}/{project}/evaluations/{object_id}/versions/{digest}",
        tags=[V2_EVALUATIONS_TAG_NAME],
        operation_id="evaluation_read_v2",
    )
    def evaluation_read_v2(
        entity: str,
        project: str,
        object_id: str,
        digest: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationReadV2Res:
        """Get an evaluation object."""
        project_id = f"{entity}/{project}"
        req = tsi.EvaluationReadV2Req(
            project_id=project_id, object_id=object_id, digest=digest
        )
        return service.trace_server_interface.evaluation_read_v2(req)

    @router.get(
        "/{entity}/{project}/evaluations",
        tags=[V2_EVALUATIONS_TAG_NAME],
        operation_id="evaluation_list_v2",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/EvaluationReadV2Res"
                            },
                        }
                    }
                },
            }
        },
    )
    def evaluation_list_v2(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List evaluation objects."""
        project_id = f"{entity}/{project}"
        req = tsi.EvaluationListV2Req(project_id=project_id, limit=limit, offset=offset)
        return StreamingResponse(
            service.trace_server_interface.evaluation_list_v2(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/evaluations/{object_id}",
        tags=[V2_EVALUATIONS_TAG_NAME],
        operation_id="evaluation_delete_v2",
    )
    def evaluation_delete_v2(
        entity: str,
        project: str,
        object_id: str,
        digests: list[str] | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationDeleteV2Res:
        """Delete an evaluation object."""
        project_id = f"{entity}/{project}"
        req = tsi.EvaluationDeleteV2Req(
            project_id=project_id, object_id=object_id, digests=digests
        )
        return service.trace_server_interface.evaluation_delete_v2(req)

    @router.post(
        "/{entity}/{project}/evaluation_runs",
        tags=[V2_EVALUATION_RUNS_TAG_NAME],
        operation_id="evaluation_run_create_v2",
    )
    def evaluation_run_create_v2(
        entity: str,
        project: str,
        body: tsi.EvaluationRunCreateV2Body,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationRunCreateV2Res:
        """Create an evaluation run."""
        project_id = f"{entity}/{project}"
        req = tsi.EvaluationRunCreateV2Req(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.evaluation_run_create_v2(req)

    @router.get(
        "/{entity}/{project}/evaluation_runs/{evaluation_run_id}",
        tags=[V2_EVALUATION_RUNS_TAG_NAME],
        operation_id="evaluation_run_read_v2",
    )
    def evaluation_run_read_v2(
        entity: str,
        project: str,
        evaluation_run_id: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationRunReadV2Res:
        """Get an evaluation run."""
        project_id = f"{entity}/{project}"
        req = tsi.EvaluationRunReadV2Req(
            project_id=project_id, evaluation_run_id=evaluation_run_id
        )
        return service.trace_server_interface.evaluation_run_read_v2(req)

    @router.get(
        "/{entity}/{project}/evaluation_runs",
        tags=[V2_EVALUATION_RUNS_TAG_NAME],
        operation_id="evaluation_run_list_v2",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/EvaluationRunReadV2Res"
                            },
                        }
                    }
                },
            }
        },
    )
    def evaluation_run_list_v2(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List evaluation runs."""
        project_id = f"{entity}/{project}"
        req = tsi.EvaluationRunListV2Req(
            project_id=project_id, limit=limit, offset=offset
        )
        return StreamingResponse(
            service.trace_server_interface.evaluation_run_list_v2(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/evaluation_runs",
        tags=[V2_EVALUATION_RUNS_TAG_NAME],
        operation_id="evaluation_run_delete_v2",
    )
    def evaluation_run_delete_v2(
        entity: str,
        project: str,
        evaluation_run_ids: list[str],
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationRunDeleteV2Res:
        """Delete evaluation runs."""
        project_id = f"{entity}/{project}"
        req = tsi.EvaluationRunDeleteV2Req(
            project_id=project_id, evaluation_run_ids=evaluation_run_ids
        )
        return service.trace_server_interface.evaluation_run_delete_v2(req)

    @router.post(
        "/{entity}/{project}/evaluation_runs/{evaluation_run_id}/finish",
        tags=[V2_EVALUATION_RUNS_TAG_NAME],
        operation_id="evaluation_run_finish_v2",
    )
    def evaluation_run_finish_v2(
        entity: str,
        project: str,
        evaluation_run_id: str,
        body: tsi.EvaluationRunFinishV2Body,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.EvaluationRunFinishV2Res:
        """Finish an evaluation run."""
        project_id = f"{entity}/{project}"
        req = tsi.EvaluationRunFinishV2Req(
            project_id=project_id,
            evaluation_run_id=evaluation_run_id,
            **body.model_dump(),
        )
        return service.trace_server_interface.evaluation_run_finish_v2(req)

    @router.post(
        "/{entity}/{project}/models",
        tags=[V2_MODELS_TAG_NAME],
        operation_id="model_create_v2",
    )
    def model_create_v2(
        entity: str,
        project: str,
        body: tsi.ModelCreateV2Body,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ModelCreateV2Res:
        """Create a model object."""
        project_id = f"{entity}/{project}"
        req = tsi.ModelCreateV2Req(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.model_create_v2(req)

    @router.get(
        "/{entity}/{project}/models/{object_id}/versions/{digest}",
        tags=[V2_MODELS_TAG_NAME],
        operation_id="model_read_v2",
    )
    def model_read_v2(
        entity: str,
        project: str,
        object_id: str,
        digest: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ModelReadV2Res:
        """Get a model object."""
        project_id = f"{entity}/{project}"
        req = tsi.ModelReadV2Req(
            project_id=project_id, object_id=object_id, digest=digest
        )
        return service.trace_server_interface.model_read_v2(req)

    @router.get(
        "/{entity}/{project}/models",
        tags=[V2_MODELS_TAG_NAME],
        operation_id="model_list_v2",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ModelReadV2Res"},
                        }
                    }
                },
            }
        },
    )
    def model_list_v2(
        entity: str,
        project: str,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List model objects."""
        project_id = f"{entity}/{project}"
        req = tsi.ModelListV2Req(project_id=project_id, limit=limit, offset=offset)
        return StreamingResponse(
            service.trace_server_interface.model_list_v2(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/models/{object_id}",
        tags=[V2_MODELS_TAG_NAME],
        operation_id="model_delete_v2",
    )
    def model_delete_v2(
        entity: str,
        project: str,
        object_id: str,
        digests: list[str] | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ModelDeleteV2Res:
        """Delete a model object. If digests are provided, only those versions are deleted. Otherwise, all versions are deleted."""
        project_id = f"{entity}/{project}"
        req = tsi.ModelDeleteV2Req(
            project_id=project_id, object_id=object_id, digests=digests
        )
        return service.trace_server_interface.model_delete_v2(req)

    # Prediction Routes

    @router.post(
        "/{entity}/{project}/predictions",
        tags=[V2_PREDICTIONS_TAG_NAME],
        operation_id="prediction_create_v2",
    )
    def prediction_create_v2(
        entity: str,
        project: str,
        body: tsi.PredictionCreateV2Body,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.PredictionCreateV2Res:
        """Create a prediction."""
        project_id = f"{entity}/{project}"
        req = tsi.PredictionCreateV2Req(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.prediction_create_v2(req)

    @router.get(
        "/{entity}/{project}/predictions/{prediction_id}",
        tags=[V2_PREDICTIONS_TAG_NAME],
        operation_id="prediction_read_v2",
    )
    def prediction_read_v2(
        entity: str,
        project: str,
        prediction_id: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.PredictionReadV2Res:
        """Get a prediction."""
        project_id = f"{entity}/{project}"
        req = tsi.PredictionReadV2Req(
            project_id=project_id, prediction_id=prediction_id
        )
        return service.trace_server_interface.prediction_read_v2(req)

    @router.get(
        "/{entity}/{project}/predictions",
        tags=[V2_PREDICTIONS_TAG_NAME],
        operation_id="prediction_list_v2",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {
                                "$ref": "#/components/schemas/PredictionReadV2Res"
                            },
                        }
                    }
                },
            }
        },
    )
    def prediction_list_v2(
        entity: str,
        project: str,
        evaluation_run_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List predictions."""
        project_id = f"{entity}/{project}"
        req = tsi.PredictionListV2Req(
            project_id=project_id,
            evaluation_run_id=evaluation_run_id,
            limit=limit,
            offset=offset,
        )
        return StreamingResponse(
            service.trace_server_interface.prediction_list_v2(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/predictions",
        tags=[V2_PREDICTIONS_TAG_NAME],
        operation_id="prediction_delete_v2",
    )
    def prediction_delete_v2(
        entity: str,
        project: str,
        prediction_ids: list[str],
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.PredictionDeleteV2Res:
        """Delete predictions."""
        project_id = f"{entity}/{project}"
        req = tsi.PredictionDeleteV2Req(
            project_id=project_id, prediction_ids=prediction_ids
        )
        return service.trace_server_interface.prediction_delete_v2(req)

    @router.post(
        "/{entity}/{project}/predictions/{prediction_id}/finish",
        tags=[V2_PREDICTIONS_TAG_NAME],
        operation_id="prediction_finish_v2",
    )
    def prediction_finish_v2(
        entity: str,
        project: str,
        prediction_id: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.PredictionFinishV2Res:
        """Finish a prediction."""
        print(
            f"DEBUG REST: prediction_finish_v2 called with prediction_id={prediction_id}"
        )
        project_id = f"{entity}/{project}"
        req = tsi.PredictionFinishV2Req(
            project_id=project_id, prediction_id=prediction_id
        )
        print("DEBUG REST: calling trace_server_interface.prediction_finish_v2")
        result = service.trace_server_interface.prediction_finish_v2(req)
        print(f"DEBUG REST: prediction_finish_v2 completed, success={result.success}")
        return result

    # Score Routes

    @router.post(
        "/{entity}/{project}/scores",
        tags=[V2_SCORES_TAG_NAME],
        operation_id="score_create_v2",
    )
    def score_create_v2(
        entity: str,
        project: str,
        body: tsi.ScoreCreateV2Body,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScoreCreateV2Res:
        """Create a score."""
        project_id = f"{entity}/{project}"
        req = tsi.ScoreCreateV2Req(project_id=project_id, **body.model_dump())
        return service.trace_server_interface.score_create_v2(req)

    @router.get(
        "/{entity}/{project}/scores/{score_id}",
        tags=[V2_SCORES_TAG_NAME],
        operation_id="score_read_v2",
    )
    def score_read_v2(
        entity: str,
        project: str,
        score_id: str,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScoreReadV2Res:
        """Get a score."""
        project_id = f"{entity}/{project}"
        req = tsi.ScoreReadV2Req(project_id=project_id, score_id=score_id)
        return service.trace_server_interface.score_read_v2(req)

    @router.get(
        "/{entity}/{project}/scores",
        tags=[V2_SCORES_TAG_NAME],
        operation_id="score_list_v2",
        response_class=StreamingResponse,
        responses={
            200: {
                "description": "Stream of data in JSONL format",
                "content": {
                    "application/jsonl": {
                        "schema": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ScoreReadV2Res"},
                        }
                    }
                },
            }
        },
    )
    def score_list_v2(
        entity: str,
        project: str,
        evaluation_run_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> StreamingResponse:
        """List scores."""
        project_id = f"{entity}/{project}"
        req = tsi.ScoreListV2Req(
            project_id=project_id,
            evaluation_run_id=evaluation_run_id,
            limit=limit,
            offset=offset,
        )
        return StreamingResponse(
            service.trace_server_interface.score_list_v2(req),
            media_type="application/jsonl",
        )

    @router.delete(
        "/{entity}/{project}/scores",
        tags=[V2_SCORES_TAG_NAME],
        operation_id="score_delete_v2",
    )
    def score_delete_v2(
        entity: str,
        project: str,
        score_ids: list[str],
        service: TraceService = Depends(get_service),  # noqa: B008
    ) -> tsi.ScoreDeleteV2Res:
        """Delete scores."""
        project_id = f"{entity}/{project}"
        req = tsi.ScoreDeleteV2Req(project_id=project_id, score_ids=score_ids)
        return service.trace_server_interface.score_delete_v2(req)

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

    # @router.post("/op/create", tags=[OPS_TAG_NAME])
    # def op_create(
    #     req: tsi.OpCreateReq,
    #     server: tsi.TraceServerInterface = Depends(get_server),
    # ) -> tsi.OpCreateRes:
    #     return server.op_create(req)

    # @router.post("/op/read", tags=[OPS_TAG_NAME])
    # def op_read(
    #     req: tsi.OpReadReq,
    #     server: tsi.TraceServerInterface = Depends(get_server),
    # ) -> tsi.OpReadRes:
    #     return server.op_read(req)

    # @router.post("/ops/query", tags=[OPS_TAG_NAME])
    # def ops_query(
    #     req: tsi.OpQueryReq,
    #     server: tsi.TraceServerInterface = Depends(get_server),
    # ) -> tsi.OpQueryRes:
    #     return server.ops_query(req)

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
