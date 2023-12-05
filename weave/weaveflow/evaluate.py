import typing

import weave

from .dataset import Dataset
from .structured_output import StructuredOutputChatModel


@weave.type()
class Evaluate:
    @weave.op()
    def compute(self, dataset: Dataset, predictions: list[typing.Any]) -> typing.Any:
        ...


@weave.type()
class EvaluateExactMatch(Evaluate):
    format_example: typing.Callable[[typing.Any], typing.Any]

    @weave.op()
    def compute(self, dataset: Dataset, predictions: list[typing.Any]) -> typing.Any:
        match = [p == self.format_example(r) for p, r in zip(predictions, dataset.rows)]
        return {
            "columns": {"match": match},
            "summary": {"match_frac": sum(match) / len(match)},
        }


@weave.type()
class EvaluateLLM(Evaluate):
    chat_llm: StructuredOutputChatModel
    messages_template: typing.Callable[[typing.Any, typing.Any], typing.Any]

    @weave.op()
    def compute(self, dataset: Dataset, predictions: list[typing.Any]) -> typing.Any:
        result_type = weave.types.TypedDict(
            {
                "score": weave.types.Float(),
                "rationale": weave.types.String(),
            }
        )
        # TODO: get rid of this const() wrap... why do I need it?
        from .. import weave_internal

        all_messages = dataset.rows.apply(
            lambda r, i: self.messages_template(r, weave_internal.const(predictions)[i])
        )
        results = all_messages.apply(lambda m: self.chat_llm.complete(m, result_type))

        scores = results.column("score")
        rationales = results.column("rationale")

        non_none_scores = [s for s in scores if s is not None]
        score_avg = 0
        if len(non_none_scores) > 0:
            score_avg = sum(non_none_scores) / len(non_none_scores)
        return {
            "columns": {"score": scores, "rationale": rationales},
            "summary": {"score_avg": score_avg},
        }


@weave.type()
class EvaluateMulti(Evaluate):
    evaluations: dict[str, Evaluate]

    @weave.op()
    def compute(self, dataset: Dataset, predictions: list[typing.Any]) -> typing.Any:
        columns = {}
        summary = {}
        for k, eval in self.evaluations.items():
            eval_result = eval.compute(dataset, predictions)
            columns[k] = eval_result["columns"]
            summary[k] = eval_result["summary"]
        return {
            "columns": columns,
            "summary": summary,
        }


@weave.type()
class EvaluateNamedSteps(Evaluate):
    step_keys: list[str]
    evaluation: Evaluate

    @weave.op()
    def compute(self, dataset: typing.Any, predictions: list[typing.Any]) -> typing.Any:
        # This handles nested columns by recursively computing column deltas.
        # TODO: This would be nicer with column traversal / leaf-mapping.
        def compute_delta(
            cur: dict, prior: dict, delta_columns: dict, delta_summary: dict
        ) -> None:
            for k, v in cur.items():
                if isinstance(v, dict):
                    delta_columns[k] = {}
                    delta_summary[k] = {}
                    compute_delta(
                        v, prior.get(k, {}), delta_columns[k], delta_summary[k]
                    )
                else:
                    try:
                        float_delta = [
                            float(v[i]) - float(prior[k][i]) for i in range(len(v))
                        ]
                        delta_columns[k] = float_delta
                        delta_summary[k] = sum(float_delta) / len(float_delta)
                    except (ValueError, TypeError, KeyError):
                        continue

        columns = {}
        summary = {}
        for i, step_key in enumerate(self.step_keys):
            eval_result = self.evaluation.compute(
                dataset, [p[step_key] for p in predictions]
            )
            columns[step_key] = eval_result["columns"]
            summary[step_key] = eval_result["summary"]
            if i != 0:
                prior_columns = columns[self.step_keys[i - 1]]
                cur_columns = columns[step_key]
                delta_columns: dict = {}
                delta_summary: dict = {}
                compute_delta(cur_columns, prior_columns, delta_columns, delta_summary)
                columns[f"{step_key}_delta"] = delta_columns
                summary[f"{step_key}_delta_avg"] = delta_summary

        return {
            "columns": columns,
            "summary": summary,
        }
