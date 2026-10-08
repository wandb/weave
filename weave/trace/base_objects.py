from pydantic import BaseModel

from weave.flow.llm_structured_model import LLMStructuredCompletionModel
from weave.shared.interface.builtin_object_classes import builtin_object_registry
from weave.shared.interface.builtin_object_classes.builtin_object_registry import (
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
    register_base_object,
)

__all__ = [
    "BUILTIN_OBJECT_REGISTRY",
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

# The server validates against the passive schema in weave.shared; the SDK
# decodes stored objects into the executable model.
BUILTIN_OBJECT_REGISTRY: dict[str, type[BaseModel]] = {
    **builtin_object_registry.BUILTIN_OBJECT_REGISTRY,
    LLMStructuredCompletionModel.__name__: LLMStructuredCompletionModel,
}
