from typing import Dict, Type

from pydantic import BaseModel

from weave.trace_server.interface.base_object_classes.base_object_def import BaseObject
from weave.trace_server.interface.base_object_classes.test_only_example import *

BASE_OBJECT_REGISTRY: Dict[str, Type[BaseObject]] = {}


def register_base_object(cls: Type[BaseObject]) -> None:
    BASE_OBJECT_REGISTRY[cls.__name__] = cls


register_base_object(TestOnlyExample)
register_base_object(TestOnlyNestedBaseObject)


# TODO: Remove this helper
class CompositeBaseObject(BaseModel):
    TestOnlyExample: TestOnlyExample
    TestOnlyNestedBaseObject: TestOnlyNestedBaseObject
