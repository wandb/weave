from typing import Dict, Optional, Tuple, Union

from notdiamond.toolkit.custom_router import CustomRouter
import pandas as pd

import weave
from weave import Dataset, Model
from weave.flow.eval import EvaluationResults

@weave.op(
    description="Train a custom router on evaluation results.",
    name="notdiamond.custom_router.train_evaluations",
)
def train_evaluations(
    model_evals: dict[Union[weave.Model, str], EvaluationResults],
    prompt_column: str,
    response_column: str,
    preference_id: Optional[str] = None,
    language: str = None,
    maximize: bool = None,
    api_key: Optional[str] = None,
) -> CustomRouter:
    """
    Currently only supports EvaluationResults with a single score column.
    """
    router_dataset: Dict[str, pd.DataFrame] = {}

    for model, eval_results in model_evals.items():
        if isinstance(model, weave.Model):
            model = model.name or f"model-{_placeholder_model_name()}"

        score_col_name, eval_df = _build_dataframe(model, eval_results)
        router_dataset[model] = eval_df

    custom_router = CustomRouter(language=language, maximize=maximize, api_key=api_key)

    return custom_router.fit(
        router_dataset,
        prompt_column=prompt_column,
        response_column=response_column,
        score_column=score_col_name,
        preference_id=preference_id,
    )

@weave.op(
    description="Evaluate a custom router.",
    name="notdiamond.custom_router.evaluate_router",
)
def evaluate_router(
    model_datasets: dict[Union[weave.Model, str], Dataset],
    prompt_column: str,
    response_column: str,
    preference_id: str,
    api_key: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    router_dataset: Dict[str, pd.DataFrame] = {}

    for model, dataset in model_datasets.items():
        score_column, model_df = _build_dataframe(model, dataset)
        router_dataset[model] = model_df[[prompt_column, response_column, score_column]]

    custom_router = CustomRouter(api_key=api_key)
    eval_results, eval_stats = custom_router.eval(
        router_dataset,
        prompt_column=prompt_column,
        response_column=response_column,
        score_column=score_column,
        preference_id=preference_id,
    )

    return eval_results, eval_stats

def _get_score_column(model: str, scores: dict, score_col_name: str = None) -> Tuple[str, float]:
    """
    Extract a single score from the nested `scores` column.
        - raise for multiple scores
        - build score column name if not provided
    """
    if len(scores) > 1:
        raise ValueError(
            f"Multiple eval scores for {model}. Please specify a single score column."
        )

    score_column, score_val = next(iter(scores.items()))
    _nd_score_column = f"{score_column}_score"
    if score_col_name is not None and _nd_score_column != score_col_name:
        raise ValueError(
            f"Multiple eval scores for {model}: {score_col_name} and {_nd_score_column}. "
            "Please specify a single score column."
        )

    return _nd_score_column, score_val


def _build_dataframe(
    model: str, dataset: Union[EvaluationResults, Dataset]
) -> Tuple[str, pd.DataFrame]:
    df_rows = []
    score_col_name = None
    for row in dataset.rows:
        _df_row = dict()
        for col, val in row.items():
            if col == "scores":
                col, val = _get_score_column(model, val, score_col_name=score_col_name)
                score_col_name = score_col_name or col
            _df_row[col] = val
        df_rows.append(_df_row)

    return score_col_name, pd.DataFrame(df_rows)


def _placeholder_model_name() -> str:
    import random
    import string
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(random.choices(alphabet, k=8))
