import weave
from tests.trace.data_serialization.spec import SerializationTestCase
from weave import AnnotationSpec
from weave.flow import leaderboard
from weave.flow.monitor import Monitor
from weave.scorers import ValidJSONScorer

config_cases = [
    SerializationTestCase(
        id="AnnotationSpec",
        runtime_object_factory=lambda: AnnotationSpec(
            name="Numerical field #1",
            description="A numerical field with a range of -1 to 1",
            field_schema={
                "type": "number",
                "minimum": -1,
                "maximum": 1,
            },
            unique_among_creators=True,
            op_scope=None,
        ),
        inline_call_param=True,
        is_legacy=False,
        exp_json={},
        exp_objects=[],
        exp_files=[],
    ),
    SerializationTestCase(
        id="Leaderboard",
        runtime_object_factory=lambda: leaderboard.Leaderboard(
            name="Empty Leaderboard",
            description="""This is an empty leaderboard""",
            columns=[
                leaderboard.LeaderboardColumn(
                    evaluation_object_ref="FAKE_REF",
                    scorer_name="test_scorer_name",
                    summary_metric_path="test_summary_metric_path",
                )
            ],
        ),
        inline_call_param=True,
        is_legacy=False,
        exp_json={},
        exp_objects=[],
        exp_files=[],
    ),
    SerializationTestCase(
        id="SavedView",
        runtime_object_factory=lambda: weave.SavedView(
            "traces", "My saved view"
        ).filter_op("Evaluation.predict_and_score"),
        inline_call_param=True,
        is_legacy=False,
        exp_json={},
        exp_objects=[],
        exp_files=[],
    ),
    SerializationTestCase(
        id="Monitor",
        runtime_object_factory=lambda: Monitor(
            name="test_monitor",
            sampling_rate=0.5,
            scorers=[ValidJSONScorer()],
            op_names=["example_op_name"],
            query={
                "$expr": {
                    "$gt": [
                        {"$getField": "started_at"},
                        {"$literal": 1742540400},
                    ]
                }
            },
        ),
        inline_call_param=True,
        is_legacy=False,
        exp_json={},
        exp_objects=[],
        exp_files=[],
    ),
]
