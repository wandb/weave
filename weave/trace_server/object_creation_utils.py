"""Utils for creating object payloads that are similar to what the SDK would create."""

from __future__ import annotations

from typing import Any

OP_SOURCE_FILE_NAME = "obj.py"
PLACEHOLDER_OP_SOURCE = """def func(*args, **kwargs):
    ... # Code-capture unavailable for this op
"""
PLACEHOLDER_SCORER_SUMMARIZE_OP_SOURCE = """def summarize(score_rows: list) -> dict | None:
    '''Default summarize implementation that auto-summarizes score rows.'''
    from weave.flow.scorer import auto_summarize
    return auto_summarize(score_rows)
"""
PLACEHOLDER_EVALUATE_OP_SOURCE = """import weave
@weave.op()
def evaluate(evaluation, model):
    \"\"\"Placeholder evaluate function.\"\"\"
    # TODO: Implement actual evaluation logic
    return {"status": "not_implemented"}
"""
PLACEHOLDER_PREDICT_AND_SCORE_OP_SOURCE = """import weave
@weave.op()
def predict_and_score(evaluation, example):
    \"\"\"Placeholder predict_and_score function.\"\"\"
    # TODO: Implement actual predict and score logic
    return {"prediction": None, "scores": {}}
"""
PLACEHOLDER_EVALUATION_SUMMARIZE_OP_SOURCE = """import weave
@weave.op()
def summarize(evaluation_results):
    \"\"\"Placeholder summarize function.\"\"\"
    # TODO: Implement actual summarization logic
    return {"summary": "not_implemented"}
"""
PLACEHOLDER_EVALUATION_EVALUATE_OP_SOURCE = """import weave
@weave.op()
def evaluate(evaluation, model):
    \"\"\"Placeholder evaluate function.\"\"\"
    # TODO: Implement actual evaluation logic
    return {"status": "not_implemented"}
"""
PLACEHOLDER_EVALUATION_PREDICT_AND_SCORE_OP_SOURCE = """import weave
@weave.op()
def predict_and_score(evaluation, example):
    \"\"\"Placeholder predict_and_score function.\"\"\"
    # TODO: Implement actual predict and score logic
    return {"prediction": None, "scores": {}}
"""
PLACEHOLDER_EVALUATION_SUMMARIZE_OP_SOURCE = """import weave
@weave.op()
def summarize(evaluation_results):
    \"\"\"Placeholder summarize function.\"\"\"
    # TODO: Implement actual summarization logic
    return {"summary": "not_implemented"}
"""
PLACEHOLDER_MODEL_PREDICT_OP_SOURCE = """import weave
@weave.op()
def predict(model, **inputs):
    \"\"\"Placeholder model predict function.\"\"\"
    # System-generated op for model predictions
    return model.predict(**inputs)
"""
PLACEHOLDER_SCORER_SCORE_OP_SOURCE = """import weave
@weave.op()
def score(scorer, **inputs):
    \"\"\"Placeholder scorer score function.\"\"\"
    # System-generated op for scoring
    return scorer.score(**inputs)
"""


def make_safe_name(name: str | None) -> str:
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
    if name is None:
        name = "unknown"
    return name.replace(" ", "_").replace("/", "_").lower()


def make_dataset_id(name: str | None) -> str:
    """Create a dataset object ID from a dataset name.

    Args:
        name: The dataset name (can be None)

    Returns:
        The dataset object ID: "Dataset" if name is None, otherwise the sanitized name

    Examples:
        >>> make_dataset_id(None)
        'Dataset'
        >>> make_dataset_id("My Dataset")
        'my_dataset'
        >>> make_dataset_id("user/model")
        'user_model'
    """
    if name is None:
        return "Dataset"
    return make_safe_name(name)


