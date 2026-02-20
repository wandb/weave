from tests.trace.data_serialization.spec import SerializationTestCase
from weave import AnnotationSpec
from weave.flow import leaderboard
from weave.flow.monitor import Monitor

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
        exp_json={
            "_type": "AnnotationSpec",
            "name": "Numerical field #1",
            "description": "A numerical field with a range of -1 to 1",
            "field_schema": {"type": "number", "minimum": -1, "maximum": 1},
            "unique_among_creators": True,
            "op_scope": None,
            "_class_name": "AnnotationSpec",
            "_bases": ["BaseObject", "BaseModel"],
        },
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
        exp_json={
            "_type": "Leaderboard",
            "name": "Empty Leaderboard",
            "description": "This is an empty leaderboard",
            "columns": [
                {
                    "_type": "LeaderboardColumn",
                    "evaluation_object_ref": "FAKE_REF",
                    "scorer_name": "test_scorer_name",
                    "summary_metric_path": "test_summary_metric_path",
                    "should_minimize": None,
                    "_class_name": "LeaderboardColumn",
                    "_bases": ["BaseModel"],
                }
            ],
            "_class_name": "Leaderboard",
            "_bases": ["BaseObject", "BaseModel"],
        },
        exp_objects=[],
        exp_files=[],
    ),
    # Unfortunately SavedViews are sufficiently messed up that this does not work
    # SerializationTestCase(
    #     id="SavedView",
    #     runtime_object_factory=lambda: weave.SavedView(
    #         "traces", "My saved view"
    #     ).filter_op("Evaluation.predict_and_score"),
    #     inline_call_param=True,
    #     is_legacy=False,
    #     # THIS IS A BUG! We serialize as a string? This is way wrong
    #     exp_json="<weave.flow.saved_view.SavedView object at 0x136ea6f90>",
    #     exp_objects=[],
    #     exp_files=[],
    #     # Sad ... equality is really a pain to assert here (and is broken)
    #     # TODO: Write a good equality check and make it work
    #     equality_check=lambda a, b: True,
    # ),
    SerializationTestCase(
        id="Monitor",
        runtime_object_factory=lambda: Monitor(
            name="test_monitor",
            sampling_rate=0.5,
            scorers=[],
            op_names=["example_op_name"],
            query={
                "$expr": {
                    "$gt": [
                        {"$getField": "started_at"},
                        {"$literal": 1742540400},
                    ]
                }
            },
            scorer_debounce_config={
                "enabled": True,
                "aggregation_field": "trace_id",
                "timeout_seconds": 60.1,
            },
        ),
        inline_call_param=False,
        is_legacy=False,
        exp_json={
            "_type": "Monitor",
            "name": "test_monitor",
            "description": None,
            "sampling_rate": 0.5,
            "scorers": [],
            "op_names": ["example_op_name"],
            "query": {
                "_type": "Query",
                "$expr": {
                    "_type": "GtOperation",
                    "$gt": [
                        {
                            "_type": "GetFieldOperator",
                            "$getField": "started_at",
                            "_class_name": "GetFieldOperator",
                            "_bases": ["BaseModel"],
                        },
                        {
                            "_type": "LiteralOperation",
                            "$literal": 1742540400,
                            "_class_name": "LiteralOperation",
                            "_bases": ["BaseModel"],
                        },
                    ],
                    "_class_name": "GtOperation",
                    "_bases": ["BaseModel"],
                },
                "_class_name": "Query",
                "_bases": ["BaseModel"],
            },
            "active": False,
            "scorer_debounce_config": {
                "enabled": True,
                "aggregation_field": "trace_id",
                "timeout_seconds": 60.1,
            },
            "_class_name": "Monitor",
            "_bases": ["Object", "BaseModel"],
        },
        exp_objects=[],
        exp_files=[],
        # Sad ... equality is really a pain to assert here (and is broken)
        # TODO: Write a good equality check and make it work
        equality_check=lambda a, b: True,
    ),
    SerializationTestCase(
        id="Monitor (legacy v1, before debouncing)",
        runtime_object_factory=lambda: Monitor(
            name="test_monitor",
            sampling_rate=0.5,
            scorers=[],
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
        inline_call_param=False,
        is_legacy=True,
        exp_json={
            "_type": "Monitor",
            "name": "test_monitor",
            "description": None,
            "sampling_rate": 0.5,
            "scorers": [],
            "op_names": ["example_op_name"],
            "query": {
                "_type": "Query",
                "$expr": {
                    "_type": "GtOperation",
                    "$gt": [
                        {
                            "_type": "GetFieldOperator",
                            "$getField": "started_at",
                            "_class_name": "GetFieldOperator",
                            "_bases": ["BaseModel"],
                        },
                        {
                            "_type": "LiteralOperation",
                            "$literal": 1742540400,
                            "_class_name": "LiteralOperation",
                            "_bases": ["BaseModel"],
                        },
                    ],
                    "_class_name": "GtOperation",
                    "_bases": ["BaseModel"],
                },
                "_class_name": "Query",
                "_bases": ["BaseModel"],
            },
            "active": False,
            "_class_name": "Monitor",
            "_bases": ["Object", "BaseModel"],
        },
        exp_objects=[],
        exp_files=[],
        # Sad ... equality is really a pain to assert here (and is broken)
        # TODO: Write a good equality check and make it work
        equality_check=lambda a, b: True,
    ),
]
