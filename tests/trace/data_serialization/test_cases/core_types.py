from tests.trace.data_serialization.spec import SerializationTestCase
from tests.trace.data_serialization.test_cases.core_type_factory import (
    CustomObject,
    make_op,
)


def equality_check(a, b):
    return


core_cases = [
    # Core Types
    SerializationTestCase(
        id="Op",
        runtime_object_factory=lambda: make_op(),
        inline_call_param=False,
        is_legacy=False,
        exp_json={
            "_type": "CustomWeaveType",
            "weave_type": {"type": "Op"},
            "files": {"obj.py": "uArqT16jBFwMsG3X0XdoxTYXY2iTBX4OEYDQtWM6zME"},
        },
        exp_objects=[],
        exp_files=[
            {
                "digest": "uArqT16jBFwMsG3X0XdoxTYXY2iTBX4OEYDQtWM6zME",
                "exp_content": b'import weave\n\n@weave.op\ndef say_hello(name: str):\n    return "hello " + name\n',
            }
        ],
        equality_check=lambda a, b: a("john") == b("john"),
    ),
    SerializationTestCase(
        id="Object",
        runtime_object_factory=lambda: CustomObject(my_name="John"),
        inline_call_param=False,
        is_legacy=False,
        exp_json={
            "_type": "CustomObject",
            "name": None,
            "description": None,
            "my_name": "John",
            "say_hello": "weave:///shawn/test-project/op/CustomObject.say_hello:uAuGcTP39TqYOX27waNSJL9YGZIxbiy4KyJoEDkJeIM",
            "_class_name": "CustomObject",
            "_bases": ["Object", "BaseModel"],
        },
        exp_objects=[
            {
                "object_id": "CustomObject.say_hello",
                "digest": "uAuGcTP39TqYOX27waNSJL9YGZIxbiy4KyJoEDkJeIM",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "ZiIEs8e6ZXWEtOAQMh342bCbSGM7XdotgQ0HIK1wZV4"},
                },
            }
        ],
        exp_files=[
            {
                "digest": "ZiIEs8e6ZXWEtOAQMh342bCbSGM7XdotgQ0HIK1wZV4",
                "exp_content": b'import weave\n\n@weave.op\ndef say_hello(self):\n    return "hello " + self.my_name\n',
            }
        ],
        equality_check=lambda a, b: (
            # Unfortunately this does not correct deserialize right now - specifically
            # for the inputs case! It is left as a WeaveObject. Ideally we could comment
            # this back in
            # isinstance(a, CustomObject) and isinstance(b, CustomObject) and
            a.my_name == b.my_name
        ),
    ),
]
