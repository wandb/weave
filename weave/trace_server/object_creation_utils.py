"""Shared utilities for creating high-level objects (Dataset, Scorer, Evaluation, Op).

This module provides helper functions for building the common data structures
and source code templates used by both SQLite and ClickHouse trace servers.
"""

from __future__ import annotations

from typing import Any

# Constants for Op serialization
OP_SOURCE_FILE_NAME = "obj.py"


def make_safe_name(name: str) -> str:
    """Convert a name to a safe identifier format.

    Args:
        name: The name to sanitize

    Returns:
        A safe identifier with spaces and slashes replaced by underscores, lowercased

    Examples:
        >>> make_safe_name("My Dataset")
        'my_dataset'
        >>> make_safe_name("user/model")
        'user_model'
    """
    return name.replace(" ", "_").replace("/", "_").lower()


def build_op_val_base() -> dict[str, Any]:
    """Build the base value dictionary structure for an Op object.

    Returns:
        Dictionary with the base structure for an Op object (before adding files)
    """
    return {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "Op"},
        "files": {},
    }


def build_file_digest_entry(digest: str) -> dict[str, str]:
    """Build a file digest entry for Op serialization.

    Args:
        digest: The file content digest

    Returns:
        Dictionary in the format expected for file references

    Examples:
        >>> build_file_digest_entry("abc123")
        {'digest': 'abc123'}
    """
    return {"digest": digest}


def build_dataset_val(
    name: str, description: str | None, table_ref: str
) -> dict[str, Any]:
    """Build the value dictionary for a Dataset object.

    Args:
        name: The dataset name
        description: Optional description (defaults to "Dataset: {name}")
        table_ref: Reference to the table containing the dataset rows

    Returns:
        Dictionary representing the dataset object value
    """
    return {
        # Metadata
        "_class_name": "Dataset",
        "_bases": ["Object", "BaseModel"],
        # Actual fields
        "name": name,
        "description": description or f"Dataset: {name}",
        "rows": table_ref,
    }


def build_scorer_val(name: str, description: str | None, op_ref: str) -> dict[str, Any]:
    """Build the value dictionary for a Scorer object.

    Args:
        name: The scorer name
        description: Optional description (defaults to "Scorer: {name}")
        op_ref: Reference to the op implementing the scoring logic

    Returns:
        Dictionary representing the scorer object value
    """
    return {
        # Metadata
        "_class_name": "Scorer",
        "_bases": ["Object", "BaseModel"],
        # Actual fields
        "name": name,
        "description": description or f"Scorer: {name}",
        "op": op_ref,
    }


def build_evaluation_val(
    name: str,
    dataset_ref: str,
    trials: int,
    description: str | None = None,
    scorer_refs: list[str] | None = None,
    evaluation_name: str | None = None,
    eval_attributes: dict[str, Any] | None = None,
    evaluate_ref: str | None = None,
    predict_and_score_ref: str | None = None,
    summarize_ref: str | None = None,
) -> dict[str, Any]:
    """Build the value dictionary for an Evaluation object.

    Args:
        name: The evaluation name
        dataset_ref: Reference to the dataset to evaluate
        trials: Number of evaluation trials
        description: Optional description
        scorer_refs: Optional list of scorer references
        evaluation_name: Optional evaluation name override
        eval_attributes: Optional attributes for the evaluation
        evaluate_ref: Optional reference to evaluate op
        predict_and_score_ref: Optional reference to predict_and_score op
        summarize_ref: Optional reference to summarize op

    Returns:
        Dictionary representing the evaluation object value
    """
    evaluation_val: dict[str, Any] = {
        # Metadata
        "_class_name": "Evaluation",
        "_bases": ["Object", "BaseModel"],
        # Required fields
        "name": name,
        "dataset": dataset_ref,
        "trials": trials,
    }

    # Add optional fields if provided
    if description is not None:
        evaluation_val["description"] = description
    if scorer_refs is not None:
        evaluation_val["scorers"] = scorer_refs
    if evaluation_name is not None:
        evaluation_val["evaluation_name"] = evaluation_name
    if eval_attributes is not None:
        evaluation_val["eval_attributes"] = eval_attributes
    if evaluate_ref is not None:
        evaluation_val["evaluate"] = evaluate_ref
    if predict_and_score_ref is not None:
        evaluation_val["predict_and_score"] = predict_and_score_ref
    if summarize_ref is not None:
        evaluation_val["summarize"] = summarize_ref

    return evaluation_val


def get_placeholder_evaluate_source() -> str:
    """Get placeholder source code for the evaluate method.

    Returns:
        Python source code for a placeholder evaluate function
    """
    return """import weave

@weave.op()
def evaluate(evaluation, model):
    \"\"\"Placeholder evaluate function.\"\"\"
    # TODO: Implement actual evaluation logic
    return {"status": "not_implemented"}
"""


def get_placeholder_predict_and_score_source() -> str:
    """Get placeholder source code for the predict_and_score method.

    Returns:
        Python source code for a placeholder predict_and_score function
    """
    return """import weave

@weave.op()
def predict_and_score(evaluation, example):
    \"\"\"Placeholder predict_and_score function.\"\"\"
    # TODO: Implement actual predict and score logic
    return {"prediction": None, "scores": {}}
"""


def get_placeholder_summarize_source() -> str:
    """Get placeholder source code for the summarize method.

    Returns:
        Python source code for a placeholder summarize function
    """
    return """import weave

@weave.op()
def summarize(evaluation_results):
    \"\"\"Placeholder summarize function.\"\"\"
    # TODO: Implement actual summarization logic
    return {"summary": "not_implemented"}
"""


def build_object_ref(entity: str, project: str, object_id: str, digest: str) -> str:
    """Build a weave object reference URI.

    Args:
        entity: The entity name
        project: The project name
        object_id: The object identifier
        digest: The object digest

    Returns:
        A weave:/// URI string

    Examples:
        >>> build_object_ref("user", "my-project", "dataset_test", "abc123")
        'weave:///user/my-project/object/dataset_test:abc123'
    """
    return f"weave:///{entity}/{project}/object/{object_id}:{digest}"


def build_table_ref(entity: str, project: str, digest: str) -> str:
    """Build a weave table reference URI.

    Args:
        entity: The entity name
        project: The project name
        digest: The table digest

    Returns:
        A weave:/// URI string

    Examples:
        >>> build_table_ref("user", "my-project", "abc123")
        'weave:///user/my-project/table/abc123'
    """
    return f"weave:///{entity}/{project}/table/{digest}"