def make_scorer_id(name: str | None) -> str:
    """Create a scorer object ID from a scorer name.

    Args:
        name: The scorer name (can be None)

    Returns:
        The scorer object ID: "Scorer" if name is None, otherwise the sanitized name

    Examples:
        >>> make_scorer_id(None)
        'Scorer'
        >>> make_scorer_id("My Scorer")
        'my_scorer'
        >>> make_scorer_id("user/scorer")
        'user_scorer'
    """
    if name is None:
        return "Scorer"
    return make_safe_name(name)


def make_evaluation_id(name: str | None) -> str:
    """Create an evaluation object ID from an evaluation name.

    Args:
        name: The evaluation name (can be None)

    Returns:
        The evaluation object ID: "Evaluation" if name is None, otherwise the sanitized name

    Examples:
        >>> make_evaluation_id(None)
        'Evaluation'
        >>> make_evaluation_id("My Evaluation")
        'my_evaluation'
        >>> make_evaluation_id("user/eval")
        'user_eval'
    """
    if name is None:
        return "Evaluation"
    return make_safe_name(name)


def make_model_id(name: str | None) -> str:
    """Create a model object ID from a model name.

    Args:
        name: The model name (can be None)

    Returns:
        The model object ID: "Model" if name is None, otherwise the sanitized name

    Examples:
        >>> make_model_id(None)
        'Model'
        >>> make_model_id("My Model")
        'my_model'
        >>> make_model_id("user/model")
        'user_model'
    """
    if name is None:
        return "Model"
    return make_safe_name(name)


def make_op_id(name: str | None) -> str:
    """Create an op object ID from an op name.

    Args:
        name: The op name (can be None)

    Returns:
        The op object ID: "Op" if name is None, otherwise the sanitized name

    Examples:
        >>> make_op_id(None)
        'Op'
        >>> make_op_id("My Op")
        'my_op'
        >>> make_op_id("user/op")
        'user_op'
    """
    if name is None:
        return "Op"
    return make_safe_name(name)


def build_op_val(file_digest: str, load_op: str | None = None) -> dict[str, Any]:
    """Build the op value structure with a file digest (post-file-upload).

    This creates the structure that matches what the SDK produces after file upload,
    where the files dict contains digest strings rather than content bytes.

    Args:
        file_digest: The digest of the uploaded source file
        load_op: Optional URI of the load_op (for non-Op custom types)

    Returns:
        Dictionary with the complete structure for an Op object ready for storage

    Examples:
        >>> result = build_op_val_with_file_digest("abc123")
        >>> result["files"][OP_SOURCE_FILE_NAME]
        'abc123'
    """
    result = {
        "_type": "CustomWeaveType",
        "weave_type": {"type": "Op"},
        "files": {OP_SOURCE_FILE_NAME: file_digest},
    }
    if load_op is not None:
        result["load_op"] = load_op
    return result


def build_dataset_val(
    table_ref: str, name: str | None = None, description: str | None = None
) -> dict[str, Any]:
    """Build the value dictionary for a Dataset object.

    Args:
        name: The dataset name
        description: Optional description
        table_ref: Reference to the table containing the dataset rows

    Returns:
        Dictionary representing the dataset object value
    """
    if name is None:
        name = "Dataset"

    return {
        "_type": "Dataset",
        "_class_name": "Dataset",
        "_bases": ["Object", "BaseModel"],
        "name": name,
        "description": description,
        "rows": table_ref,
    }


def build_table_ref(entity: str, project: str, digest: str) -> str:
    return f"weave:///{entity}/{project}/table/{digest}"


def build_object_ref(entity: str, project: str, object_id: str, digest: str) -> str:
    return f"weave:///{entity}/{project}/object/{object_id}:{digest}"


