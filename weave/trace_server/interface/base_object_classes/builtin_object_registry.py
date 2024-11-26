import pydantic

from weave.scorers.test_scorer import TestScorer
from weave.trace_server.interface.base_object_classes.actions import ActionSpec
from weave.trace_server.interface.base_object_classes.annotation_spec import (
    AnnotationSpec,
)
from weave.trace_server.interface.base_object_classes.leaderboard import Leaderboard
from weave.trace_server.interface.base_object_classes.test_only_example import (
    TestOnlyExample,
    TestOnlyNestedBaseObject,
)

BUILTIN_OBJECT_CLASS_REGISTRY: dict[str, type[pydantic.BaseModel]] = {}


def register_builtin_object(cls: type[pydantic.BaseModel]) -> None:
    """
    Register a Builtin pydantic.BaseModel class in the global registry.

    Args:
        cls: The pydantic.BaseModel class to register
    """
    BUILTIN_OBJECT_CLASS_REGISTRY[cls.__name__] = cls


register_builtin_object(TestOnlyExample)
register_builtin_object(TestOnlyNestedBaseObject)
register_builtin_object(Leaderboard)
register_builtin_object(ActionSpec)
register_builtin_object(AnnotationSpec)
register_builtin_object(TestScorer)
