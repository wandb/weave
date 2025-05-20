from weave.trace_server.interface.builtin_object_classes.actions import ActionSpec
from weave.trace_server.interface.builtin_object_classes.annotation_spec import (
    AnnotationSpec,
)
from weave.trace_server.interface.builtin_object_classes.base_object_def import (
    BaseObject,
)
from weave.trace_server.interface.builtin_object_classes.leaderboard import Leaderboard
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModel,
)
from weave.trace_server.interface.builtin_object_classes.provider import (
    Provider,
    ProviderModel,
)
from weave.trace_server.interface.builtin_object_classes.saved_view import SavedView
from weave.trace_server.interface.builtin_object_classes.test_only_example import (
    TestOnlyExample,
    TestOnlyNestedBaseObject,
)

BUILTIN_OBJECT_REGISTRY: dict[str, type[BaseObject]] = {}


def register_base_object(cls: type[BaseObject]) -> None:
    """
    Register a BaseObject class in the global registry.

    Args:
        cls: The BaseObject class to register
    """
    BUILTIN_OBJECT_REGISTRY[cls.__name__] = cls


register_base_object(TestOnlyExample)
register_base_object(TestOnlyNestedBaseObject)
register_base_object(Leaderboard)
register_base_object(ActionSpec)
register_base_object(AnnotationSpec)
register_base_object(Provider)
register_base_object(ProviderModel)
register_base_object(SavedView)
register_base_object(LLMStructuredCompletionModel)
