from tests.trace.data_serialization.spec import SerializationTestCase

primitive_cases = [
    # Primitives
    SerializationTestCase(
        id="primitives",
        runtime_object_factory=lambda: {
            "int": 1,
            "float": 1.0,
            "str": "hello",
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
        },
        inline_call_param=True,
        is_legacy=False,
        exp_json={
            "int": 1,
            "float": 1.0,
            "str": "hello",
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
        },
        exp_objects=[],
        exp_files=[],
    ),
]
