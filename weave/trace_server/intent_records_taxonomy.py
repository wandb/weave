"""Category taxonomy for intent records, shared by the writer and the schema.

The `category` column in migration 040 is a closed Enum over the union of the two
lens taxonomies, with a constraint pinning each label to its lens. This module is
what the writer labels from, and
`test_intent_records_schema_and_replacement_lifecycle` asserts the applied schema
matches it, so a judge prompt and the DDL cannot drift apart silently.
"""

from __future__ import annotations

# An omitted category. Deliberately has no DEFAULT in the DDL, so an unlabeled
# row reads back empty instead of claiming to be the first Enum label.
UNSET_CATEGORY = ""
UNSET_CATEGORY_VALUE = 0

# Valid under either lens. The writer maps a judge label it does not recognize to
# this, so a novel label degrades to 'other' instead of failing the whole insert
# batch against the Enum.
SHARED_CATEGORIES: dict[str, int] = {"other": 10}

# What the user's turn was trying to do. Values 1-20 belong to this lens.
INTENT_ONLY_CATEGORIES: dict[str, int] = {
    "action_request": 1,
    "information_request": 2,
    "problem_report": 3,
    "feedback": 4,
    "approval": 5,
    "rejection": 6,
    "correction": 7,
    "clarification": 8,
    "bad_faith": 9,
}

# How the agent's turn went wrong. Values 21 and up belong to this lens.
FAILURE_ONLY_CATEGORIES: dict[str, int] = {
    "task_misunderstanding": 21,
    "context_loss": 22,
    "wrong_output": 23,
    "requirement_violation": 24,
    "tool_misuse": 25,
    "tool_failure": 26,
    "system_error": 27,
    "unproductive_loop": 28,
    "capability_gap": 29,
    "improper_refusal": 30,
    "safety_violation": 31,
}

INTENT_CATEGORIES: dict[str, int] = {**INTENT_ONLY_CATEGORIES, **SHARED_CATEGORIES}
FAILURE_CATEGORIES: dict[str, int] = {**FAILURE_ONLY_CATEGORIES, **SHARED_CATEGORIES}

CATEGORIES_BY_LENS: dict[str, dict[str, int]] = {
    "intent": INTENT_CATEGORIES,
    "failure": FAILURE_CATEGORIES,
}

ALL_CATEGORIES: dict[str, int] = {
    UNSET_CATEGORY: UNSET_CATEGORY_VALUE,
    **INTENT_CATEGORIES,
    **FAILURE_CATEGORIES,
}


def clickhouse_enum_type() -> str:
    """Render the taxonomy as the Enum8 type ClickHouse reports for `category`.

    Sorted by value because ClickHouse normalizes a reported Enum to ascending
    numeric order regardless of the order it was declared in.
    """
    members = ", ".join(
        f"'{name}' = {value}"
        for name, value in sorted(ALL_CATEGORIES.items(), key=lambda item: item[1])
    )
    return f"Enum8({members})"
