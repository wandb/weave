import json
import random
import string
from typing import Any

import pandas as pd
from notdiamond import NotDiamond

import weave
from weave.evaluation.eval import EvaluationResults
from weave.integrations.integration_metadata import library_integration
from weave.utils.iterators import first

# Integration provenance stamped onto the calls these helper ops produce.
NOTDIAMOND_INTEGRATION = library_integration("notdiamond")


@weave.op(
    name="notdiamond.custom_router.train_router",
    attributes=NOTDIAMOND_INTEGRATION.as_attributes(),
)
def train_router(
    model_evals: dict[weave.Model | str, EvaluationResults],
    prompt_column: str,
    response_column: str,
    preference_id: str | None = None,
    language: str | None = None,
    maximize: bool | None = None,
    api_key: str | None = None,
) -> str:
    """Currently only supports EvaluationResults with a single score column."""
    router_dataset: dict[str, pd.DataFrame] = {}

    for model_key, eval_results in model_evals.items():
        model = _model_name(model_key)

        score_col_name, eval_df = _build_dataframe(model, eval_results)
        router_dataset[model] = eval_df

    client = NotDiamond(api_key=api_key)
    training_df = _build_training_dataframe(
        router_dataset,
        prompt_column=prompt_column,
        response_column=response_column,
        score_column=score_col_name,
    )
    train_kwargs: dict[str, Any] = {
        "dataset_file": (
            "router_dataset.csv",
            training_df.to_csv(index=False).encode("utf-8"),
            "text/csv",
        ),
        "language": language or "en",
        "llm_providers": json.dumps(
            [_llm_provider_from_model_name(model) for model in router_dataset]
        ),
        "maximize": True if maximize is None else maximize,
        "prompt_column": prompt_column,
    }
    if preference_id is not None:
        train_kwargs["preference_id"] = preference_id

    response = client.custom_router.train_custom_router(**train_kwargs)
    return response.preference_id


@weave.op(
    name="notdiamond.custom_router.evaluate_router",
    attributes=NOTDIAMOND_INTEGRATION.as_attributes(),
)
def evaluate_router(
    model_datasets: dict[weave.Model | str, weave.Dataset],
    prompt_column: str,
    response_column: str,
    preference_id: str,
    api_key: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    router_dataset: dict[str, pd.DataFrame] = {}

    for source_model, dataset in model_datasets.items():
        model = _model_name(source_model)
        score_column, model_df = _build_dataframe(model, dataset)
        router_dataset[model] = model_df[[prompt_column, response_column, score_column]]

    client = NotDiamond(api_key=api_key)
    providers = [_llm_provider_from_model_name(model) for model in router_dataset]
    prompt_df = first(router_dataset.values())
    routed_rows = []
    for prompt in prompt_df[prompt_column]:
        response = client.model_router.select_model(
            llm_providers=providers,
            messages=[{"role": "user", "content": prompt}],
            metric="accuracy",
            max_model_depth=4,
            hash_content=False,
            preference_id=preference_id,
        )
        provider = response.providers[0]
        routed_model = f"{provider.provider}/{provider.model}"
        source_df = router_dataset[routed_model]
        response_value, score_value = source_df[source_df[prompt_column] == prompt][
            [response_column, score_column]
        ].values[0]
        routed_rows.append(
            {
                "prompt": prompt,
                "response": response_value,
                "score": score_value,
            }
        )

    def _get_model_results(provider_name: str) -> pd.DataFrame:
        model_df = router_dataset[provider_name]
        return model_df[[prompt_column, response_column, score_column]].rename(
            columns={
                prompt_column: "prompt",
                response_column: "response",
                score_column: "score",
            }
        )

    best_provider = max(
        router_dataset,
        key=lambda model: router_dataset[model][score_column].mean(),
    )
    model_results = _get_model_results(best_provider)
    not_diamond_results = pd.DataFrame(routed_rows)

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


def _model_name(model: weave.Model | str) -> str:
    if isinstance(model, weave.Model):
        return model.name or f"model-{_placeholder_model_name()}"
    return model


def _llm_provider_from_model_name(model: str) -> dict[str, Any]:
    if "/" in model:
        provider, model_name = model.split("/", 1)
    else:
        provider, model_name = "custom", model
    return {
        "provider": provider,
        "model": model_name,
        "is_custom": provider == "custom",
        "context_length": None,
        "input_price": None,
        "output_price": None,
        "latency": None,
    }


def _build_training_dataframe(
    router_dataset: dict[str, pd.DataFrame],
    prompt_column: str,
    response_column: str,
    score_column: str,
) -> pd.DataFrame:
    first_model_df = first(router_dataset.values()).reset_index(drop=True)
    training_df = pd.DataFrame({prompt_column: first_model_df[prompt_column]})
    for model, source_model_df in router_dataset.items():
        model_df = source_model_df.reset_index(drop=True)
        training_df[f"{model}/response"] = model_df[response_column]
        training_df[f"{model}/score"] = model_df[score_column]
    return training_df


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
            row_col = col
            row_value = val
            if col == "scores":
                row_col, row_value = _get_score_column(
                    model, val, score_col_name=score_col_name
                )
                score_col_name = score_col_name or row_col
            df_row[row_col] = row_value
        df_rows.append(df_row)

    if score_col_name is None:
        raise ValueError(f"No score column found for {model}. Is this correct?")

    return score_col_name, pd.DataFrame(df_rows)


def _placeholder_model_name() -> str:
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
