import asyncio
import json
import logging
import traceback
from collections.abc import Callable
from datetime import datetime
from itertools import chain, repeat
from typing import Any, Literal

from pydantic import PrivateAttr
from typing_extensions import Self

from weave.dataset.dataset import Dataset
from weave.flow import util
from weave.flow.casting import DatasetLike, ScorerLike
from weave.flow.model import (
    ApplyModelError,
    Model,
    PreprocessModelInput,
    apply_model_async,
)
from weave.flow.scorer import (
    Scorer,
    _has_oldstyle_scorers,
    auto_summarize,
    get_scorer_attributes,
)
from weave.flow.util import make_memorable_name, transpose
from weave.object.obj import Object
from weave.trace.call import Call, CallsIter
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.env import get_weave_parallelism
from weave.trace.objectify import maybe_objectify, register_object
from weave.trace.op import OpCallError, as_op, is_op, op
from weave.trace.op_protocol import CallDisplayNameFunc, Op
from weave.trace.refs import ObjectRef
from weave.trace.table import Table
from weave.trace.vals import WeaveObject
from weave.trace.weave_client import get_ref
from weave.trace_server.trace_server_interface import CallsFilter
from weave.utils.project_id import from_project_id

logger = logging.getLogger(__name__)

INVALID_MODEL_ERROR = (
    "`Evaluation.evaluate` requires a `Model` or `Op` instance as the `model` argument. "
    + "If you are using a function, wrap it with `weave.op` to create an `Op` instance."
)


def default_evaluation_display_name(call: Call) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    unique_name = make_memorable_name()
    return f"eval-{date}-{unique_name}"


class EvaluationResults(Object):
    rows: Table


