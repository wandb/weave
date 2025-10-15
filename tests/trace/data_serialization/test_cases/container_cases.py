import dataclasses

import pydantic

from tests.trace.data_serialization.spec import SerializationTestCase


class PydanticBaseModel(pydantic.BaseModel):
    my_int: int


@dataclasses.dataclass
class ClassicDataclass:
    my_int: int


container_cases = [
    # Container Types
    SerializationTestCase(
        id="Pydantic BaseModel",
        runtime_object_factory=lambda: PydanticBaseModel(my_int=1),
        inline_call_param=True,
        is_legacy=False,
        exp_json={
            "_type": "PydanticBaseModel",
            "my_int": 1,
            "_class_name": "PydanticBaseModel",
            "_bases": ["BaseModel"],
        },
        exp_objects=[],
        exp_files=[],
    ),
    SerializationTestCase(
        id="Classic Dataclass",
        runtime_object_factory=lambda: ClassicDataclass(my_int=1),
        inline_call_param=True,
        is_legacy=False,
        exp_json={
            "_type": "ClassicDataclass",
            "my_int": 1,
            "_class_name": "ClassicDataclass",
            "_bases": [],
        },
        exp_objects=[],
        exp_files=[],
    ),
]
