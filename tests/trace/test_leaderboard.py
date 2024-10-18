import pytest

import weave
from weave.flow import leaderboard
from weave.trace.weave_client import get_ref


def test_leaderboard_empty(client):
    spec = leaderboard.Leaderboard(
        name="Test Leaderboard",
        description="This is a test leaderboard",
        columns=[
            leaderboard.LeaderboardColumn(
                evaluation_object_ref="test_evaluation_object_ref",
                scorer_name="test_scorer_name",
                summary_metric_path="test_summary_metric_path",
            )
        ],
    )

    results = leaderboard.get_leaderboard_results(spec, client)
    assert len(results) == 0


async def do_evaluations():
    @weave.op
    def my_scorer(target, model_output):
        return target == model_output

    evaluation_obj_1 = weave.Evaluation(
        name="test_evaluation_name",
        dataset=[{"input": 1, "target": 1}],
        scorers=[my_scorer],
    )

    @weave.op
    def simple_model(input):
        return input

    await evaluation_obj_1.evaluate(simple_model)

    evaluation_obj_2 = weave.Evaluation(
        name="test_evaluation_name",
        dataset=[{"input": 1, "target": 1}, {"input": 2, "target": 2}],
        scorers=[my_scorer],
    )

    @weave.op
    def static_model(input):
        return 1

    @weave.op
    def bad_model(input):
        return input + 1

    await evaluation_obj_2.evaluate(simple_model)
    await evaluation_obj_2.evaluate(static_model)
    await evaluation_obj_2.evaluate(bad_model)

    return evaluation_obj_1, evaluation_obj_2, simple_model, static_model, bad_model


@pytest.mark.asyncio
async def test_leaderboard_with_results(client):
    (
        evaluation_obj_1,
        evaluation_obj_2,
        simple_model,
        static_model,
        bad_model,
    ) = await do_evaluations()

    spec = leaderboard.Leaderboard(
        name="Simple Leaderboard",
        description="This is a test leaderboard",
        columns=[
            leaderboard.LeaderboardColumn(
                evaluation_object_ref=get_ref(evaluation_obj_1).uri(),
                scorer_name="my_scorer",
                summary_metric_path_parts=["true_fraction"],
            )
        ],
    )

    ref = weave.publish(spec)

    # TODO: this is not working
    # spec = ref.get()

    results = leaderboard.get_leaderboard_results(spec, client)
    assert len(results) == 1
    assert results[0].model_ref == get_ref(simple_model).uri()
    assert results[0].column_scores[0].scores[0].value == 1.0

    spec = leaderboard.Leaderboard(
        name="Complex Leaderboard",
        description="This is a test leaderboard",
        columns=[
            leaderboard.LeaderboardColumn(
                evaluation_object_ref=get_ref(evaluation_obj_2).uri(),
                scorer_name="my_scorer",
                summary_metric_path_parts=["true_count"],
            ),
            leaderboard.LeaderboardColumn(
                evaluation_object_ref=get_ref(evaluation_obj_2).uri(),
                scorer_name="my_scorer",
                should_minimize=True,
                summary_metric_path_parts=["true_fraction"],
            ),
            leaderboard.LeaderboardColumn(
                evaluation_object_ref=get_ref(evaluation_obj_1).uri(),
                scorer_name="my_scorer",
                summary_metric_path_parts=["true_fraction"],
            ),
        ],
    )

    ref = weave.publish(spec)

    # TODO: this is not working
    # spec = ref.get()

    results = leaderboard.get_leaderboard_results(spec, client)
    assert len(results) == 3
    assert results[0].model_ref == get_ref(simple_model).uri()
    assert len(results[0].column_scores) == 3
    assert results[0].column_scores[0].scores[0].value == 2.0
    assert results[0].column_scores[1].scores[0].value == 1.0
    assert results[0].column_scores[1].scores[0].value == 1.0
    assert results[1].model_ref == get_ref(static_model).uri()
    assert len(results[1].column_scores) == 3
    assert results[1].column_scores[0].scores[0].value == 1.0
    assert results[1].column_scores[1].scores[0].value == 0.5
    assert len(results[1].column_scores[2].scores) == 0
    assert results[2].model_ref == get_ref(bad_model).uri()
    assert len(results[1].column_scores) == 3
    assert results[2].column_scores[0].scores[0].value == 0
    assert results[2].column_scores[1].scores[0].value == 0
    assert len(results[2].column_scores[2].scores) == 0
