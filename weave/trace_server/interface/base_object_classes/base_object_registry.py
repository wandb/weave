from weave.trace_server.interface.base_object_classes.actions import ActionSpec
from weave.trace_server.interface.base_object_classes.annotation_spec import (
    AnnotationSpec,
)
from weave.trace_server.interface.base_object_classes.base_object_def import BaseObject
from weave.trace_server.interface.base_object_classes.leaderboard import Leaderboard
from weave.trace_server.interface.base_object_classes.test_only_example import (
    TestOnlyExample,
    TestOnlyNestedBaseObject,
)

BASE_OBJECT_REGISTRY: dict[str, type[BaseObject]] = {}


def register_base_object(cls: type[BaseObject]) -> None:
    """
    Register a BaseObject class in the global registry.

    Args:
        cls: The BaseObject class to register
    """
    BASE_OBJECT_REGISTRY[cls.__name__] = cls


register_base_object(TestOnlyExample)
register_base_object(TestOnlyNestedBaseObject)
register_base_object(Leaderboard)
register_base_object(ActionSpec)
register_base_object(AnnotationSpec)
