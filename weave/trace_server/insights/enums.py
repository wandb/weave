"""Shared vocabulary for the insights endpoints.

The literals and ceilings that both the write and the read surface name, in one
place so a new signature type or a new write gate is a single edit.
"""

from typing import Literal

# Intent rows say what a user was trying to do; failure rows say how an agent
# went wrong. Each read and each write names exactly one.
InsightSignatureType = Literal["intent", "failure"]
InsightQueryMode = Literal["rows", "groups"]
InsightRowOrder = Literal["key", "recent"]
InsightGroupField = Literal[
    "signature", "category", "sentiment", "severity", "agent_name", "day"
]

# The first four discard the candidate; the last three repair the label and keep it.
InsightWriteGate = Literal[
    "empty_signature",
    "vector_dimensions",
    "ungrounded_attribution",
    "duplicate_in_batch",
    "unknown_category",
    "unknown_sentiment",
    "unknown_severity",
]

DEFAULT_SIGNATURE_LIMIT = 100
MAX_SIGNATURE_LIMIT = 10_000
# A vector page carries `embedding.dimensions` floats per row, so it gets its own
# ceiling well below the row ceiling.
MAX_VECTOR_PAGE_LIMIT = 1_000

# `mode` picks one result shape, and the knobs of the other shape are then
# meaningless. Naming one is rejected rather than silently ignored.
ROWS_ONLY_FIELDS = frozenset({"order", "cursor", "include_vector"})
GROUPS_ONLY_FIELDS = frozenset({"group_by"})
