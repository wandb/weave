"""SDK-level rescore_evaluation — runs locally, no Kafka/worker required.

The SDK path is distinct from the server path (POST /evaluations/rescore):
- SDK path: calls evaluation_run_create directly, then awaits rescore_predictions
- Server path: POST /evaluations/rescore → rescore() creates the run internally then dispatches to Kafka

These are separate code paths — there is no double-creation.
"""

from weave.trace.context.weave_client_context import require_weave_client
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.workers.evaluate_model_worker.rescore_worker import (
    rescore_predictions,
)


async def rescore_evaluation(
    source_evaluation_run_id: str,
    scorer_refs: list[str],
    *,
    project_id: str | None = None,
) -> str:
    """Rescore an existing evaluation run with different scorer(s), running locally.

    Applies scorer(s) to the predictions from source_evaluation_run_id and creates a new
    EvaluationRun containing the new scores. Returns the new evaluation_run_id.

    Original prediction call IDs are preserved — no new predictions are created.
    Runs in-process — no eval worker or Kafka required.

    Args:
        source_evaluation_run_id: ID of the evaluation run whose predictions to rescore
        scorer_refs: List of scorer weave:// URIs to apply
        project_id: Project ID (entity/project). Defaults to the current client project.

    Returns:
        The new evaluation_run_id

    Example:
        new_run_id = await weave.evaluation.rescore_evaluation(
            source_evaluation_run_id="abc123",
            scorer_refs=["weave:///entity/project/object/MyScorer:latest"],
        )
    """
    client = require_weave_client()
    if project_id is None:
        project_id = client.project_id  # plain attribute, not a method call

    source_run = client.server.evaluation_run_read(
        tsi.EvaluationRunReadReq(
            project_id=project_id,
            evaluation_run_id=source_evaluation_run_id,
        )
    )
    new_run_res = client.server.evaluation_run_create(
        tsi.EvaluationRunCreateReq(
            project_id=project_id,
            evaluation=source_run.evaluation,
            model=source_run.model,
            source_evaluation_run_id=source_evaluation_run_id,
        )
    )

    # await directly — rescore_predictions is async def, no asyncio.run() needed here.
    # wb_user_id is None: the SDK path has no server-side user context.
    # score_create and evaluation_run_finish handle None wb_user_id gracefully.
    await rescore_predictions(
        tsi.RescoringArgs(
            project_id=project_id,
            source_evaluation_run_id=source_evaluation_run_id,
            scorer_refs=scorer_refs,
            wb_user_id=None,  # None, not "" — layers check `if req.wb_user_id is None`
            new_evaluation_run_id=new_run_res.evaluation_run_id,
        )
    )
    return new_run_res.evaluation_run_id
