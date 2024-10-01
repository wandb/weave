from typing import Dict, Optional, Union
import warnings

from notdiamond.toolkit.custom_router import CustomRouter
import pandas as pd

import weave


def train_on_evaluations(
    model_evals: dict[Union[weave.Model, str], weave.EvaluationResults],
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

        df_rows = []
        score_col_name = None
        for row in eval_results.rows:
            _df_row = dict()
            for col, val in row.items():
                if col == 'scores':
                    # get the first score; raise if there are multiple
                    if len(val) > 1:
                        raise ValueError(f"Multiple eval scores for {model}. Please specify a single score column.")

                    score_column, score_val = next(iter(val.items()))
                    _nd_score_column = f"{score_column}_score"
                    _df_row[_nd_score_column] = score_val

                    if score_col_name is not None and _nd_score_column != score_col_name:
                        raise ValueError(
                            f"Multiple eval scores for {model}: {score_col_name} and {_nd_score_column}. Please specify a single score column."
                        )
                    score_col_name = _nd_score_column
                else:
                    _df_row[col] = val
            df_rows.append(_df_row)
        eval_df = pd.DataFrame(df_rows)
        router_dataset[model] = eval_df

    custom_router = CustomRouter(language=language, maximize=maximize, api_key=api_key)

    return custom_router.fit(
        router_dataset,
        prompt_column=prompt_column,
        response_column=response_column,
        score_column=score_col_name,
        preference_id=preference_id,
    )

def train_on_dataset(
    dataset: weave.Dataset,
    prompt_column: str,
    response_column: str,
    score_column: str,
    preference_id: Optional[str] = None,
    **kwargs,
) -> CustomRouter:
    """
    """
    # todo
    pass

def _placeholder_model_name() -> str:
    import random
    import string
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(random.choices(alphabet, k=8))
