from tests.trace.data_serialization.spec import SerializationTestCase
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
[] tuple
[] set

## Media Types:
[X] Audio
[] Content
[x] Datetime
[] File
[x] Image
[x] Markdown
[X] Video

## Container Types:
[] Dataclass
[] Pydantic BaseModel

## Weave Core Types:
[] Op
[] Object

## Weave Library Objects:
[] Model
[] Scorer
[] Evaluation
[] Dataset
[] Prompt

### Weave Library Specialized Objects:
[] LLMStructuredCompletionModel
[] LLMAsAJudgeScorer

## Weave Config Objects:
[] AnnotationSpec
[] Leaderboard
[] SavedView
[] Monitor
"""

cases: list[SerializationTestCase] = [
    *primitive_cases,
    *media_cases,
]
