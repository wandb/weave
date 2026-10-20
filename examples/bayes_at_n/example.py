"""Run a local Bayes@N evaluation without a model provider."""

import asyncio

import weave


@weave.op
def correct(output: str, target: str) -> bool:
    return output == target


@weave.op
def model(question_id: str) -> str:
    return "yes" if question_id == "q1" else "no"


async def main() -> None:
    rows = [
        {"question_id": question, "trial_id": trial, "scorer_inputs": {"target": "yes"}}
        for question in ["q0", "q1"]
        for trial in [0, 1]
    ]
    scorer = weave.BayesAtNScorer(
        scorer=correct,
        question_ids=["q0", "q1"],
        trial_ids=[0, 1],
    )
    evaluation = weave.Evaluation(dataset=rows, scorers=[scorer], trials=1)
    summary = await evaluation.evaluate(model)
    print(summary["BayesAtNScorer"])


if __name__ == "__main__":
    asyncio.run(main())
