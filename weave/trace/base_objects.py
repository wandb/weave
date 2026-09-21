from weave.flow.llm_structured_model import LLMStructuredCompletionModel
from weave.shared.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    BUILTIN_OBJECT_REGISTRY as _SCHEMA_REGISTRY,
)
from weave.shared.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    AgentDashboard,
    AlertSpec,
    AnnotationSpec,
    BaseObject,
    ChartConfig,
    ComparisonView,
    Leaderboard,
    Provider,
    ProviderModel,
    SavedView,
    TestOnlyExample,
    TestOnlyInheritedBaseObject,
    TestOnlyNestedBaseObject,
)

BUILTIN_OBJECT_REGISTRY = dict(_SCHEMA_REGISTRY)
BUILTIN_OBJECT_REGISTRY["LLMStructuredCompletionModel"] = LLMStructuredCompletionModel


def register_base_object(cls: type[BaseObject]) -> None:
    """Register a BaseObject class in the global registry.

    Args:
        cls: The BaseObject class to register
    """
    BUILTIN_OBJECT_REGISTRY[cls.__name__] = cls


__all__ = [
    "BUILTIN_OBJECT_REGISTRY",
    "AgentDashboard",
    "AlertSpec",
    "AnnotationSpec",
    "BaseObject",
    "ChartConfig",
    "ComparisonView",
    "LLMStructuredCompletionModel",
    "Leaderboard",
    "Provider",
    "ProviderModel",
    "SavedView",
    "TestOnlyExample",
    "TestOnlyInheritedBaseObject",
    "TestOnlyNestedBaseObject",
    "register_base_object",
]