def build_scorer_val(
    name: str,
    description: str | None,
    score_op_ref: str,
    summarize_op_ref: str,
    column_map: dict[str, str] | None = None,
    class_name: str = "Scorer",
) -> dict[str, Any]:
    """Build the value dictionary for a Scorer object.

    Args:
        name: The scorer name
        description: Optional description (defaults to "Scorer: {name}")
        score_op_ref: Reference to the op implementing the scoring logic
        summarize_op_ref: Reference to the op implementing the summarize method
        column_map: Optional mapping from dataset columns to scorer argument names
        class_name: The class name (defaults to "Scorer" for base scorers, or a custom name for subclasses)

    Returns:
        Dictionary representing the scorer object value
    """
    # Base Scorer has bases ["Object", "BaseModel"]
    # Custom subclasses have bases ["Scorer", "Object", "BaseModel"]
    if class_name == "Scorer":
        bases = ["Object", "BaseModel"]
    else:
        bases = ["Scorer", "Object", "BaseModel"]

    return {
        "_type": class_name,
        "_class_name": class_name,
        "_bases": bases,
        "name": name,
        "description": description,
        "score": score_op_ref,
        "summarize": summarize_op_ref,
        "column_map": column_map,
    }


def build_model_val(
    name: str,
    description: str | None,
    source_file_digest: str,
    attributes: dict[str, Any] | None = None,
    class_name: str = "Model",
) -> dict[str, Any]:
    """Build the value dictionary for a Model object.

    Args:
        name: The model name
        description: Optional description of the model
        source_file_digest: Digest of the uploaded source code file
        attributes: Optional additional attributes for the model
        class_name: The class name (defaults to "Model" for base models, or a custom name for subclasses)

    Returns:
        Dictionary representing the model object value
    """
    if class_name == "Model":
        bases = ["Object", "BaseModel"]
    else:
        bases = ["Model", "Object", "BaseModel"]

    result = {
        "_type": class_name,
        "_class_name": class_name,
        "_bases": bases,
        "name": name,
        "description": description,
        "files": {OP_SOURCE_FILE_NAME: source_file_digest},
    }

    if attributes is not None:
        result.update(attributes)

    return result


def build_evaluation_val(
    name: str,
    dataset_ref: str,
    trials: int,
    description: str | None,
    scorer_refs: list[str] | None,
    evaluation_name: str | None,
    metadata: dict[str, Any] | None,
    preprocess_model_input: str | None,
    evaluate_ref: str,
    predict_and_score_ref: str,
    summarize_ref: str,
    class_name: str = "Evaluation",
    eval_attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the value dictionary for an Evaluation object.

    Args:
        name: The evaluation name
        dataset_ref: Reference to the dataset (weave:// URI)
        trials: Number of trials to run
        description: Optional description of the evaluation
        scorer_refs: Optional list of scorer references (weave:// URIs)
        evaluation_name: Optional name for the evaluation run
        metadata: Optional metadata for the evaluation
        preprocess_model_input: Optional reference to a function that preprocesses model inputs
        evaluate_ref: Reference to the op implementing the evaluate method
        predict_and_score_ref: Reference to the op implementing the predict_and_score method
        summarize_ref: Reference to the op implementing the summarize method
        class_name: The class name (defaults to "Evaluation" for base evaluations, or a custom name for subclasses)
        eval_attributes: Optional attributes for the evaluation

    Returns:
        Dictionary representing the evaluation object value
    """
    if class_name == "Evaluation":
        bases = ["Object", "BaseModel"]
    else:
        bases = ["Evaluation", "Object", "BaseModel"]

    result = {
        "_type": class_name,
        "_class_name": class_name,
        "_bases": bases,
        "name": name,
        "description": description,
        "dataset": dataset_ref,
        "scorers": scorer_refs or [],
        "trials": trials,
        "evaluation_name": evaluation_name,
        "metadata": metadata,
        "preprocess_model_input": preprocess_model_input,
        "evaluate": evaluate_ref,
        "predict_and_score": predict_and_score_ref,
        "summarize": summarize_ref,
    }

    if eval_attributes is not None:
        result.update(eval_attributes)

    return result
