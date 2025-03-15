import weave
from weave.builtin_objects.models.CompletionModel import LiteLLMCompletionModel
from weave.builtin_objects.scorers.LLMJudgeScorer import LLMJudgeScorer

_BUILTIN_REGISTRY: dict[str, type[weave.Object]] = {}


def register_builtin(cls: type[weave.Object]) -> None:
    if not issubclass(cls, weave.Object):
        raise TypeError(f"Object {cls} is not a subclass of weave.Object")

    if cls.__name__ in _BUILTIN_REGISTRY:
        raise ValueError(f"Object {cls} already registered")

    _BUILTIN_REGISTRY[cls.__name__] = cls


def get_builtin(name: str) -> type[weave.Object]:
    return _BUILTIN_REGISTRY[name]


register_builtin(LiteLLMCompletionModel)
register_builtin(LLMJudgeScorer)
# Since evals require nested refs, this is not possible yet
# register_builtin(weave.Evaluation)
