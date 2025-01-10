import pandas as pd

import weave
from weave.flow.eval import EvaluationResults


def get_model_evals(
    file_path: str = "integrations/notdiamond/test_data/humaneval.csv",
) -> dict[str, EvaluationResults]:
    df = pd.read_csv(file_path)
    models = [
        "anthropic/claude-3-5-sonnet-20240620",
        "openai/gpt-4o-2024-05-13",
        "google/gemini-1.5-pro-latest",
        "openai/gpt-4-turbo-2024-04-09",
        "anthropic/claude-3-opus-20240229",
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