@register_object
class Evaluation(Object):
    """Sets up an evaluation which includes a set of scorers and a dataset.

    Calling evaluation.evaluate(model) will pass in rows from a dataset into a model matching
        the names of the columns of the dataset to the argument names in model.predict.

    Then it will call all of the scorers and save the results in weave.

    If you want to preprocess the rows from the dataset you can pass in a function
    to preprocess_model_input.

    Examples:
    ```python
    # Collect your examples
    examples = [
        {"question": "What is the capital of France?", "expected": "Paris"},
        {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
        {"question": "What is the square root of 64?", "expected": "8"},
    ]

    # Define any custom scoring function
    @weave.op
    def match_score1(expected: str, model_output: dict) -> dict:
        # Here is where you'd define the logic to score the model output
        return {'match': expected == model_output['generated_text']}

    @weave.op
    def function_to_evaluate(question: str):
        # here's where you would add your LLM call and return the output
        return  {'generated_text': 'Paris'}

    # Score your examples using scoring functions
    evaluation = Evaluation(
        dataset=examples, scorers=[match_score1]
    )

    # Start tracking the evaluation
    weave.init('intro-example')
    # Run the evaluation
    asyncio.run(evaluation.evaluate(function_to_evaluate))
    ```
    """

    dataset: DatasetLike
    scorers: list[ScorerLike] | None = None
    preprocess_model_input: PreprocessModelInput | None = None
    trials: int = 1

    metadata: dict[str, Any] | None = None

    # Custom evaluation name for display in the UI.  This is the same API as passing a
    # custom `call_display_name` to `weave.op` (see that for more details).
    evaluation_name: str | CallDisplayNameFunc | None = None

    # internal attr to track whether to use the new `output` or old `model_output` key for outputs
    _output_key: Literal["output", "model_output"] = PrivateAttr("output")

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        field_values = {}
        for field_name in cls.model_fields:
            if hasattr(obj, field_name):
                field_values[field_name] = getattr(obj, field_name)

        # Start mega-hack
        # This is a very bad hack. Our deserialization/portability logic
        # is totally broken. It will require a complete re-write of our
        # deserialization layer to fix. The specific issue is that our
        # deserialization code does not recursively deserialize custom objects
        # (in this case scorers) and therefore needs to be done manually.
        # In the meantime, this is such a common pattern, that I am going to
        # fix it here. If you are a future dev and you actually fix the
        # serialization stuff, that may or may not break this. That is OK!
        # please feel free to remove this as we have tests that validate the
        # end-user experience.
        if orig_scorers := field_values.get("scorers"):
            from weave import scorers as weave_scorers

            assert weave_scorers
            scorers = []
            for scorer in orig_scorers:
                if isinstance(scorer, WeaveObject):
                    scorer = maybe_objectify(scorer)
                scorers.append(scorer)
            field_values["scorers"] = scorers
        # End mega-hack

        if not field_values.get("ref"):
            entity, project = from_project_id(obj.project_id)
            field_values["ref"] = ObjectRef(
                entity=entity,
                project=project,
                name=obj.object_id,
                _digest=obj.digest,
            )

        return cls(**field_values)

    def model_post_init(self, __context: Any) -> None:
        # Determine output key based on scorer types
        scorers = self.scorers or []
        if _has_oldstyle_scorers(scorers):
            self._output_key = "model_output"
            util.warn_once(
                logger,
                "Using 'model_output' key for compatibility with older scorers. Please update scorers to use 'output' parameter.",
            )

        if self.evaluation_name:
            eval_op = as_op(self.evaluate)
            eval_op.call_display_name = self.evaluation_name

        if self.name is None and self.dataset.name is not None:
            self.name = self.dataset.name + "-evaluation"  # type: ignore

    @op
    async def predict_and_score(self, model: Op | Model, example: dict) -> dict:
        apply_model_result = await apply_model_async(
            model, example, self.preprocess_model_input
        )

        if isinstance(apply_model_result, ApplyModelError):
            return {
                self._output_key: None,
                "scores": {},
                "model_latency": apply_model_result.model_latency,
            }

        model_output = apply_model_result.model_output
        model_call = apply_model_result.model_call
        model_latency = apply_model_result.model_latency

        scores = {}
        if scorers := self.scorers:
            # Run all scorer calls in parallel
            scorer_tasks = [
                model_call.apply_scorer(scorer, example) for scorer in scorers
            ]
            apply_scorer_results = await asyncio.gather(*scorer_tasks)

            # Process results and build scores dict
            for scorer, apply_scorer_result in zip(
                scorers, apply_scorer_results, strict=False
            ):
                result = apply_scorer_result.result
                scorer_attributes = get_scorer_attributes(scorer)
                scorer_name = scorer_attributes.scorer_name
                scores[scorer_name] = result

        return {
            self._output_key: model_output,
            "scores": scores,
            "model_latency": model_latency,
        }

    @op
    async def summarize(self, eval_table: EvaluationResults) -> dict:
        eval_table_rows = list(eval_table.rows)
        cols = transpose(eval_table_rows)
        summary = {}

        for name, vals in cols.items():
            if name == "scores":
                if scorers := self.scorers:
                    for scorer in scorers:
                        scorer_attributes = get_scorer_attributes(scorer)
                        scorer_name = scorer_attributes.scorer_name
                        summarize_fn = scorer_attributes.summarize_fn
                        scorer_stats = transpose(vals)
                        score_table = scorer_stats[scorer_name]
                        scored = summarize_fn(score_table)
                        summary[scorer_name] = scored
            else:
                model_output_summary = auto_summarize(vals)
                if model_output_summary:
                    summary[name] = model_output_summary
        return summary

    async def get_eval_results(self, model: Op | Model) -> EvaluationResults:
        if not is_valid_model(model):
            raise ValueError(INVALID_MODEL_ERROR)
        eval_rows: list[tuple[int, dict]] = []

        async def eval_example(example: dict) -> dict:
            try:
                eval_row = await self.predict_and_score(model, example)
            except OpCallError as e:
                raise e
            except Exception:
                logger.info("Predict and score failed")
                traceback.print_exc()
                return {self._output_key: None, "scores": {}}
            return eval_row

        n_complete = 0
        dataset = self.dataset
        rows = dataset.rows
        num_rows = len(rows) * self.trials

        trial_rows = chain.from_iterable(repeat(rows, self.trials))
        async for index, _example, eval_row in util.async_foreach(
            trial_rows, eval_example, get_weave_parallelism()
        ):
            n_complete += 1
            logger.info(f"Evaluated {n_complete} of {num_rows} examples")
            if eval_row is None:
                eval_row = {self._output_key: None, "scores": {}}
            else:
                eval_row["scores"] = eval_row.get("scores", {})
            if self.scorers:
                for scorer in self.scorers:
                    scorer_attributes = get_scorer_attributes(scorer)
                    scorer_name = scorer_attributes.scorer_name
                    if scorer_name not in eval_row["scores"]:
                        eval_row["scores"][scorer_name] = {}
            eval_rows.append((index, eval_row))
        eval_rows.sort(key=lambda x: x[0])
        table_rows = [eval_row for _, eval_row in eval_rows]
        return EvaluationResults(rows=Table(table_rows))

    @op(call_display_name=default_evaluation_display_name)
    async def evaluate(self, model: Op | Model) -> dict:
        eval_results = await self.get_eval_results(model)
        summary = await self.summarize(eval_results)

        summary_str = _safe_summarize_to_str(summary)
        if summary_str:
            logger.info(f"Evaluation summary {summary_str}")

        return summary

    def get_evaluate_calls(self) -> CallsIter:
        """Retrieve all evaluation calls that used this Evaluation object.

        Note that this returns a CallsIter instead of a single call because it's
        possible to have multiple evaluation calls for a single evaluation (e.g.
        if you run the same evaluation multiple times).

        Returns:
            CallsIter: An iterator over Call objects representing evaluation runs.

        Raises:
            ValueError: If the evaluation has no ref (hasn't been saved/run yet).

        Examples:
            ```python
            evaluation = Evaluation(dataset=examples, scorers=[scorer])
            await evaluation.evaluate(model)  # Run evaluation first
            calls = evaluation.get_evaluate_calls()
            for call in calls:
                print(f"Evaluation run: {call.id} at {call.started_at}")
            ```
        """
        client = require_weave_client()

        if not self.ref:
            raise ValueError("Evaluation has no ref, please run the evaluation first!")

        evaluate_op_name = "Evaluation.evaluate"
        eval_op_ref = f"weave:///{client._project_id()}/op/{evaluate_op_name}:*"
        return client.get_calls(
            filter=CallsFilter(
                input_refs=[self.ref.uri()],
                op_names=[eval_op_ref],
            ),
        )

    def get_score_calls(self) -> dict[str, list[Call]]:
        """Retrieve scorer calls for each evaluation run, grouped by trace ID.

        Returns:
            dict[str, list[Call]]: A dictionary mapping trace IDs to lists of scorer Call objects.
                Each trace ID represents one evaluation run, and the list contains all scorer
                calls executed during that run.

        Examples:
            ```python
            evaluation = Evaluation(dataset=examples, scorers=[accuracy_scorer, f1_scorer])
            await evaluation.evaluate(model)
            score_calls = evaluation.get_score_calls()
            for trace_id, calls in score_calls.items():
                print(f"Trace {trace_id}: {len(calls)} scorer calls")
                for call in calls:
                    scorer_name = call.summary.get("weave", {}).get("trace_name")
                    print(f"  Scorer: {scorer_name}, Output: {call.output}")
            ```
        """
        d = {}
        client = require_weave_client()
        for evaluate_call in self.get_evaluate_calls():
            descendents = list(
                client.get_calls(filter={"trace_ids": [evaluate_call.trace_id]})
            )
            summary_call = list(descendents)[-1]
            scorer_names = {
                k for k in summary_call.output if k not in ["output", "model_latency"]
            }
            score_calls = [
                call
                for call in descendents
                if call.summary.get("weave", {}).get("trace_name") in scorer_names
            ]
            d[evaluate_call.trace_id] = score_calls

        return d

    def get_scores(self) -> dict[str, dict[str, list[Any]]]:
        """Extract and organize scorer outputs from evaluation runs.

        Returns:
            dict[str, dict[str, list[Any]]]: A nested dictionary structure where:
                - First level keys are trace IDs (evaluation runs)
                - Second level keys are scorer names
                - Values are lists of scorer outputs for that run and scorer

        Examples:
            ```python
            evaluation = Evaluation(dataset=examples, scorers=[accuracy_scorer, f1_scorer])
            await evaluation.evaluate(model)
            scores = evaluation.get_scores()
            # Access scores by trace and scorer
            for trace_id, trace_scores in scores.items():
                    print(f"Evaluation run {trace_id}:")
                    for scorer_name, outputs in trace_scores.items():
                        print(f"  {scorer_name}: {outputs}")
            ```

            Expected output:

            ```
            {
                "trace_123": {
                "accuracy_scorer": [{"accuracy": 0.85}],
                "f1_scorer": [{"f1": 0.78}]
                }
            }
            ```
        """
        score_calls = self.get_score_calls()
        d: dict[str, dict[str, list[Any]]] = {}
        for trace_id, calls in score_calls.items():
            d[trace_id] = {}
            for call in calls:
                if call.summary is None:
                    continue
                scorer_name = call.summary.get("weave", {}).get("trace_name")
                if scorer_name not in d[trace_id]:
                    d[trace_id][scorer_name] = []
                d[trace_id][scorer_name].append(call.output)
        return d


def _safe_summarize_to_str(summary: dict) -> str:
    summary_str = ""
    try:
        summary_str = json.dumps(summary, indent=2)
    except Exception:
        try:
            summary_str = str(summary)
        except Exception:
            pass
    return summary_str


def evaluate(
    dataset: Dataset | list,
    model: Op | Model,
    scorers: list[Callable | Scorer] | None = None,
    preprocess_model_input: PreprocessModelInput | None = None,
) -> dict:
    eval = Evaluation(
        dataset=dataset, scorers=scorers, preprocess_model_input=preprocess_model_input
    )
    return asyncio.run(eval.evaluate(model))


def is_valid_model(model: Any) -> bool:
    return (
        # Model instances are supported
        isinstance(model, Model)
        # Ops are supported
        or is_op(model)
        # Saved Models (Objects with predict) are supported
        or (
            get_ref(model) is not None
            and isinstance(model, WeaveObject)
            and hasattr(model, "predict")
            and is_op(model.predict)
        )
    )
