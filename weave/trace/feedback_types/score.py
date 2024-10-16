# This type is still "Beta" and the underlying payload might change as well.
# We're using "beta.1" to indicate that this is a pre-release version.
from typing import TypedDict

SCORE_TYPE_NAME = "wandb.score.beta.1"


class ScoreTypePayload(TypedDict):
    name: str
    op_ref: str
    call_ref: str
    results: dict
    # supervision: dict
