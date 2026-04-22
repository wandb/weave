from __future__ import annotations

import atexit
import datetime
import json
import keyword
import logging
import re
from collections.abc import Callable
from threading import Lock
from typing import Any, TypeVar, cast

from weave.dataset.dataset import Dataset
from weave.flow.scorer import Scorer
from weave.flow.util import make_memorable_name
from weave.object.obj import Object
from weave.trace.table import Table

DEFAULT_SCORER_CACHE_SIZE = 1000

T = TypeVar("T")
ID = str
ScoreType = float | bool | dict

logger = logging.getLogger(__name__)

VALID_CLASS_NAME_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

IMPERATIVE_EVAL_MARKER = {"_weave_eval_meta": {"imperative": True}}
IMPERATIVE_SCORE_MARKER = {"_weave_eval_meta": {"imperative": True, "score": True}}


# Accepts any logger duck-typed with `_is_finalized: bool` and `.finish()`.
# V1 (EvaluationLogger) and V2 (EvaluationLoggerV2) both satisfy this.
_active_evaluation_loggers: list[Any] = []


def _cleanup_all_evaluations() -> None:
    for eval_logger in _active_evaluation_loggers:
        _cleanup_evaluation(eval_logger)


def _cleanup_evaluation(eval_logger: Any) -> None:
    try:
        if not eval_logger._is_finalized:
            eval_logger.finish()
    except Exception:
        logger.exception("Error during cleanup of evaluation logger")


atexit.register(_cleanup_all_evaluations)


def _sanitize_class_name(name: str) -> str:
    """Return a valid Python class name based on a string."""
    class_name = re.sub(r"\W", "", name)
    if class_name == "":
        return "GeneratedClass"

    first_char = class_name[0]
    if not first_char.isalpha() and first_char != "_":
        class_name = "C" + class_name

    if keyword.iskeyword(class_name):
        class_name += "Class"

    return class_name


def _validate_class_name(name: str, base_class_name: str = "Class") -> str:
    if not name:
        raise ValueError(f"{base_class_name} name cannot be empty")

    if not VALID_CLASS_NAME_REGEX.match(name):
        raise ValueError(
            f"Invalid `{base_class_name}` name: '{name}'. `{base_class_name}` names must start with a letter or underscore "
            "and contain only alphanumeric characters and underscores."
        )

    if keyword.iskeyword(name):
        raise ValueError(
            f"`{base_class_name}` name '{name}' cannot be a Python keyword"
        )

    return name


def _cast_to_cls(type_: type[T]) -> Callable[[str | dict | T], T]:
    def _convert_to_cls_inner(value: str | dict | T) -> T:
        if isinstance(value, str):
            cls_name = _sanitize_class_name(value)
            cls_name = _validate_class_name(cls_name, type_.__name__)

            pydantic_config_dict = {
                "__annotations__": {"name": str},
                "name": cls_name,
            }

            cls = type(cls_name, (type_,), pydantic_config_dict)
            return cast(T, cls())

        elif isinstance(value, dict):
            attributes = value

            if "name" not in attributes:
                raise ValueError("Your dict must contain a `name` key.")

            pydantic_config_dict = {
                "__annotations__": dict.fromkeys(attributes, Any),
                **attributes,
            }
            cls = type(attributes["name"], (type_,), pydantic_config_dict)
            return cast(T, cls())

        elif isinstance(value, type_):
            instance = value
            if isinstance(instance, Object) and not instance.name:
                instance.name = instance.__class__.__name__
            return instance

        raise TypeError("Unsupported type for casting")

    return _convert_to_cls_inner


def _cast_to_imperative_dataset(value: Dataset | list[dict] | str) -> Dataset:
    if isinstance(value, str):
        return Dataset(name=value, rows=Table([{"dataset_id": value}]))
    elif isinstance(value, list):
        return Dataset(rows=Table(value))
    elif isinstance(value, Dataset):
        return value
    else:
        raise TypeError("Unsupported type for casting")


def _default_dataset_name() -> str:
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"{date}-{unique_name}-dataset"


class ScorerCache:
    _cached_scorers: dict[str, Scorer]
    _cached_scorers_lock: Any
    _max_size: int

    def __init__(self, max_size: int = DEFAULT_SCORER_CACHE_SIZE) -> None:
        self._cached_scorers = {}
        self._cached_scorers_lock = Lock()
        self._max_size = max_size

    def get_scorer(
        self, scorer_id: str, default_factory: Callable[[], Scorer]
    ) -> Scorer:
        with self._cached_scorers_lock:
            if scorer_id not in self._cached_scorers:
                if len(self._cached_scorers) >= self._max_size:
                    self._cached_scorers.popitem()
                self._cached_scorers[scorer_id] = default_factory()
        return self._cached_scorers[scorer_id]


global_scorer_cache = ScorerCache()


def scorer_to_cache_key(scorer: Scorer | dict | str) -> str:
    return json.dumps(scorer)
