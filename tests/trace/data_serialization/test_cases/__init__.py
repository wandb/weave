from tests.trace.data_serialization.spec import SerializationTestCase
from tests.trace.data_serialization.test_cases.config_cases import config_cases
from tests.trace.data_serialization.test_cases.container_cases import container_cases
from tests.trace.data_serialization.test_cases.core_types import core_cases
from tests.trace.data_serialization.test_cases.library_cases import library_cases
from tests.trace.data_serialization.test_cases.media_cases import media_cases
from tests.trace.data_serialization.test_cases.primitive_cases import primitive_cases

"""
# Data Type Directory (Test Checklist)

## Primitives:
[x] int
[x] float
[x] str
[x] bool
[x] None
[x] list
[x] dict
[] tuple (skipping)
[] set (skipping)

## Media Types:
[x] Audio
[x] Content
[x] Datetime
[] File (deprecated)
[x] Image
[x] Markdown
[x] Video

## Container Types:
[x] Dataclass
[x] Pydantic BaseModel

## Weave Core Types:
[x] Op
[x] Object

## Weave Evaluation Library Objects:
[x] Model
[x] Scorer
[x] Evaluation
[x] Dataset
[x] Prompt

### Weave Evaluation Library Specialized Objects:
[x] LLMStructuredCompletionModel
[x] LLMAsAJudgeScorer

## Weave Config Objects:
[x] AnnotationSpec
[x] Leaderboard
[x] SavedView
[x] Monitor
"""

cases: list[SerializationTestCase] = [
    *primitive_cases,
    *media_cases,
    *container_cases,
    *core_cases,
    *library_cases,
    *config_cases,
]
