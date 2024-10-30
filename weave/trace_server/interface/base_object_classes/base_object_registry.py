from typing import Dict, Type

from weave.trace_server.interface.base_object_classes.base_object_def import BaseObject
from weave.trace_server.interface.base_object_classes.test_only_example import *

REGISTRY: Dict[str, Type[BaseObject]] = {
    "TestOnlyExample": TestOnlyExample,
    "TestOnlyNestedBaseObject": TestOnlyNestedBaseObject,
}
