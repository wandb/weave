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

BUILTIN_OBJECT_REGISTRY: dict[str, type[BaseModel]] = {
    **builtin_object_registry.BUILTIN_OBJECT_REGISTRY,
    LLMStructuredCompletionModel.__name__: LLMStructuredCompletionModel,
}


def register_base_object(cls: type[BaseObject]) -> None:
    builtin_object_registry.register_base_object(cls)
    BUILTIN_OBJECT_REGISTRY[cls.__name__] = cls
