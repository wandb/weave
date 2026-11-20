# Bayes@N for repeated binary scores

`weave.BayesAtNScorer` wraps a binary scorer and reports a posterior mean and posterior standard deviation over a fixed set of questions. It uses a uniform Beta(1, 1) prior for each question. Both outputs are in correctness-probability units.

Give each generated completion an explicit question ID and trial ID. Declare the complete lists of expected IDs when constructing the scorer, then run `Evaluation(trials=1)` over those expanded rows:

```python
import weave

@weave.op
def correct(output: str, target: str) -> bool:
    return output == target

scorer = weave.BayesAtNScorer(
    scorer=correct,
    question_ids=["q0", "q1"],
    trial_ids=[0, 1],
)
rows = [
    {"question_id": q, "trial_id": t, "scorer_inputs": {"target": "yes"}}
    for q in ["q0", "q1"]
    for t in [0, 1]
]
evaluation = weave.Evaluation(dataset=rows, scorers=[scorer], trials=1)
summary = await evaluation.evaluate(model)
moments = summary["BayesAtNScorer"]
```

The [complete local example](example.py) defines `model` and needs no provider account. Run it from the repository root with `uv run python examples/bayes_at_n/example.py`. It produces:

```python
{"posterior_mean": 0.5, "posterior_sd": 0.13693063937629152}
```

Each expected question/trial pair must occur exactly once. Missing grades, failed model calls, entirely absent questions, unknown IDs, and duplicate pairs make the summary raise `ValueError`. String and integer IDs retain their types: `1` and `"1"` are different IDs. Boolean and fractional IDs are rejected. Use the same question and grading rule across trials, with comparable independent generations. The scorer checks the declared data layout; it cannot establish statistical independence from completion text.

Weave rejects an empty dataset list at construction. An evaluation with no scheduled rows, such as `trials=0`, skips all scorer summaries and returns `{}`, so it produces no Bayes@N result. Calling `scorer.summarize([])` directly raises `ValueError`. A result without these posterior fields is not a completed Bayes@N estimate.

Each row supplies `scorer_inputs`, the dictionary passed to the wrapped scorer as its example. This keeps its own `column_map`, reserved input names, and sync/async behavior intact. Use this wrapper's normal `column_map` to rename the `question_id`, `trial_id`, or `scorer_inputs` columns. A wrapped scorer can return a bool or integer `0`/`1`. If it returns a dictionary, set `score_key="passed"` to select that binary field. Float rewards, partial credit, and missing fields are errors. A wrapped scorer's column mappings refer to fields inside `scorer_inputs`; the wrapper's mappings refer to columns on the outer dataset row.

Automatic `Evaluation(trials=N)` for `N > 1` repeats the dataset's trial IDs, so it is unsupported here. Keep `trials=1` and expand the trial rows explicitly. This also gives saved score payloads enough information to reject a duplicate trial replacing a missing one. Reusing the same scorer for a new evaluation does not reuse observations from earlier runs.

For `M` questions and `N` trials, let `s_i` be the number of correct outcomes for question `i`. The summary computes:

```text
a_i = s_i + 1; b_i = N - s_i + 1; T = N + 2
posterior_mean = mean(a_i / T)
posterior_sd = sqrt(sum(a_i * b_i / (T*T*(T+1)))) / M
```

These are exact moments of the average latent correctness probability, conditional on the declared questions. The standard deviation describes that posterior. The existing `stderr` function measures a different quantity. Prior observations, multi-category rubrics, adaptive sampling, and credible intervals are outside this scorer's supported scope. Reloading a wrapped class scorer requires that its class be registered with Weave; wrapped op scorers use the normal op-reference path.

Method: [Don't Pass@k: A Bayesian Framework for Large Language Model Evaluation](https://arxiv.org/abs/2510.04265v4). The [Scorio reference](https://github.com/mohsenhariri/scorio/blob/7278f677c30396d99a0454bcbb08f5a9a53c4efb/scorio/eval/bayes.py) also supports categorical rewards and aligned prior observations.
