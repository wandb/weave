from pydantic import BaseModel

from weave.flow.llm_structured_model import LLMStructuredCompletionModel
from weave.shared.builtin_object_classes.builtin_object_registry import (
    BUILTIN_OBJECT_REGISTRY as SHARED_BUILTIN_OBJECT_REGISTRY,
)
from weave.shared.builtin_object_classes.builtin_object_registry import (
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
    **SHARED_BUILTIN_OBJECT_REGISTRY,
    "LLMStructuredCompletionModel": LLMStructuredCompletionModel,
}


def register_base_object(cls: type[BaseModel]) -> None:
    """Register a class for SDK object reconstruction."""
    BUILTIN_OBJECT_REGISTRY[cls.__name__] = cls
