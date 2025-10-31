from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict


def default_equality_check(a, b):
    return a == b


class ExpFileSpec(TypedDict):
    digest: str
    exp_content: str


class ExpObjectSpec(TypedDict):
    object_id: str
    digest: str
    exp_val: dict


@dataclass
class SerializationTestCase:
    # A unique identifier for the test case
    id: str

    # Returns a python object to be serialized
    runtime_object_factory: Callable[[], Any]

    # If true, then then used in a paramter/return value of a call,
    # will be directly stored in the call's inputs/outputs (as opposed
    # to being published and stored as a Ref)
    inline_call_param: bool

    # The expected json representation of the object
    exp_json: dict

    # The published objects that are expected to have been created
    # and used to support the serialization
    exp_objects: list[ExpObjectSpec]

    # The associated files that are expected to have been created
    # and used to support the serialization
    exp_files: list[ExpFileSpec]

    # If true, then the current library code is not expected to PRODUCE
    # this JSON, but should still be able to deserialize it. When True,
    # we will bootstrap the expected objects and files and assert that
    # deserialization still works.
    is_legacy: bool

    # A function that checks if two objects are equal. If None, then
    # the objects are expected to be equal using `==`
    equality_check: Callable[[Any, Any], bool] | None = default_equality_check

    # The python version that was used to write the ops (different versions
    # result in different code captures!)
    python_version_code_capture: tuple[int, int] | None = None
