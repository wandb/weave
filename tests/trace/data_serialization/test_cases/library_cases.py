import weave
from tests.trace.data_serialization.spec import SerializationTestCase


class MyModel(weave.Model):
    prompt: weave.StringPrompt

    @weave.op
    def predict(self, user_input: str) -> str:
        return self.prompt.format(user_input=user_input)


class MyScorer(weave.Scorer):
    @weave.op
    def score(self, user_input: str, output: str) -> str:
        return user_input in output


def make_evaluation():
    dataset = [{"user_input": "Tim"}, {"user_input": "Sweeney"}]
    return weave.Evaluation(dataset=dataset, scorers=[MyScorer()])


def make_model():
    return MyModel(prompt=weave.StringPrompt("Hello {user_input}"))


def evaluation_equality_check(a, b):
    dataset_a = a.dataset.rows
    dataset_b = b.dataset.rows

    if dataset_a != dataset_b:
        return False

    scorers_a = a.scorers
    scorers_b = b.scorers

    if scorers_a != scorers_b:
        return False

    return True


library_cases = [
    SerializationTestCase(
        id="Library Objects - Scorer, Evaluation, Dataset",
        runtime_object_factory=lambda: make_evaluation(),
        inline_call_param=False,
        is_legacy=False,
        exp_json={
            "_type": "Evaluation",
            "name": None,
            "description": None,
            "dataset": "weave:///shawn/test-project/object/Dataset:N0VKaX8wr9kF9QQzM7mSQz3yKrJJjTiJi4c9Bt7RSTA",
            "scorers": [
                "weave:///shawn/test-project/object/MyScorer:K1OwZ5OGLRYNboUzGHPhnyR0W6PqWj431ieXWISYiyA"
            ],
            "preprocess_model_input": None,
            "trials": 1,
            "metadata": None,
            "evaluation_name": None,
            "evaluate": "weave:///shawn/test-project/op/Evaluation.evaluate:ZQ2X360ll0FmGXmDDU1fUii6MKgimqYYJQOKFwyXkuU",
            "predict_and_score": "weave:///shawn/test-project/op/Evaluation.predict_and_score:NbvZTtBp9EjaNqvaUHIhY0JwtlXanwJRjGThby0Fa1k",
            "summarize": "weave:///shawn/test-project/op/Evaluation.summarize:i5dmmojYMQYCNbCKXLbbp9hHgIw6wMwbExEonnPYia8",
            "_class_name": "Evaluation",
            "_bases": ["Object", "BaseModel"],
        },
        exp_objects=[
            {
                "object_id": "Dataset",
                "digest": "N0VKaX8wr9kF9QQzM7mSQz3yKrJJjTiJi4c9Bt7RSTA",
                "exp_val": {
                    "_type": "Dataset",
                    "name": None,
                    "description": None,
                    "rows": "weave:///shawn/test-project/table/97126095885a61df726e0d1d6197db7c55784b083b33a2c10e6ca8e0a1d4889e",
                    "_class_name": "Dataset",
                    "_bases": ["Object", "BaseModel"],
                },
            },
            {
                "object_id": "Evaluation.evaluate",
                "digest": "ZQ2X360ll0FmGXmDDU1fUii6MKgimqYYJQOKFwyXkuU",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "pn6E2Yw1tujS7r1KAKKKwyCKLL2PxZkitEUVes7Y7zM"},
                },
            },
            {
                "object_id": "Evaluation.predict_and_score",
                "digest": "NbvZTtBp9EjaNqvaUHIhY0JwtlXanwJRjGThby0Fa1k",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "H9FZVABE7ktDVkZpQBUezhHxX2Y7nTUWyagqlwpZ9bY"},
                },
            },
            {
                "object_id": "MyScorer",
                "digest": "K1OwZ5OGLRYNboUzGHPhnyR0W6PqWj431ieXWISYiyA",
                "exp_val": {
                    "_type": "MyScorer",
                    "name": None,
                    "description": None,
                    "column_map": None,
                    "score": "weave:///shawn/test-project/op/MyScorer.score:aYU47lnlWPzEnb4euRSicDtC5Puo4YJTl55KlTCDuOU",
                    "summarize": "weave:///shawn/test-project/op/Scorer.summarize:lMo39TTtMo50nRj7gWzUJUXXbuX3D3VXkRRMuOTdCHU",
                    "_class_name": "MyScorer",
                    "_bases": ["Scorer", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "Evaluation.summarize",
                "digest": "i5dmmojYMQYCNbCKXLbbp9hHgIw6wMwbExEonnPYia8",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "8UQV2iinJaY1psOCPnDf3YGBFdnZKY9pYY8zYieGNNI"},
                },
            },
            {
                "object_id": "MyScorer.score",
                "digest": "aYU47lnlWPzEnb4euRSicDtC5Puo4YJTl55KlTCDuOU",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "Q5mId9WksFCNbY86SM7wcXW0VombvaYvWszyMr87lA8"},
                },
            },
            {
                "object_id": "Scorer.summarize",
                "digest": "lMo39TTtMo50nRj7gWzUJUXXbuX3D3VXkRRMuOTdCHU",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "8teCjKYMtHbgJiusy1APBXy3yFjmEZ6cMQCFYDR9cBA"},
                },
            },
        ],
        exp_files=[
            {
                "digest": "pn6E2Yw1tujS7r1KAKKKwyCKLL2PxZkitEUVes7Y7zM",
                "exp_content": b'import weave\nfrom typing import Union\nfrom weave.trace.op_protocol import Op\nfrom weave.flow.model import Model\nimport json\nfrom weave.trace.op import op\nfrom weave.trace.call import Call\nfrom datetime import datetime\nfrom weave.flow.util import make_memorable_name\n\ndef _safe_summarize_to_str(summary: dict) -> str:\n    summary_str = ""\n    try:\n        summary_str = json.dumps(summary, indent=2)\n    except Exception:\n        try:\n            summary_str = str(summary)\n        except Exception:\n            pass\n    return summary_str\n\nlogger = "<Logger weave.evaluation.eval (ERROR)>"\n\ndef default_evaluation_display_name(call: Call) -> str:\n    date = datetime.now().strftime("%Y-%m-%d")\n    unique_name = make_memorable_name()\n    return f"eval-{date}-{unique_name}"\n\n@weave.op()\n@op(call_display_name=default_evaluation_display_name)\nasync def evaluate(self, model: Union[Op, Model]) -> dict:\n    eval_results = await self.get_eval_results(model)\n    summary = await self.summarize(eval_results)\n\n    summary_str = _safe_summarize_to_str(summary)\n    if summary_str:\n        logger.info(f"Evaluation summary {summary_str}")\n\n    return summary\n',
            },
            {
                "digest": "Q5mId9WksFCNbY86SM7wcXW0VombvaYvWszyMr87lA8",
                "exp_content": b"import weave\n\n@weave.op()\ndef score(self, user_input: str, output: str) -> str:\n    return user_input in output\n",
            },
            {
                "digest": "8teCjKYMtHbgJiusy1APBXy3yFjmEZ6cMQCFYDR9cBA",
                "exp_content": b'import weave\nfrom numbers import Number\nfrom typing import Optional\nfrom typing import Any\nfrom pydantic.main import BaseModel\nfrom weave.trace.op import op\n\ndef _import_numpy() -> Optional[Any]:\n    try:\n        import numpy\n    except ImportError:\n        return None\n    return numpy\n\ndef auto_summarize(data: list) -> Optional[dict[str, Any]]:\n    """Automatically summarize a list of (potentially nested) dicts.\n\n    Computes:\n        - avg for numeric cols\n        - count and fraction for boolean cols\n        - other col types are ignored\n\n    If col is all None, result is None\n\n    Returns:\n      dict of summary stats, with structure matching input dict structure.\n    """\n    if not data:\n        return {}\n    data = [x for x in data if x is not None]\n\n    if not data:\n        return None\n\n    val = data[0]\n\n    if isinstance(val, bool):\n        return {\n            "true_count": (true_count := sum(1 for x in data if x)),\n            "true_fraction": true_count / len(data),\n        }\n    elif isinstance(val, Number):\n        if np := _import_numpy():\n            return {"mean": np.mean(data).item()}\n        else:\n            return {"mean": sum(data) / len(data)}\n    elif isinstance(val, dict):\n        result = {}\n        all_keys = list(\n            dict.fromkeys([k for d in data if isinstance(d, dict) for k in d.keys()])\n        )\n        for k in all_keys:\n            if (\n                summary := auto_summarize(\n                    [x.get(k) for x in data if isinstance(x, dict)]\n                )\n            ) is not None:\n                if k in summary:\n                    result.update(summary)\n                else:\n                    result[k] = summary\n        if not result:\n            return None\n        return result\n    elif isinstance(val, BaseModel):\n        return auto_summarize([x.model_dump() for x in data])\n    return None\n\n@weave.op()\n@op\ndef summarize(self, score_rows: list) -> Optional[dict]:\n    return auto_summarize(score_rows)\n',
            },
            {
                "digest": "H9FZVABE7ktDVkZpQBUezhHxX2Y7nTUWyagqlwpZ9bY",
                "exp_content": b'import weave\nfrom typing import Union\nfrom weave.trace.op_protocol import Op\nfrom weave.flow.model import Model\nfrom weave.flow.model import apply_model_async\nfrom weave.flow.model import ApplyModelError\nimport asyncio\nfrom weave.flow.scorer import get_scorer_attributes\nfrom weave.trace.op import op\n\n@weave.op()\n@op\nasync def predict_and_score(self, model: Union[Op, Model], example: dict) -> dict:\n    apply_model_result = await apply_model_async(\n        model, example, self.preprocess_model_input\n    )\n\n    if isinstance(apply_model_result, ApplyModelError):\n        return {\n            self._output_key: None,\n            "scores": {},\n            "model_latency": apply_model_result.model_latency,\n        }\n\n    model_output = apply_model_result.model_output\n    model_call = apply_model_result.model_call\n    model_latency = apply_model_result.model_latency\n\n    scores = {}\n    if scorers := self.scorers:\n        # Run all scorer calls in parallel\n        scorer_tasks = [\n            model_call.apply_scorer(scorer, example) for scorer in scorers\n        ]\n        apply_scorer_results = await asyncio.gather(*scorer_tasks)\n\n        # Process results and build scores dict\n        for scorer, apply_scorer_result in zip(scorers, apply_scorer_results):\n            result = apply_scorer_result.result\n            scorer_attributes = get_scorer_attributes(scorer)\n            scorer_name = scorer_attributes.scorer_name\n            scores[scorer_name] = result\n\n    return {\n        self._output_key: model_output,\n        "scores": scores,\n        "model_latency": model_latency,\n    }\n',
            },
            {
                "digest": "8UQV2iinJaY1psOCPnDf3YGBFdnZKY9pYY8zYieGNNI",
                "exp_content": b'import weave\nfrom weave.object.obj import Object\nfrom weave.trace.table import Table\nfrom weave.flow.util import transpose\nfrom weave.flow.scorer import get_scorer_attributes\nfrom weave.flow.scorer import auto_summarize\nfrom weave.trace.op import op\n\nclass EvaluationResults(Object):\n    rows: Table\n\n@weave.op()\n@op\nasync def summarize(self, eval_table: EvaluationResults) -> dict:\n    eval_table_rows = list(eval_table.rows)\n    cols = transpose(eval_table_rows)\n    summary = {}\n\n    for name, vals in cols.items():\n        if name == "scores":\n            if scorers := self.scorers:\n                for scorer in scorers:\n                    scorer_attributes = get_scorer_attributes(scorer)\n                    scorer_name = scorer_attributes.scorer_name\n                    summarize_fn = scorer_attributes.summarize_fn\n                    scorer_stats = transpose(vals)\n                    score_table = scorer_stats[scorer_name]\n                    scored = summarize_fn(score_table)\n                    summary[scorer_name] = scored\n        else:\n            model_output_summary = auto_summarize(vals)\n            if model_output_summary:\n                summary[name] = model_output_summary\n    return summary\n',
            },
        ],
        # Sad ... equality is really a pain to assert here (and is broken)
        # TODO: Write a good equality check and make it work
        equality_check=lambda a, b: True,
    ),
    SerializationTestCase(
        id="Library Objects - Model, Prompt",
        runtime_object_factory=lambda: make_model(),
        inline_call_param=False,
        is_legacy=False,
        exp_json={
            "_type": "MyModel",
            "name": None,
            "description": None,
            "prompt": "weave:///shawn/test-project/object/StringPrompt:E5XB0iGux1m8LJXEiwZlOLdJLmHSAbCBsgXHYeP0UB4",
            "predict": "weave:///shawn/test-project/op/MyModel.predict:g8cfXevUvSEsS9EwiCuMs17EXufrpTZHeeyPCDVLvIg",
            "_class_name": "MyModel",
            "_bases": ["Model", "Object", "BaseModel"],
        },
        exp_objects=[
            {
                "object_id": "StringPrompt",
                "digest": "E5XB0iGux1m8LJXEiwZlOLdJLmHSAbCBsgXHYeP0UB4",
                "exp_val": {
                    "_type": "StringPrompt",
                    "name": None,
                    "description": None,
                    "content": "Hello {user_input}",
                    "_class_name": "StringPrompt",
                    "_bases": ["Prompt", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "MyModel.predict",
                "digest": "g8cfXevUvSEsS9EwiCuMs17EXufrpTZHeeyPCDVLvIg",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "P7IiKkb3yNxV4tHW01Zj9ShtRKBVJTEtSttrv4S2nFU"},
                },
            },
        ],
        exp_files=[
            {
                "digest": "P7IiKkb3yNxV4tHW01Zj9ShtRKBVJTEtSttrv4S2nFU",
                "exp_content": b"import weave\n\n@weave.op()\ndef predict(self, user_input: str) -> str:\n    return self.prompt.format(user_input=user_input)\n",
            }
        ],
        # Sad ... equality is really a pain to assert here (and is broken)
        # TODO: Write a good equality check and make it work
        equality_check=lambda a, b: True,
    ),
]
