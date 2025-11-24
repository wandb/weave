from typing import Any

import pandas as pd
from notdiamond.toolkit.custom_router import CustomRouter

import weave
from weave.evaluation.eval import EvaluationResults
from weave.utils.iterators import first


@weave.op(
    name="notdiamond.custom_router.train_router",
)
def train_router(
    model_evals: dict[weave.Model | str, EvaluationResults],
    prompt_column: str,
    response_column: str,
    preference_id: str | None = None,
    language: str | None = None,
    maximize: bool | None = None,
    api_key: str | None = None,
) -> CustomRouter:
    """Currently only supports EvaluationResults with a single score column."""
    router_dataset: dict[str, pd.DataFrame] = {}

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
    name="notdiamond.custom_router.evaluate_router",
)
def evaluate_router(
    model_datasets: dict[weave.Model | str, weave.Dataset],
    prompt_column: str,
    response_column: str,
    preference_id: str,
    api_key: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    router_dataset: dict[str, pd.DataFrame] = {}

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
    best_provider = eval_stats["Best Average Provider"][0]

    def _get_model_results(provider_name: str) -> pd.DataFrame:
        return eval_results[
            [prompt_column, f"{provider_name}/score", f"{provider_name}/response"]
        ].rename(
            columns={
                prompt_column: "prompt",
                f"{provider_name}/score": "score",
                f"{provider_name}/response": "response",
            }
        )

    model_results = _get_model_results(best_provider)
    not_diamond_results = _get_model_results("notdiamond")

    class _DummyEvalModel(weave.Model):
        model_results: pd.DataFrame

        @weave.op
        def predict(self, prompt: str) -> dict[str, Any]:
            response, score = self.model_results[
                self.model_results[prompt_column] == prompt
            ][["response", "score"]].values[0]
            return {"response": response, "score": score}

    class BestRoutedModel(_DummyEvalModel):
        model_name: str

        @weave.op
        def predict(self, prompt: str) -> dict[str, Any]:
            return super().predict(prompt)

    class NotDiamondRoutedModel(_DummyEvalModel):
        @weave.op
        def predict(self, prompt: str) -> dict[str, Any]:
            return super().predict(prompt)

    best_provider_model = BestRoutedModel(
        model_name=best_provider, model_results=model_results
    )
    not_diamond_model = NotDiamondRoutedModel(model_results=not_diamond_results)

    return best_provider_model, not_diamond_model


def _get_score_column(
    model: str, scores: dict, score_col_name: str | None = None
) -> tuple[str, float]:
    """Extract a single score from the nested `scores` column.
    - raise for multiple scores
    - build score column name if not provided.
    """
    if len(scores) > 1:
        raise ValueError(
            f"Multiple eval scores for {model}. Please specify a single score column."
        )

    score_column, score_val = first(scores.items())
    not_diamond_score_column = f"{score_column}_score"
    if score_col_name is not None and not_diamond_score_column != score_col_name:
        raise ValueError(
            f"Multiple eval scores for {model}: {score_col_name} and {not_diamond_score_column}. "
            "Please specify a single score column."
        )

    return not_diamond_score_column, score_val


def _build_dataframe(
    model: str, dataset: EvaluationResults | weave.Dataset
) -> tuple[str, pd.DataFrame]:
    df_rows = []
    score_col_name = None
    for row in dataset.rows:
        df_row = {}
        for col, val in row.items():
            if col == "scores":
                col, val = _get_score_column(model, val, score_col_name=score_col_name)
                score_col_name = score_col_name or col
            df_row[col] = val
        df_rows.append(df_row)

    if score_col_name is None:
        raise ValueError(f"No score column found for {model}. Is this correct?")

    return score_col_name, pd.DataFrame(df_rows)


def _placeholder_model_name() -> str:
    import random
    import string

    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choices(alphabet, k=8))


def _in_notebook() -> bool:
    try:
        from IPython import get_ipython

        if "IPKernelApp" not in get_ipython().config:  # pragma: no cover
            return False
    except ImportError:
        return False
    except AttributeError:
        return False
    return True
