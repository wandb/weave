from pathlib import Path

import pandas as pd

import weave
from weave.evaluation.eval import EvaluationResults


def get_model_evals(
    file_path: str | None = None,
) -> dict[str, EvaluationResults]:
    if file_path is None:
        # Get path relative to this module file
        module_dir = (
            Path(__file__).parent.parent.parent.parent
            / "tests"
            / "integrations"
            / "notdiamond"
            / "test_data"
        )
        file_path = str(module_dir / "humaneval.csv")

    df = pd.read_csv(file_path)
    models = [
        "openai/gpt-4o",
        "google/gemini-2.5-flash",
        "openai/gpt-4-turbo",
        "anthropic/claude-sonnet-4-5",
    ]

    model_evals = {}
    for model in models:
        input_score_col = _get_score_column(model)
        input_response_col = _get_response_column(model)
        columns = ["Input", input_response_col, input_score_col]
        eval_rows = df[columns].rename(
            columns={
                "Input": "prompt",
                input_response_col: "actual",
                input_score_col: "scores",
            }
        )
        eval_rows["scores"] = eval_rows["scores"].apply(lambda x: {"correctness": x})
        eval_rows = eval_rows.to_dict(orient="records")
        model_evals[model] = EvaluationResults(rows=weave.Table(eval_rows))

    return model_evals


def _get_score_column(model: str) -> str:
    return f"{model}/final_score"


def _get_response_column(model: str) -> str:
    return f"{model}/response"
