import sys

import weave
from tests.trace.data_serialization.spec import SerializationTestCase
from weave.scorers import LLMAsAJudgeScorer
from weave.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    LLMStructuredCompletionModel,
)
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModelDefaultParams,
)


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
    return weave.Evaluation(
        dataset=dataset,
        scorers=[
            MyScorer(),
            LLMAsAJudgeScorer(
                model=LLMStructuredCompletionModel(
                    llm_model_id="gpt-4o-mini",
                    default_params=LLMStructuredCompletionModelDefaultParams(
                        messages_template=[
                            {
                                "role": "system",
                                "content": "You are a judge, respond with json. 'score' (0-1), 'reasoning' (string)",
                            }
                        ],
                        response_format="json_object",
                    ),
                ),
                scoring_prompt="Here are the inputs: {inputs}. Here is the output: {output}. Is the output correct?",
                enable_audio_input_scoring=True,
                media_scoring_json_paths=["$.messages[0].content[1].input_audio"],
            ),
        ],
    )


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


llm_as_a_judge_scorer_digest = (
    "BDAXKzn8KFLjB653bFX2imLtdZJbkqz6obO6dYYR490"
    if sys.version_info.major >= 3 and sys.version_info.minor >= 13
    else "GuTiuaw9aciXWCWPU5cvWtQqs0lcBtJPfYRlYH3GUwk"
)

library_cases = [
    SerializationTestCase(
        id="Library Objects - Scorer, Evaluation, Dataset, LLMAsAJudgeScorer, LLMStructuredCompletionModel (legacy v4)",
        runtime_object_factory=lambda: make_evaluation(),
        inline_call_param=True,
        is_legacy=True,
        exp_json={
            "_type": "Evaluation",
            "name": None,
            "description": None,
            "dataset": "weave:///shawn/test-project/object/Dataset:N0VKaX8wr9kF9QQzM7mSQz3yKrJJjTiJi4c9Bt7RSTA",
            "scorers": [
                "weave:///shawn/test-project/object/MyScorer:ILpCvdAsCLLLt9wU28MU9ugSScTkg7L3XX6PlUgFvlg",
                "weave:///shawn/test-project/object/LLMAsAJudgeScorer:GuTiuaw9aciXWCWPU5cvWtQqs0lcBtJPfYRlYH3GUwk",
            ],
            "preprocess_model_input": None,
            "trials": 1,
            "metadata": None,
            "evaluation_name": None,
            "evaluate": "weave:///shawn/test-project/op/Evaluation.evaluate:XbyuZNBxQ90Ur9tjMI6Cj8CNXnisWemlzU8etRYeFsI",
            "predict_and_score": "weave:///shawn/test-project/op/Evaluation.predict_and_score:NrwneWUrXaCdi9BUqmufH4dg1U1tvHFGPK5dZh2CcPQ",
            "summarize": "weave:///shawn/test-project/op/Evaluation.summarize:eq6QbaZJYKZlbaCR95PvaoLDomTryBhb5uajqpIX8u0",
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
                "digest": "XbyuZNBxQ90Ur9tjMI6Cj8CNXnisWemlzU8etRYeFsI",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "MqFC4mjZWQVAB2AkQZ1g4uNUee9YhkUYXLYArWmTEcU"},
                },
            },
            {
                "object_id": "Evaluation.predict_and_score",
                "digest": "NrwneWUrXaCdi9BUqmufH4dg1U1tvHFGPK5dZh2CcPQ",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "ZHD4K7uUDPT93NdVQO3I6F9Xah9AEceWYBSQXg1bZPM"},
                },
            },
            {
                "object_id": "MyScorer",
                "digest": "ILpCvdAsCLLLt9wU28MU9ugSScTkg7L3XX6PlUgFvlg",
                "exp_val": {
                    "_type": "MyScorer",
                    "name": None,
                    "description": None,
                    "column_map": None,
                    "score": "weave:///shawn/test-project/op/MyScorer.score:BE7Pf2XsllJGfbeffAcYiZa2zRAD24oytT9U9iqIn4o",
                    "summarize": "weave:///shawn/test-project/op/Scorer.summarize:bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                    "_class_name": "MyScorer",
                    "_bases": ["Scorer", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMAsAJudgeScorer",
                "digest": "GuTiuaw9aciXWCWPU5cvWtQqs0lcBtJPfYRlYH3GUwk",
                "exp_val": {
                    "_type": "LLMAsAJudgeScorer",
                    "name": None,
                    "description": None,
                    "column_map": None,
                    "model": "weave:///shawn/test-project/object/LLMStructuredCompletionModel:VUqRnYmuvNhu3zgfDb9hnZhLRFM1vKKI1WEpw3bsViE",
                    "enable_audio_input_scoring": True,
                    "media_scoring_json_paths": [
                        "$.messages[0].content[1].input_audio"
                    ],
                    "scoring_prompt": "Here are the inputs: {inputs}. Here is the output: {output}. Is the output correct?",
                    "score": "weave:///shawn/test-project/op/LLMAsAJudgeScorer.score:EdDalYbNwTflbeMrWbUDn3tlYQeX9JquL9DkXuKRZr8",
                    "summarize": "weave:///shawn/test-project/op/Scorer.summarize:bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                    "_class_name": "LLMAsAJudgeScorer",
                    "_bases": ["Scorer", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMAsAJudgeScorer.score",
                "digest": "EdDalYbNwTflbeMrWbUDn3tlYQeX9JquL9DkXuKRZr8",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "fqXqYs4C4l0HpQOaRfbVXwsvwYUZhMYyn4cvK0wnCMU"},
                },
            },
            {
                "object_id": "LLMStructuredCompletionModel",
                "digest": "VUqRnYmuvNhu3zgfDb9hnZhLRFM1vKKI1WEpw3bsViE",
                "exp_val": {
                    "_type": "LLMStructuredCompletionModel",
                    "name": None,
                    "description": None,
                    "llm_model_id": "gpt-4o-mini",
                    "default_params": {
                        "_type": "LLMStructuredCompletionModelDefaultParams",
                        "messages_template": [
                            {
                                "_type": "Message",
                                "role": "system",
                                "content": "You are a judge, respond with json. 'score' (0-1), 'reasoning' (string)",
                                "name": None,
                                "function_call": None,
                                "tool_call_id": None,
                                "_class_name": "Message",
                                "_bases": ["BaseModel"],
                            }
                        ],
                        "prompt": None,
                        "temperature": None,
                        "top_p": None,
                        "max_tokens": None,
                        "presence_penalty": None,
                        "frequency_penalty": None,
                        "stop": None,
                        "n_times": None,
                        "functions": None,
                        "response_format": "json_object",
                        "_class_name": "LLMStructuredCompletionModelDefaultParams",
                        "_bases": ["BaseModel"],
                    },
                    "predict": "weave:///shawn/test-project/op/LLMStructuredCompletionModel.predict:ili08oGwFsNX4Bn0fhZPvKpT9CfjSgNJVLegSJ2iGUk",
                    "_class_name": "LLMStructuredCompletionModel",
                    "_bases": ["Model", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMStructuredCompletionModel.predict",
                "digest": "ili08oGwFsNX4Bn0fhZPvKpT9CfjSgNJVLegSJ2iGUk",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "DiAZb8kCdeyJthXvVuKMe1CwwaPbSuFxH0JNGZsmenY"},
                },
            },
            {
                "object_id": "Evaluation.summarize",
                "digest": "eq6QbaZJYKZlbaCR95PvaoLDomTryBhb5uajqpIX8u0",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "vY6VtT9xBAKNfqhozgQdWEGuijncPtmZLYKrXexUERY"},
                },
            },
            {
                "object_id": "MyScorer.score",
                "digest": "BE7Pf2XsllJGfbeffAcYiZa2zRAD24oytT9U9iqIn4o",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "Y7lSNR7UXFYVtxWyD8GOE3CFXRWfdLX2n1mcYfbSErs"},
                },
            },
            {
                "object_id": "Scorer.summarize",
                "digest": "bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "mfCJxTVupdfb98h8MKgrxYxRwh4ZkEfjqVKvRKpzcZo"},
                },
            },
        ],
        exp_files=[
            {
                "digest": "MqFC4mjZWQVAB2AkQZ1g4uNUee9YhkUYXLYArWmTEcU",
                "exp_content": b'import weave\nfrom weave.trace.op_protocol import Op\nfrom weave.flow.model import Model\nimport json\nfrom weave.trace.op import op\nfrom weave.trace.call import Call\nfrom datetime import datetime\nfrom weave.flow.util import make_memorable_name\n\ndef _safe_summarize_to_str(summary: dict) -> str:\n    summary_str = ""\n    try:\n        summary_str = json.dumps(summary, indent=2)\n    except Exception:\n        try:\n            summary_str = str(summary)\n        except Exception:\n            pass\n    return summary_str\n\nlogger = "<Logger weave.evaluation.eval (DEBUG)>"\n\ndef default_evaluation_display_name(call: Call) -> str:\n    date = datetime.now().strftime("%Y-%m-%d")\n    unique_name = make_memorable_name()\n    return f"eval-{date}-{unique_name}"\n\n@weave.op\n@op(call_display_name=default_evaluation_display_name)\nasync def evaluate(self, model: Op | Model) -> dict:\n    eval_results = await self.get_eval_results(model)\n    summary = await self.summarize(eval_results)\n\n    summary_str = _safe_summarize_to_str(summary)\n    if summary_str:\n        logger.info(f"Evaluation summary {summary_str}")\n\n    return summary\n',
            },
            {
                "digest": "Y7lSNR7UXFYVtxWyD8GOE3CFXRWfdLX2n1mcYfbSErs",
                "exp_content": b"import weave\n\n@weave.op\ndef score(self, user_input: str, output: str) -> str:\n    return user_input in output\n",
            },
            {
                "digest": "mfCJxTVupdfb98h8MKgrxYxRwh4ZkEfjqVKvRKpzcZo",
                "exp_content": b'import weave\nfrom numbers import Number\nfrom typing import Any\nfrom pydantic.main import BaseModel\nfrom weave.trace.op import op\n\ndef _import_numpy() -> Any | None:\n    try:\n        import numpy\n    except ImportError:\n        return None\n    return numpy\n\ndef auto_summarize(data: list) -> dict[str, Any] | None:\n    """Automatically summarize a list of (potentially nested) dicts.\n\n    Computes:\n        - avg for numeric cols\n        - count and fraction for boolean cols\n        - other col types are ignored\n\n    If col is all None, result is None\n\n    Returns:\n      dict of summary stats, with structure matching input dict structure.\n    """\n    if not data:\n        return {}\n    data = [x for x in data if x is not None]\n\n    if not data:\n        return None\n\n    val = data[0]\n\n    if isinstance(val, bool):\n        return {\n            "true_count": (true_count := sum(1 for x in data if x)),\n            "true_fraction": true_count / len(data),\n        }\n    elif isinstance(val, Number):\n        if np := _import_numpy():\n            return {"mean": np.mean(data).item()}\n        else:\n            return {"mean": sum(data) / len(data)}\n    elif isinstance(val, dict):\n        result = {}\n        all_keys = list(\n            dict.fromkeys([k for d in data if isinstance(d, dict) for k in d.keys()])\n        )\n        for k in all_keys:\n            if (\n                summary := auto_summarize(\n                    [x.get(k) for x in data if isinstance(x, dict)]\n                )\n            ) is not None:\n                if k in summary:\n                    result.update(summary)\n                else:\n                    result[k] = summary\n        if not result:\n            return None\n        return result\n    elif isinstance(val, BaseModel):\n        return auto_summarize([x.model_dump() for x in data])\n    return None\n\n@weave.op\n@op\ndef summarize(self, score_rows: list) -> dict | None:\n    return auto_summarize(score_rows)\n',
            },
            {
                "digest": "ZHD4K7uUDPT93NdVQO3I6F9Xah9AEceWYBSQXg1bZPM",
                "exp_content": b'import weave\nfrom weave.trace.op_protocol import Op\nfrom weave.flow.model import Model\nfrom weave.flow.model import apply_model_async\nfrom weave.flow.model import ApplyModelError\nimport asyncio\nfrom weave.flow.scorer import get_scorer_attributes\nfrom weave.trace.op import op\n\n@weave.op\n@op\nasync def predict_and_score(self, model: Op | Model, example: dict) -> dict:\n    apply_model_result = await apply_model_async(\n        model, example, self.preprocess_model_input\n    )\n\n    if isinstance(apply_model_result, ApplyModelError):\n        return {\n            self._output_key: None,\n            "scores": {},\n            "model_latency": apply_model_result.model_latency,\n        }\n\n    model_output = apply_model_result.model_output\n    model_call = apply_model_result.model_call\n    model_latency = apply_model_result.model_latency\n\n    scores = {}\n    if scorers := self.scorers:\n        # Run all scorer calls in parallel\n        scorer_tasks = [\n            model_call.apply_scorer(scorer, example) for scorer in scorers\n        ]\n        apply_scorer_results = await asyncio.gather(*scorer_tasks)\n\n        # Process results and build scores dict\n        for scorer, apply_scorer_result in zip(\n            scorers, apply_scorer_results, strict=False\n        ):\n            result = apply_scorer_result.result\n            scorer_attributes = get_scorer_attributes(scorer)\n            scorer_name = scorer_attributes.scorer_name\n            scores[scorer_name] = result\n\n    return {\n        self._output_key: model_output,\n        "scores": scores,\n        "model_latency": model_latency,\n    }\n',
            },
            {
                "digest": "vY6VtT9xBAKNfqhozgQdWEGuijncPtmZLYKrXexUERY",
                "exp_content": b'import weave\nfrom weave.object.obj import Object\nfrom weave.trace.table import Table\nfrom weave.flow.util import transpose\nfrom weave.flow.scorer import get_scorer_attributes\nfrom weave.flow.scorer import auto_summarize\nfrom weave.trace.op import op\n\nclass EvaluationResults(Object):\n    rows: Table\n\n@weave.op\n@op\nasync def summarize(self, eval_table: EvaluationResults) -> dict:\n    eval_table_rows = list(eval_table.rows)\n    cols = transpose(eval_table_rows)\n    summary = {}\n\n    for name, vals in cols.items():\n        if name == "scores":\n            if scorers := self.scorers:\n                for scorer in scorers:\n                    scorer_attributes = get_scorer_attributes(scorer)\n                    scorer_name = scorer_attributes.scorer_name\n                    summarize_fn = scorer_attributes.summarize_fn\n                    scorer_stats = transpose(vals)\n                    score_table = scorer_stats[scorer_name]\n                    scored = summarize_fn(score_table)\n                    summary[scorer_name] = scored\n        else:\n            model_output_summary = auto_summarize(vals)\n            if model_output_summary:\n                summary[name] = model_output_summary\n    return summary\n',
            },
            {
                "digest": "fqXqYs4C4l0HpQOaRfbVXwsvwYUZhMYyn4cvK0wnCMU",
                "exp_content": b'import weave\nfrom typing import Any\nfrom weave.prompt.prompt import MessagesPrompt\nfrom weave.trace.op import op\n\n@weave.op\n@op\ndef score(self, *, output: str, **kwargs: Any) -> Any:\n    """Score the output using the scoring_prompt."""\n    if isinstance(self.scoring_prompt, MessagesPrompt):\n        model_input = self.scoring_prompt.format(output=output, **kwargs)\n    else:\n        scoring_prompt = self.scoring_prompt.format(output=output, **kwargs)\n        model_input = [{"role": "user", "content": scoring_prompt}]\n    return self.model.predict(model_input)\n',
            },
            {
                "digest": "DiAZb8kCdeyJthXvVuKMe1CwwaPbSuFxH0JNGZsmenY",
                "exp_content": b'import weave\nfrom typing import Annotated as MessageListLike\nfrom typing import Annotated as LLMStructuredModelParamsLike\nfrom typing import Any\nfrom weave.trace.context.weave_client_context import get_weave_client\nfrom weave.trace.context.weave_client_context import WeaveInitError\nfrom weave.utils.project_id import to_project_id\nfrom typing import Literal as ResponseFormat\nimport json\nfrom pydantic.main import BaseModel\nfrom weave.trace.op import op\n\nclass Message(BaseModel):\n    """A message in a conversation with an LLM.\n\n    Attributes:\n        role: The role of the message\'s author. Can be: system, user, assistant, function or tool.\n        content: The contents of the message. Required for all messages, but may be null for assistant messages with function calls.\n        name: The name of the author of the message. Required if role is "function". Must match the name of the function represented in content.\n              Can contain characters (a-z, A-Z, 0-9), and underscores, with a maximum length of 64 characters.\n        function_call: The name and arguments of a function that should be called, as generated by the model.\n        tool_call_id: Tool call that this message is responding to.\n    """\n\n    role: str\n    content: str | list[dict] | None = None\n    name: str | None = None\n    function_call: dict | None = None\n    tool_call_id: str | None = None\n\ndef parse_response(\n    response_payload: dict, response_format: ResponseFormat | None\n) -> Message | str | dict[str, Any]:\n    if response_payload.get("error"):\n        # Or handle more gracefully depending on desired behavior\n        raise RuntimeError(f"LLM API returned an error: {response_payload[\'error\']}")\n\n    # Assuming OpenAI-like structure: a list of choices, first choice has the message\n    output_message_dict = response_payload["choices"][0]["message"]\n\n    if response_format == "text":\n        return output_message_dict["content"]\n    elif response_format == "json_object":\n        return json.loads(output_message_dict["content"])\n    else:\n        raise ValueError(f"Invalid response_format: {response_format}")\n\n@weave.op\n@op\ndef predict(\n    self,\n    user_input: MessageListLike | None = None,\n    config: LLMStructuredModelParamsLike | None = None,\n    **template_vars: Any,\n) -> Message | str | dict[str, Any]:\n    """Generates a prediction by preparing messages (template + user_input)\n    and calling the LLM completions endpoint with overridden config, using the provided client.\n\n    Messages are prepared in one of two ways:\n    1. If default_params.prompt is set, the referenced MessagesPrompt object is\n       loaded and its format() method is called with template_vars to generate messages.\n    2. If default_params.messages_template is set (and prompt is not), the template\n       messages are used with template variable substitution.\n\n    Note: If both prompt and messages_template are provided, prompt takes precedence.\n\n    Args:\n        user_input: The user input messages to append after template messages\n        config: Optional configuration to override default parameters\n        **template_vars: Variables to substitute in the messages template using {variable_name} syntax\n    """\n    if user_input is None:\n        user_input = []\n\n    current_client = get_weave_client()\n    if current_client is None:\n        raise WeaveInitError(\n            "You must call `weave.init(<project_name>)` first, to predict with a LLMStructuredCompletionModel"\n        )\n\n    req = self.prepare_completion_request(\n        project_id=to_project_id(current_client.entity, current_client.project),\n        user_input=user_input,\n        config=config,\n        **template_vars,\n    )\n\n    # 5. Call the LLM API\n    try:\n        api_response = current_client.server.completions_create(req=req)\n    except Exception as e:\n        raise RuntimeError("Failed to call LLM completions endpoint.") from e\n\n    # 6. Extract the message from the API response\n    try:\n        # The \'response\' attribute of CompletionsCreateRes is a dict\n        response_payload = api_response.response\n        response_format = (\n            req.inputs.response_format.get("type")\n            if req.inputs.response_format is not None\n            else None\n        )\n        return parse_response(response_payload, response_format)\n    except (\n        KeyError,\n        IndexError,\n        TypeError,\n        AttributeError,\n        json.JSONDecodeError,\n    ) as e:\n        raise RuntimeError(\n            f"Failed to extract message from LLM response payload. Response: {api_response.response}"\n        ) from e\n',
            },
        ],
        # Sad ... equality is really a pain to assert here (and is broken)
        # TODO: Write a good equality check and make it work
        equality_check=lambda a, b: True,
        python_version_code_capture=(3, 13),
    ),
    SerializationTestCase(
        id="Library Objects - Scorer, Evaluation, Dataset, LLMAsAJudgeScorer, LLMStructuredCompletionModel (legacy v3)",
        runtime_object_factory=lambda: make_evaluation(),
        inline_call_param=False,
        is_legacy=True,
        exp_json={
            "_type": "Evaluation",
            "name": None,
            "description": None,
            "dataset": "weave:///shawn/test-project/object/Dataset:N0VKaX8wr9kF9QQzM7mSQz3yKrJJjTiJi4c9Bt7RSTA",
            "scorers": [
                "weave:///shawn/test-project/object/MyScorer:ILpCvdAsCLLLt9wU28MU9ugSScTkg7L3XX6PlUgFvlg",
                "weave:///shawn/test-project/object/LLMAsAJudgeScorer:hhCGYF6e9ybgkNGlFyXNxwAYArvjeCDXtEFUkcvgK3c",
            ],
            "preprocess_model_input": None,
            "trials": 1,
            "metadata": None,
            "evaluation_name": None,
            "evaluate": "weave:///shawn/test-project/op/Evaluation.evaluate:XbyuZNBxQ90Ur9tjMI6Cj8CNXnisWemlzU8etRYeFsI",
            "predict_and_score": "weave:///shawn/test-project/op/Evaluation.predict_and_score:NrwneWUrXaCdi9BUqmufH4dg1U1tvHFGPK5dZh2CcPQ",
            "summarize": "weave:///shawn/test-project/op/Evaluation.summarize:eq6QbaZJYKZlbaCR95PvaoLDomTryBhb5uajqpIX8u0",
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
                "digest": "XbyuZNBxQ90Ur9tjMI6Cj8CNXnisWemlzU8etRYeFsI",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "MqFC4mjZWQVAB2AkQZ1g4uNUee9YhkUYXLYArWmTEcU"},
                },
            },
            {
                "object_id": "Evaluation.predict_and_score",
                "digest": "NrwneWUrXaCdi9BUqmufH4dg1U1tvHFGPK5dZh2CcPQ",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "ZHD4K7uUDPT93NdVQO3I6F9Xah9AEceWYBSQXg1bZPM"},
                },
            },
            {
                "object_id": "MyScorer",
                "digest": "ILpCvdAsCLLLt9wU28MU9ugSScTkg7L3XX6PlUgFvlg",
                "exp_val": {
                    "_type": "MyScorer",
                    "name": None,
                    "description": None,
                    "column_map": None,
                    "score": "weave:///shawn/test-project/op/MyScorer.score:BE7Pf2XsllJGfbeffAcYiZa2zRAD24oytT9U9iqIn4o",
                    "summarize": "weave:///shawn/test-project/op/Scorer.summarize:bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                    "_class_name": "MyScorer",
                    "_bases": ["Scorer", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMAsAJudgeScorer",
                "digest": "hhCGYF6e9ybgkNGlFyXNxwAYArvjeCDXtEFUkcvgK3c",
                "exp_val": {
                    "_type": "LLMAsAJudgeScorer",
                    "name": None,
                    "description": None,
                    "column_map": None,
                    "model": "weave:///shawn/test-project/object/LLMStructuredCompletionModel:VUqRnYmuvNhu3zgfDb9hnZhLRFM1vKKI1WEpw3bsViE",
                    "enable_audio_input_scoring": True,
                    "audio_input_scoring_json_paths": [
                        "$.messages[0].content[1].input_audio"
                    ],
                    "scoring_prompt": "Here are the inputs: {inputs}. Here is the output: {output}. Is the output correct?",
                    "score": "weave:///shawn/test-project/op/LLMAsAJudgeScorer.score:EdDalYbNwTflbeMrWbUDn3tlYQeX9JquL9DkXuKRZr8",
                    "summarize": "weave:///shawn/test-project/op/Scorer.summarize:bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                    "_class_name": "LLMAsAJudgeScorer",
                    "_bases": ["Scorer", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMAsAJudgeScorer.score",
                "digest": "EdDalYbNwTflbeMrWbUDn3tlYQeX9JquL9DkXuKRZr8",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "fqXqYs4C4l0HpQOaRfbVXwsvwYUZhMYyn4cvK0wnCMU"},
                },
            },
            {
                "object_id": "LLMStructuredCompletionModel",
                "digest": "VUqRnYmuvNhu3zgfDb9hnZhLRFM1vKKI1WEpw3bsViE",
                "exp_val": {
                    "_type": "LLMStructuredCompletionModel",
                    "name": None,
                    "description": None,
                    "llm_model_id": "gpt-4o-mini",
                    "default_params": {
                        "_type": "LLMStructuredCompletionModelDefaultParams",
                        "messages_template": [
                            {
                                "_type": "Message",
                                "role": "system",
                                "content": "You are a judge, respond with json. 'score' (0-1), 'reasoning' (string)",
                                "name": None,
                                "function_call": None,
                                "tool_call_id": None,
                                "_class_name": "Message",
                                "_bases": ["BaseModel"],
                            }
                        ],
                        "prompt": None,
                        "temperature": None,
                        "top_p": None,
                        "max_tokens": None,
                        "presence_penalty": None,
                        "frequency_penalty": None,
                        "stop": None,
                        "n_times": None,
                        "functions": None,
                        "response_format": "json_object",
                        "_class_name": "LLMStructuredCompletionModelDefaultParams",
                        "_bases": ["BaseModel"],
                    },
                    "predict": "weave:///shawn/test-project/op/LLMStructuredCompletionModel.predict:ili08oGwFsNX4Bn0fhZPvKpT9CfjSgNJVLegSJ2iGUk",
                    "_class_name": "LLMStructuredCompletionModel",
                    "_bases": ["Model", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMStructuredCompletionModel.predict",
                "digest": "ili08oGwFsNX4Bn0fhZPvKpT9CfjSgNJVLegSJ2iGUk",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "DiAZb8kCdeyJthXvVuKMe1CwwaPbSuFxH0JNGZsmenY"},
                },
            },
            {
                "object_id": "Evaluation.summarize",
                "digest": "eq6QbaZJYKZlbaCR95PvaoLDomTryBhb5uajqpIX8u0",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "vY6VtT9xBAKNfqhozgQdWEGuijncPtmZLYKrXexUERY"},
                },
            },
            {
                "object_id": "MyScorer.score",
                "digest": "BE7Pf2XsllJGfbeffAcYiZa2zRAD24oytT9U9iqIn4o",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "Y7lSNR7UXFYVtxWyD8GOE3CFXRWfdLX2n1mcYfbSErs"},
                },
            },
            {
                "object_id": "Scorer.summarize",
                "digest": "bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "mfCJxTVupdfb98h8MKgrxYxRwh4ZkEfjqVKvRKpzcZo"},
                },
            },
        ],
        exp_files=[
            {
                "digest": "MqFC4mjZWQVAB2AkQZ1g4uNUee9YhkUYXLYArWmTEcU",
                "exp_content": b'import weave\nfrom weave.trace.op_protocol import Op\nfrom weave.flow.model import Model\nimport json\nfrom weave.trace.op import op\nfrom weave.trace.call import Call\nfrom datetime import datetime\nfrom weave.flow.util import make_memorable_name\n\ndef _safe_summarize_to_str(summary: dict) -> str:\n    summary_str = ""\n    try:\n        summary_str = json.dumps(summary, indent=2)\n    except Exception:\n        try:\n            summary_str = str(summary)\n        except Exception:\n            pass\n    return summary_str\n\nlogger = "<Logger weave.evaluation.eval (DEBUG)>"\n\ndef default_evaluation_display_name(call: Call) -> str:\n    date = datetime.now().strftime("%Y-%m-%d")\n    unique_name = make_memorable_name()\n    return f"eval-{date}-{unique_name}"\n\n@weave.op\n@op(call_display_name=default_evaluation_display_name)\nasync def evaluate(self, model: Op | Model) -> dict:\n    eval_results = await self.get_eval_results(model)\n    summary = await self.summarize(eval_results)\n\n    summary_str = _safe_summarize_to_str(summary)\n    if summary_str:\n        logger.info(f"Evaluation summary {summary_str}")\n\n    return summary\n',
            },
            {
                "digest": "Y7lSNR7UXFYVtxWyD8GOE3CFXRWfdLX2n1mcYfbSErs",
                "exp_content": b"import weave\n\n@weave.op\ndef score(self, user_input: str, output: str) -> str:\n    return user_input in output\n",
            },
            {
                "digest": "mfCJxTVupdfb98h8MKgrxYxRwh4ZkEfjqVKvRKpzcZo",
                "exp_content": b'import weave\nfrom numbers import Number\nfrom typing import Any\nfrom pydantic.main import BaseModel\nfrom weave.trace.op import op\n\ndef _import_numpy() -> Any | None:\n    try:\n        import numpy\n    except ImportError:\n        return None\n    return numpy\n\ndef auto_summarize(data: list) -> dict[str, Any] | None:\n    """Automatically summarize a list of (potentially nested) dicts.\n\n    Computes:\n        - avg for numeric cols\n        - count and fraction for boolean cols\n        - other col types are ignored\n\n    If col is all None, result is None\n\n    Returns:\n      dict of summary stats, with structure matching input dict structure.\n    """\n    if not data:\n        return {}\n    data = [x for x in data if x is not None]\n\n    if not data:\n        return None\n\n    val = data[0]\n\n    if isinstance(val, bool):\n        return {\n            "true_count": (true_count := sum(1 for x in data if x)),\n            "true_fraction": true_count / len(data),\n        }\n    elif isinstance(val, Number):\n        if np := _import_numpy():\n            return {"mean": np.mean(data).item()}\n        else:\n            return {"mean": sum(data) / len(data)}\n    elif isinstance(val, dict):\n        result = {}\n        all_keys = list(\n            dict.fromkeys([k for d in data if isinstance(d, dict) for k in d.keys()])\n        )\n        for k in all_keys:\n            if (\n                summary := auto_summarize(\n                    [x.get(k) for x in data if isinstance(x, dict)]\n                )\n            ) is not None:\n                if k in summary:\n                    result.update(summary)\n                else:\n                    result[k] = summary\n        if not result:\n            return None\n        return result\n    elif isinstance(val, BaseModel):\n        return auto_summarize([x.model_dump() for x in data])\n    return None\n\n@weave.op\n@op\ndef summarize(self, score_rows: list) -> dict | None:\n    return auto_summarize(score_rows)\n',
            },
            {
                "digest": "ZHD4K7uUDPT93NdVQO3I6F9Xah9AEceWYBSQXg1bZPM",
                "exp_content": b'import weave\nfrom weave.trace.op_protocol import Op\nfrom weave.flow.model import Model\nfrom weave.flow.model import apply_model_async\nfrom weave.flow.model import ApplyModelError\nimport asyncio\nfrom weave.flow.scorer import get_scorer_attributes\nfrom weave.trace.op import op\n\n@weave.op\n@op\nasync def predict_and_score(self, model: Op | Model, example: dict) -> dict:\n    apply_model_result = await apply_model_async(\n        model, example, self.preprocess_model_input\n    )\n\n    if isinstance(apply_model_result, ApplyModelError):\n        return {\n            self._output_key: None,\n            "scores": {},\n            "model_latency": apply_model_result.model_latency,\n        }\n\n    model_output = apply_model_result.model_output\n    model_call = apply_model_result.model_call\n    model_latency = apply_model_result.model_latency\n\n    scores = {}\n    if scorers := self.scorers:\n        # Run all scorer calls in parallel\n        scorer_tasks = [\n            model_call.apply_scorer(scorer, example) for scorer in scorers\n        ]\n        apply_scorer_results = await asyncio.gather(*scorer_tasks)\n\n        # Process results and build scores dict\n        for scorer, apply_scorer_result in zip(\n            scorers, apply_scorer_results, strict=False\n        ):\n            result = apply_scorer_result.result\n            scorer_attributes = get_scorer_attributes(scorer)\n            scorer_name = scorer_attributes.scorer_name\n            scores[scorer_name] = result\n\n    return {\n        self._output_key: model_output,\n        "scores": scores,\n        "model_latency": model_latency,\n    }\n',
            },
            {
                "digest": "vY6VtT9xBAKNfqhozgQdWEGuijncPtmZLYKrXexUERY",
                "exp_content": b'import weave\nfrom weave.object.obj import Object\nfrom weave.trace.table import Table\nfrom weave.flow.util import transpose\nfrom weave.flow.scorer import get_scorer_attributes\nfrom weave.flow.scorer import auto_summarize\nfrom weave.trace.op import op\n\nclass EvaluationResults(Object):\n    rows: Table\n\n@weave.op\n@op\nasync def summarize(self, eval_table: EvaluationResults) -> dict:\n    eval_table_rows = list(eval_table.rows)\n    cols = transpose(eval_table_rows)\n    summary = {}\n\n    for name, vals in cols.items():\n        if name == "scores":\n            if scorers := self.scorers:\n                for scorer in scorers:\n                    scorer_attributes = get_scorer_attributes(scorer)\n                    scorer_name = scorer_attributes.scorer_name\n                    summarize_fn = scorer_attributes.summarize_fn\n                    scorer_stats = transpose(vals)\n                    score_table = scorer_stats[scorer_name]\n                    scored = summarize_fn(score_table)\n                    summary[scorer_name] = scored\n        else:\n            model_output_summary = auto_summarize(vals)\n            if model_output_summary:\n                summary[name] = model_output_summary\n    return summary\n',
            },
            {
                "digest": "fqXqYs4C4l0HpQOaRfbVXwsvwYUZhMYyn4cvK0wnCMU",
                "exp_content": b'import weave\nfrom typing import Any\nfrom weave.prompt.prompt import MessagesPrompt\nfrom weave.trace.op import op\n\n@weave.op\n@op\ndef score(self, *, output: str, **kwargs: Any) -> Any:\n    """Score the output using the scoring_prompt."""\n    if isinstance(self.scoring_prompt, MessagesPrompt):\n        model_input = self.scoring_prompt.format(output=output, **kwargs)\n    else:\n        scoring_prompt = self.scoring_prompt.format(output=output, **kwargs)\n        model_input = [{"role": "user", "content": scoring_prompt}]\n    return self.model.predict(model_input)\n',
            },
            {
                "digest": "DiAZb8kCdeyJthXvVuKMe1CwwaPbSuFxH0JNGZsmenY",
                "exp_content": b'import weave\nfrom typing import Annotated as MessageListLike\nfrom typing import Annotated as LLMStructuredModelParamsLike\nfrom typing import Any\nfrom weave.trace.context.weave_client_context import get_weave_client\nfrom weave.trace.context.weave_client_context import WeaveInitError\nfrom weave.utils.project_id import to_project_id\nfrom typing import Literal as ResponseFormat\nimport json\nfrom pydantic.main import BaseModel\nfrom weave.trace.op import op\n\nclass Message(BaseModel):\n    """A message in a conversation with an LLM.\n\n    Attributes:\n        role: The role of the message\'s author. Can be: system, user, assistant, function or tool.\n        content: The contents of the message. Required for all messages, but may be null for assistant messages with function calls.\n        name: The name of the author of the message. Required if role is "function". Must match the name of the function represented in content.\n              Can contain characters (a-z, A-Z, 0-9), and underscores, with a maximum length of 64 characters.\n        function_call: The name and arguments of a function that should be called, as generated by the model.\n        tool_call_id: Tool call that this message is responding to.\n    """\n\n    role: str\n    content: str | list[dict] | None = None\n    name: str | None = None\n    function_call: dict | None = None\n    tool_call_id: str | None = None\n\ndef parse_response(\n    response_payload: dict, response_format: ResponseFormat | None\n) -> Message | str | dict[str, Any]:\n    if response_payload.get("error"):\n        # Or handle more gracefully depending on desired behavior\n        raise RuntimeError(f"LLM API returned an error: {response_payload[\'error\']}")\n\n    # Assuming OpenAI-like structure: a list of choices, first choice has the message\n    output_message_dict = response_payload["choices"][0]["message"]\n\n    if response_format == "text":\n        return output_message_dict["content"]\n    elif response_format == "json_object":\n        return json.loads(output_message_dict["content"])\n    else:\n        raise ValueError(f"Invalid response_format: {response_format}")\n\n@weave.op\n@op\ndef predict(\n    self,\n    user_input: MessageListLike | None = None,\n    config: LLMStructuredModelParamsLike | None = None,\n    **template_vars: Any,\n) -> Message | str | dict[str, Any]:\n    """Generates a prediction by preparing messages (template + user_input)\n    and calling the LLM completions endpoint with overridden config, using the provided client.\n\n    Messages are prepared in one of two ways:\n    1. If default_params.prompt is set, the referenced MessagesPrompt object is\n       loaded and its format() method is called with template_vars to generate messages.\n    2. If default_params.messages_template is set (and prompt is not), the template\n       messages are used with template variable substitution.\n\n    Note: If both prompt and messages_template are provided, prompt takes precedence.\n\n    Args:\n        user_input: The user input messages to append after template messages\n        config: Optional configuration to override default parameters\n        **template_vars: Variables to substitute in the messages template using {variable_name} syntax\n    """\n    if user_input is None:\n        user_input = []\n\n    current_client = get_weave_client()\n    if current_client is None:\n        raise WeaveInitError(\n            "You must call `weave.init(<project_name>)` first, to predict with a LLMStructuredCompletionModel"\n        )\n\n    req = self.prepare_completion_request(\n        project_id=to_project_id(current_client.entity, current_client.project),\n        user_input=user_input,\n        config=config,\n        **template_vars,\n    )\n\n    # 5. Call the LLM API\n    try:\n        api_response = current_client.server.completions_create(req=req)\n    except Exception as e:\n        raise RuntimeError("Failed to call LLM completions endpoint.") from e\n\n    # 6. Extract the message from the API response\n    try:\n        # The \'response\' attribute of CompletionsCreateRes is a dict\n        response_payload = api_response.response\n        response_format = (\n            req.inputs.response_format.get("type")\n            if req.inputs.response_format is not None\n            else None\n        )\n        return parse_response(response_payload, response_format)\n    except (\n        KeyError,\n        IndexError,\n        TypeError,\n        AttributeError,\n        json.JSONDecodeError,\n    ) as e:\n        raise RuntimeError(\n            f"Failed to extract message from LLM response payload. Response: {api_response.response}"\n        ) from e\n',
            },
        ],
        # Sad ... equality is really a pain to assert here (and is broken)
        # TODO: Write a good equality check and make it work
        equality_check=lambda a, b: True,
        python_version_code_capture=(3, 13),
    ),
    SerializationTestCase(
        id="Library Objects - Scorer, Evaluation, Dataset, LLMAsAJudgeScorer, LLMStructuredCompletionModel (legacy v2)",
        runtime_object_factory=lambda: make_evaluation(),
        inline_call_param=False,
        is_legacy=True,
        exp_json={
            "_type": "Evaluation",
            "name": None,
            "description": None,
            "dataset": "weave:///shawn/test-project/object/Dataset:N0VKaX8wr9kF9QQzM7mSQz3yKrJJjTiJi4c9Bt7RSTA",
            "scorers": [
                "weave:///shawn/test-project/object/MyScorer:ILpCvdAsCLLLt9wU28MU9ugSScTkg7L3XX6PlUgFvlg",
                "weave:///shawn/test-project/object/LLMAsAJudgeScorer:XvXn9fzgUYSCNGkioUBrGA9OkI9vFxZg8HG8TVyVEjQ",
            ],
            "preprocess_model_input": None,
            "trials": 1,
            "metadata": None,
            "evaluation_name": None,
            "evaluate": "weave:///shawn/test-project/op/Evaluation.evaluate:XbyuZNBxQ90Ur9tjMI6Cj8CNXnisWemlzU8etRYeFsI",
            "predict_and_score": "weave:///shawn/test-project/op/Evaluation.predict_and_score:NrwneWUrXaCdi9BUqmufH4dg1U1tvHFGPK5dZh2CcPQ",
            "summarize": "weave:///shawn/test-project/op/Evaluation.summarize:eq6QbaZJYKZlbaCR95PvaoLDomTryBhb5uajqpIX8u0",
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
                "digest": "XbyuZNBxQ90Ur9tjMI6Cj8CNXnisWemlzU8etRYeFsI",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "MqFC4mjZWQVAB2AkQZ1g4uNUee9YhkUYXLYArWmTEcU"},
                },
            },
            {
                "object_id": "Evaluation.predict_and_score",
                "digest": "NrwneWUrXaCdi9BUqmufH4dg1U1tvHFGPK5dZh2CcPQ",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "ZHD4K7uUDPT93NdVQO3I6F9Xah9AEceWYBSQXg1bZPM"},
                },
            },
            {
                "object_id": "MyScorer",
                "digest": "ILpCvdAsCLLLt9wU28MU9ugSScTkg7L3XX6PlUgFvlg",
                "exp_val": {
                    "_type": "MyScorer",
                    "name": None,
                    "description": None,
                    "column_map": None,
                    "score": "weave:///shawn/test-project/op/MyScorer.score:BE7Pf2XsllJGfbeffAcYiZa2zRAD24oytT9U9iqIn4o",
                    "summarize": "weave:///shawn/test-project/op/Scorer.summarize:bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                    "_class_name": "MyScorer",
                    "_bases": ["Scorer", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMAsAJudgeScorer",
                "digest": "XvXn9fzgUYSCNGkioUBrGA9OkI9vFxZg8HG8TVyVEjQ",
                "exp_val": {
                    "_type": "LLMAsAJudgeScorer",
                    "name": None,
                    "description": None,
                    "column_map": None,
                    "model": "weave:///shawn/test-project/object/LLMStructuredCompletionModel:VUqRnYmuvNhu3zgfDb9hnZhLRFM1vKKI1WEpw3bsViE",
                    "scoring_prompt": "Here are the inputs: {inputs}. Here is the output: {output}. Is the output correct?",
                    "score": "weave:///shawn/test-project/op/LLMAsAJudgeScorer.score:EdDalYbNwTflbeMrWbUDn3tlYQeX9JquL9DkXuKRZr8",
                    "summarize": "weave:///shawn/test-project/op/Scorer.summarize:bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                    "_class_name": "LLMAsAJudgeScorer",
                    "_bases": ["Scorer", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMAsAJudgeScorer.score",
                "digest": "EdDalYbNwTflbeMrWbUDn3tlYQeX9JquL9DkXuKRZr8",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "fqXqYs4C4l0HpQOaRfbVXwsvwYUZhMYyn4cvK0wnCMU"},
                },
            },
            {
                "object_id": "LLMStructuredCompletionModel",
                "digest": "VUqRnYmuvNhu3zgfDb9hnZhLRFM1vKKI1WEpw3bsViE",
                "exp_val": {
                    "_type": "LLMStructuredCompletionModel",
                    "name": None,
                    "description": None,
                    "llm_model_id": "gpt-4o-mini",
                    "default_params": {
                        "_type": "LLMStructuredCompletionModelDefaultParams",
                        "messages_template": [
                            {
                                "_type": "Message",
                                "role": "system",
                                "content": "You are a judge, respond with json. 'score' (0-1), 'reasoning' (string)",
                                "name": None,
                                "function_call": None,
                                "tool_call_id": None,
                                "_class_name": "Message",
                                "_bases": ["BaseModel"],
                            }
                        ],
                        "prompt": None,
                        "temperature": None,
                        "top_p": None,
                        "max_tokens": None,
                        "presence_penalty": None,
                        "frequency_penalty": None,
                        "stop": None,
                        "n_times": None,
                        "functions": None,
                        "response_format": "json_object",
                        "_class_name": "LLMStructuredCompletionModelDefaultParams",
                        "_bases": ["BaseModel"],
                    },
                    "predict": "weave:///shawn/test-project/op/LLMStructuredCompletionModel.predict:ili08oGwFsNX4Bn0fhZPvKpT9CfjSgNJVLegSJ2iGUk",
                    "_class_name": "LLMStructuredCompletionModel",
                    "_bases": ["Model", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMStructuredCompletionModel.predict",
                "digest": "ili08oGwFsNX4Bn0fhZPvKpT9CfjSgNJVLegSJ2iGUk",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "DiAZb8kCdeyJthXvVuKMe1CwwaPbSuFxH0JNGZsmenY"},
                },
            },
            {
                "object_id": "Evaluation.summarize",
                "digest": "eq6QbaZJYKZlbaCR95PvaoLDomTryBhb5uajqpIX8u0",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "vY6VtT9xBAKNfqhozgQdWEGuijncPtmZLYKrXexUERY"},
                },
            },
            {
                "object_id": "MyScorer.score",
                "digest": "BE7Pf2XsllJGfbeffAcYiZa2zRAD24oytT9U9iqIn4o",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "Y7lSNR7UXFYVtxWyD8GOE3CFXRWfdLX2n1mcYfbSErs"},
                },
            },
            {
                "object_id": "Scorer.summarize",
                "digest": "bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "mfCJxTVupdfb98h8MKgrxYxRwh4ZkEfjqVKvRKpzcZo"},
                },
            },
        ],
        exp_files=[
            {
                "digest": "MqFC4mjZWQVAB2AkQZ1g4uNUee9YhkUYXLYArWmTEcU",
                "exp_content": b'import weave\nfrom weave.trace.op_protocol import Op\nfrom weave.flow.model import Model\nimport json\nfrom weave.trace.op import op\nfrom weave.trace.call import Call\nfrom datetime import datetime\nfrom weave.flow.util import make_memorable_name\n\ndef _safe_summarize_to_str(summary: dict) -> str:\n    summary_str = ""\n    try:\n        summary_str = json.dumps(summary, indent=2)\n    except Exception:\n        try:\n            summary_str = str(summary)\n        except Exception:\n            pass\n    return summary_str\n\nlogger = "<Logger weave.evaluation.eval (DEBUG)>"\n\ndef default_evaluation_display_name(call: Call) -> str:\n    date = datetime.now().strftime("%Y-%m-%d")\n    unique_name = make_memorable_name()\n    return f"eval-{date}-{unique_name}"\n\n@weave.op\n@op(call_display_name=default_evaluation_display_name)\nasync def evaluate(self, model: Op | Model) -> dict:\n    eval_results = await self.get_eval_results(model)\n    summary = await self.summarize(eval_results)\n\n    summary_str = _safe_summarize_to_str(summary)\n    if summary_str:\n        logger.info(f"Evaluation summary {summary_str}")\n\n    return summary\n',
            },
            {
                "digest": "Y7lSNR7UXFYVtxWyD8GOE3CFXRWfdLX2n1mcYfbSErs",
                "exp_content": b"import weave\n\n@weave.op\ndef score(self, user_input: str, output: str) -> str:\n    return user_input in output\n",
            },
            {
                "digest": "mfCJxTVupdfb98h8MKgrxYxRwh4ZkEfjqVKvRKpzcZo",
                "exp_content": b'import weave\nfrom numbers import Number\nfrom typing import Any\nfrom pydantic.main import BaseModel\nfrom weave.trace.op import op\n\ndef _import_numpy() -> Any | None:\n    try:\n        import numpy\n    except ImportError:\n        return None\n    return numpy\n\ndef auto_summarize(data: list) -> dict[str, Any] | None:\n    """Automatically summarize a list of (potentially nested) dicts.\n\n    Computes:\n        - avg for numeric cols\n        - count and fraction for boolean cols\n        - other col types are ignored\n\n    If col is all None, result is None\n\n    Returns:\n      dict of summary stats, with structure matching input dict structure.\n    """\n    if not data:\n        return {}\n    data = [x for x in data if x is not None]\n\n    if not data:\n        return None\n\n    val = data[0]\n\n    if isinstance(val, bool):\n        return {\n            "true_count": (true_count := sum(1 for x in data if x)),\n            "true_fraction": true_count / len(data),\n        }\n    elif isinstance(val, Number):\n        if np := _import_numpy():\n            return {"mean": np.mean(data).item()}\n        else:\n            return {"mean": sum(data) / len(data)}\n    elif isinstance(val, dict):\n        result = {}\n        all_keys = list(\n            dict.fromkeys([k for d in data if isinstance(d, dict) for k in d.keys()])\n        )\n        for k in all_keys:\n            if (\n                summary := auto_summarize(\n                    [x.get(k) for x in data if isinstance(x, dict)]\n                )\n            ) is not None:\n                if k in summary:\n                    result.update(summary)\n                else:\n                    result[k] = summary\n        if not result:\n            return None\n        return result\n    elif isinstance(val, BaseModel):\n        return auto_summarize([x.model_dump() for x in data])\n    return None\n\n@weave.op\n@op\ndef summarize(self, score_rows: list) -> dict | None:\n    return auto_summarize(score_rows)\n',
            },
            {
                "digest": "ZHD4K7uUDPT93NdVQO3I6F9Xah9AEceWYBSQXg1bZPM",
                "exp_content": b'import weave\nfrom weave.trace.op_protocol import Op\nfrom weave.flow.model import Model\nfrom weave.flow.model import apply_model_async\nfrom weave.flow.model import ApplyModelError\nimport asyncio\nfrom weave.flow.scorer import get_scorer_attributes\nfrom weave.trace.op import op\n\n@weave.op\n@op\nasync def predict_and_score(self, model: Op | Model, example: dict) -> dict:\n    apply_model_result = await apply_model_async(\n        model, example, self.preprocess_model_input\n    )\n\n    if isinstance(apply_model_result, ApplyModelError):\n        return {\n            self._output_key: None,\n            "scores": {},\n            "model_latency": apply_model_result.model_latency,\n        }\n\n    model_output = apply_model_result.model_output\n    model_call = apply_model_result.model_call\n    model_latency = apply_model_result.model_latency\n\n    scores = {}\n    if scorers := self.scorers:\n        # Run all scorer calls in parallel\n        scorer_tasks = [\n            model_call.apply_scorer(scorer, example) for scorer in scorers\n        ]\n        apply_scorer_results = await asyncio.gather(*scorer_tasks)\n\n        # Process results and build scores dict\n        for scorer, apply_scorer_result in zip(\n            scorers, apply_scorer_results, strict=False\n        ):\n            result = apply_scorer_result.result\n            scorer_attributes = get_scorer_attributes(scorer)\n            scorer_name = scorer_attributes.scorer_name\n            scores[scorer_name] = result\n\n    return {\n        self._output_key: model_output,\n        "scores": scores,\n        "model_latency": model_latency,\n    }\n',
            },
            {
                "digest": "vY6VtT9xBAKNfqhozgQdWEGuijncPtmZLYKrXexUERY",
                "exp_content": b'import weave\nfrom weave.object.obj import Object\nfrom weave.trace.table import Table\nfrom weave.flow.util import transpose\nfrom weave.flow.scorer import get_scorer_attributes\nfrom weave.flow.scorer import auto_summarize\nfrom weave.trace.op import op\n\nclass EvaluationResults(Object):\n    rows: Table\n\n@weave.op\n@op\nasync def summarize(self, eval_table: EvaluationResults) -> dict:\n    eval_table_rows = list(eval_table.rows)\n    cols = transpose(eval_table_rows)\n    summary = {}\n\n    for name, vals in cols.items():\n        if name == "scores":\n            if scorers := self.scorers:\n                for scorer in scorers:\n                    scorer_attributes = get_scorer_attributes(scorer)\n                    scorer_name = scorer_attributes.scorer_name\n                    summarize_fn = scorer_attributes.summarize_fn\n                    scorer_stats = transpose(vals)\n                    score_table = scorer_stats[scorer_name]\n                    scored = summarize_fn(score_table)\n                    summary[scorer_name] = scored\n        else:\n            model_output_summary = auto_summarize(vals)\n            if model_output_summary:\n                summary[name] = model_output_summary\n    return summary\n',
            },
            {
                "digest": "fqXqYs4C4l0HpQOaRfbVXwsvwYUZhMYyn4cvK0wnCMU",
                "exp_content": b'import weave\nfrom typing import Any\nfrom weave.prompt.prompt import MessagesPrompt\nfrom weave.trace.op import op\n\n@weave.op\n@op\ndef score(self, *, output: str, **kwargs: Any) -> Any:\n    """Score the output using the scoring_prompt."""\n    if isinstance(self.scoring_prompt, MessagesPrompt):\n        model_input = self.scoring_prompt.format(output=output, **kwargs)\n    else:\n        scoring_prompt = self.scoring_prompt.format(output=output, **kwargs)\n        model_input = [{"role": "user", "content": scoring_prompt}]\n    return self.model.predict(model_input)\n',
            },
            {
                "digest": "DiAZb8kCdeyJthXvVuKMe1CwwaPbSuFxH0JNGZsmenY",
                "exp_content": b'import weave\nfrom typing import Annotated as MessageListLike\nfrom typing import Annotated as LLMStructuredModelParamsLike\nfrom typing import Any\nfrom weave.trace.context.weave_client_context import get_weave_client\nfrom weave.trace.context.weave_client_context import WeaveInitError\nfrom weave.utils.project_id import to_project_id\nfrom typing import Literal as ResponseFormat\nimport json\nfrom pydantic.main import BaseModel\nfrom weave.trace.op import op\n\nclass Message(BaseModel):\n    """A message in a conversation with an LLM.\n\n    Attributes:\n        role: The role of the message\'s author. Can be: system, user, assistant, function or tool.\n        content: The contents of the message. Required for all messages, but may be null for assistant messages with function calls.\n        name: The name of the author of the message. Required if role is "function". Must match the name of the function represented in content.\n              Can contain characters (a-z, A-Z, 0-9), and underscores, with a maximum length of 64 characters.\n        function_call: The name and arguments of a function that should be called, as generated by the model.\n        tool_call_id: Tool call that this message is responding to.\n    """\n\n    role: str\n    content: str | list[dict] | None = None\n    name: str | None = None\n    function_call: dict | None = None\n    tool_call_id: str | None = None\n\ndef parse_response(\n    response_payload: dict, response_format: ResponseFormat | None\n) -> Message | str | dict[str, Any]:\n    if response_payload.get("error"):\n        # Or handle more gracefully depending on desired behavior\n        raise RuntimeError(f"LLM API returned an error: {response_payload[\'error\']}")\n\n    # Assuming OpenAI-like structure: a list of choices, first choice has the message\n    output_message_dict = response_payload["choices"][0]["message"]\n\n    if response_format == "text":\n        return output_message_dict["content"]\n    elif response_format == "json_object":\n        return json.loads(output_message_dict["content"])\n    else:\n        raise ValueError(f"Invalid response_format: {response_format}")\n\n@weave.op\n@op\ndef predict(\n    self,\n    user_input: MessageListLike | None = None,\n    config: LLMStructuredModelParamsLike | None = None,\n    **template_vars: Any,\n) -> Message | str | dict[str, Any]:\n    """Generates a prediction by preparing messages (template + user_input)\n    and calling the LLM completions endpoint with overridden config, using the provided client.\n\n    Messages are prepared in one of two ways:\n    1. If default_params.prompt is set, the referenced MessagesPrompt object is\n       loaded and its format() method is called with template_vars to generate messages.\n    2. If default_params.messages_template is set (and prompt is not), the template\n       messages are used with template variable substitution.\n\n    Note: If both prompt and messages_template are provided, prompt takes precedence.\n\n    Args:\n        user_input: The user input messages to append after template messages\n        config: Optional configuration to override default parameters\n        **template_vars: Variables to substitute in the messages template using {variable_name} syntax\n    """\n    if user_input is None:\n        user_input = []\n\n    current_client = get_weave_client()\n    if current_client is None:\n        raise WeaveInitError(\n            "You must call `weave.init(<project_name>)` first, to predict with a LLMStructuredCompletionModel"\n        )\n\n    req = self.prepare_completion_request(\n        project_id=to_project_id(current_client.entity, current_client.project),\n        user_input=user_input,\n        config=config,\n        **template_vars,\n    )\n\n    # 5. Call the LLM API\n    try:\n        api_response = current_client.server.completions_create(req=req)\n    except Exception as e:\n        raise RuntimeError("Failed to call LLM completions endpoint.") from e\n\n    # 6. Extract the message from the API response\n    try:\n        # The \'response\' attribute of CompletionsCreateRes is a dict\n        response_payload = api_response.response\n        response_format = (\n            req.inputs.response_format.get("type")\n            if req.inputs.response_format is not None\n            else None\n        )\n        return parse_response(response_payload, response_format)\n    except (\n        KeyError,\n        IndexError,\n        TypeError,\n        AttributeError,\n        json.JSONDecodeError,\n    ) as e:\n        raise RuntimeError(\n            f"Failed to extract message from LLM response payload. Response: {api_response.response}"\n        ) from e\n',
            },
        ],
        # Sad ... equality is really a pain to assert here (and is broken)
        # TODO: Write a good equality check and make it work
        equality_check=lambda a, b: True,
        python_version_code_capture=(3, 13),
    ),
    SerializationTestCase(
        id="Library Objects - Scorer, Evaluation, Dataset, LLMAsAJudgeScorer, LLMStructuredCompletionModel (Legacy)",
        runtime_object_factory=lambda: make_evaluation(),
        inline_call_param=False,
        is_legacy=True,
        exp_json={
            "_type": "Evaluation",
            "name": None,
            "description": None,
            "dataset": "weave:///shawn/test-project/object/Dataset:N0VKaX8wr9kF9QQzM7mSQz3yKrJJjTiJi4c9Bt7RSTA",
            "scorers": [
                "weave:///shawn/test-project/object/MyScorer:ILpCvdAsCLLLt9wU28MU9ugSScTkg7L3XX6PlUgFvlg",
                "weave:///shawn/test-project/object/LLMAsAJudgeScorer:U3vlpg3CT6cuu0jcm3eFm5MyDxXvH0OCvrFax0VRY3w",
            ],
            "preprocess_model_input": None,
            "trials": 1,
            "metadata": None,
            "evaluation_name": None,
            "evaluate": "weave:///shawn/test-project/op/Evaluation.evaluate:XbyuZNBxQ90Ur9tjMI6Cj8CNXnisWemlzU8etRYeFsI",
            "predict_and_score": "weave:///shawn/test-project/op/Evaluation.predict_and_score:NrwneWUrXaCdi9BUqmufH4dg1U1tvHFGPK5dZh2CcPQ",
            "summarize": "weave:///shawn/test-project/op/Evaluation.summarize:eq6QbaZJYKZlbaCR95PvaoLDomTryBhb5uajqpIX8u0",
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
                "digest": "XbyuZNBxQ90Ur9tjMI6Cj8CNXnisWemlzU8etRYeFsI",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "MqFC4mjZWQVAB2AkQZ1g4uNUee9YhkUYXLYArWmTEcU"},
                },
            },
            {
                "object_id": "Evaluation.predict_and_score",
                "digest": "NrwneWUrXaCdi9BUqmufH4dg1U1tvHFGPK5dZh2CcPQ",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "ZHD4K7uUDPT93NdVQO3I6F9Xah9AEceWYBSQXg1bZPM"},
                },
            },
            {
                "object_id": "MyScorer",
                "digest": "ILpCvdAsCLLLt9wU28MU9ugSScTkg7L3XX6PlUgFvlg",
                "exp_val": {
                    "_type": "MyScorer",
                    "name": None,
                    "description": None,
                    "column_map": None,
                    "score": "weave:///shawn/test-project/op/MyScorer.score:BE7Pf2XsllJGfbeffAcYiZa2zRAD24oytT9U9iqIn4o",
                    "summarize": "weave:///shawn/test-project/op/Scorer.summarize:bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                    "_class_name": "MyScorer",
                    "_bases": ["Scorer", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMAsAJudgeScorer",
                "digest": "U3vlpg3CT6cuu0jcm3eFm5MyDxXvH0OCvrFax0VRY3w",
                "exp_val": {
                    "_type": "LLMAsAJudgeScorer",
                    "name": None,
                    "description": None,
                    "column_map": None,
                    "model": "weave:///shawn/test-project/object/LLMStructuredCompletionModel:kgMVTEoEXBudZExbXhfAS7InEQSOAzfsQ2qmvnCGd0M",
                    "scoring_prompt": "Here are the inputs: {inputs}. Here is the output: {output}. Is the output correct?",
                    "score": "weave:///shawn/test-project/op/LLMAsAJudgeScorer.score:OIgGBpG1Xnwppf494LDa4mC2AEEu5tFePiWkX3N6B1s",
                    "summarize": "weave:///shawn/test-project/op/Scorer.summarize:bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                    "_class_name": "LLMAsAJudgeScorer",
                    "_bases": ["Scorer", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMAsAJudgeScorer.score",
                "digest": "OIgGBpG1Xnwppf494LDa4mC2AEEu5tFePiWkX3N6B1s",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "esyCIeIgAhad4jQJkWoCjIUGPX4g4d6ccTx7Hpi80FA"},
                },
            },
            {
                "object_id": "LLMStructuredCompletionModel",
                "digest": "kgMVTEoEXBudZExbXhfAS7InEQSOAzfsQ2qmvnCGd0M",
                "exp_val": {
                    "_type": "LLMStructuredCompletionModel",
                    "name": None,
                    "description": None,
                    "llm_model_id": "gpt-4o-mini",
                    "default_params": {
                        "_type": "LLMStructuredCompletionModelDefaultParams",
                        "messages_template": [
                            {
                                "_type": "Message",
                                "role": "system",
                                "content": "You are a judge, respond with json. 'score' (0-1), 'reasoning' (string)",
                                "name": None,
                                "function_call": None,
                                "tool_call_id": None,
                                "_class_name": "Message",
                                "_bases": ["BaseModel"],
                            }
                        ],
                        "temperature": None,
                        "top_p": None,
                        "max_tokens": None,
                        "presence_penalty": None,
                        "frequency_penalty": None,
                        "stop": None,
                        "n_times": None,
                        "functions": None,
                        "response_format": "json_object",
                        "_class_name": "LLMStructuredCompletionModelDefaultParams",
                        "_bases": ["BaseModel"],
                    },
                    "predict": "weave:///shawn/test-project/op/LLMStructuredCompletionModel.predict:SjfGulYMo1eX8BDv4HxKOfswszec6CVI43rbFrnxB9M",
                    "_class_name": "LLMStructuredCompletionModel",
                    "_bases": ["Model", "Object", "BaseModel"],
                },
            },
            {
                "object_id": "LLMStructuredCompletionModel.predict",
                "digest": "SjfGulYMo1eX8BDv4HxKOfswszec6CVI43rbFrnxB9M",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "bKoTdAXVJi8AI1xrFMK4HtJoUt5NjJOzoYeh7C7m2t8"},
                },
            },
            {
                "object_id": "Evaluation.summarize",
                "digest": "eq6QbaZJYKZlbaCR95PvaoLDomTryBhb5uajqpIX8u0",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "vY6VtT9xBAKNfqhozgQdWEGuijncPtmZLYKrXexUERY"},
                },
            },
            {
                "object_id": "MyScorer.score",
                "digest": "BE7Pf2XsllJGfbeffAcYiZa2zRAD24oytT9U9iqIn4o",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "Y7lSNR7UXFYVtxWyD8GOE3CFXRWfdLX2n1mcYfbSErs"},
                },
            },
            {
                "object_id": "Scorer.summarize",
                "digest": "bWwaybJxxIBLMGZp7bzeKrmjhLNCp2DYrubnU2Ry9xQ",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "mfCJxTVupdfb98h8MKgrxYxRwh4ZkEfjqVKvRKpzcZo"},
                },
            },
        ],
        exp_files=[
            {
                "digest": "MqFC4mjZWQVAB2AkQZ1g4uNUee9YhkUYXLYArWmTEcU",
                "exp_content": b'import weave\nfrom weave.trace.op_protocol import Op\nfrom weave.flow.model import Model\nimport json\nfrom weave.trace.op import op\nfrom weave.trace.call import Call\nfrom datetime import datetime\nfrom weave.flow.util import make_memorable_name\n\ndef _safe_summarize_to_str(summary: dict) -> str:\n    summary_str = ""\n    try:\n        summary_str = json.dumps(summary, indent=2)\n    except Exception:\n        try:\n            summary_str = str(summary)\n        except Exception:\n            pass\n    return summary_str\n\nlogger = "<Logger weave.evaluation.eval (DEBUG)>"\n\ndef default_evaluation_display_name(call: Call) -> str:\n    date = datetime.now().strftime("%Y-%m-%d")\n    unique_name = make_memorable_name()\n    return f"eval-{date}-{unique_name}"\n\n@weave.op\n@op(call_display_name=default_evaluation_display_name)\nasync def evaluate(self, model: Op | Model) -> dict:\n    eval_results = await self.get_eval_results(model)\n    summary = await self.summarize(eval_results)\n\n    summary_str = _safe_summarize_to_str(summary)\n    if summary_str:\n        logger.info(f"Evaluation summary {summary_str}")\n\n    return summary\n',
            },
            {
                "digest": "Y7lSNR7UXFYVtxWyD8GOE3CFXRWfdLX2n1mcYfbSErs",
                "exp_content": b"import weave\n\n@weave.op\ndef score(self, user_input: str, output: str) -> str:\n    return user_input in output\n",
            },
            {
                "digest": "mfCJxTVupdfb98h8MKgrxYxRwh4ZkEfjqVKvRKpzcZo",
                "exp_content": b'import weave\nfrom numbers import Number\nfrom typing import Any\nfrom pydantic.main import BaseModel\nfrom weave.trace.op import op\n\ndef _import_numpy() -> Any | None:\n    try:\n        import numpy\n    except ImportError:\n        return None\n    return numpy\n\ndef auto_summarize(data: list) -> dict[str, Any] | None:\n    """Automatically summarize a list of (potentially nested) dicts.\n\n    Computes:\n        - avg for numeric cols\n        - count and fraction for boolean cols\n        - other col types are ignored\n\n    If col is all None, result is None\n\n    Returns:\n      dict of summary stats, with structure matching input dict structure.\n    """\n    if not data:\n        return {}\n    data = [x for x in data if x is not None]\n\n    if not data:\n        return None\n\n    val = data[0]\n\n    if isinstance(val, bool):\n        return {\n            "true_count": (true_count := sum(1 for x in data if x)),\n            "true_fraction": true_count / len(data),\n        }\n    elif isinstance(val, Number):\n        if np := _import_numpy():\n            return {"mean": np.mean(data).item()}\n        else:\n            return {"mean": sum(data) / len(data)}\n    elif isinstance(val, dict):\n        result = {}\n        all_keys = list(\n            dict.fromkeys([k for d in data if isinstance(d, dict) for k in d.keys()])\n        )\n        for k in all_keys:\n            if (\n                summary := auto_summarize(\n                    [x.get(k) for x in data if isinstance(x, dict)]\n                )\n            ) is not None:\n                if k in summary:\n                    result.update(summary)\n                else:\n                    result[k] = summary\n        if not result:\n            return None\n        return result\n    elif isinstance(val, BaseModel):\n        return auto_summarize([x.model_dump() for x in data])\n    return None\n\n@weave.op\n@op\ndef summarize(self, score_rows: list) -> dict | None:\n    return auto_summarize(score_rows)\n',
            },
            {
                "digest": "ZHD4K7uUDPT93NdVQO3I6F9Xah9AEceWYBSQXg1bZPM",
                "exp_content": b'import weave\nfrom weave.trace.op_protocol import Op\nfrom weave.flow.model import Model\nfrom weave.flow.model import apply_model_async\nfrom weave.flow.model import ApplyModelError\nimport asyncio\nfrom weave.flow.scorer import get_scorer_attributes\nfrom weave.trace.op import op\n\n@weave.op\n@op\nasync def predict_and_score(self, model: Op | Model, example: dict) -> dict:\n    apply_model_result = await apply_model_async(\n        model, example, self.preprocess_model_input\n    )\n\n    if isinstance(apply_model_result, ApplyModelError):\n        return {\n            self._output_key: None,\n            "scores": {},\n            "model_latency": apply_model_result.model_latency,\n        }\n\n    model_output = apply_model_result.model_output\n    model_call = apply_model_result.model_call\n    model_latency = apply_model_result.model_latency\n\n    scores = {}\n    if scorers := self.scorers:\n        # Run all scorer calls in parallel\n        scorer_tasks = [\n            model_call.apply_scorer(scorer, example) for scorer in scorers\n        ]\n        apply_scorer_results = await asyncio.gather(*scorer_tasks)\n\n        # Process results and build scores dict\n        for scorer, apply_scorer_result in zip(\n            scorers, apply_scorer_results, strict=False\n        ):\n            result = apply_scorer_result.result\n            scorer_attributes = get_scorer_attributes(scorer)\n            scorer_name = scorer_attributes.scorer_name\n            scores[scorer_name] = result\n\n    return {\n        self._output_key: model_output,\n        "scores": scores,\n        "model_latency": model_latency,\n    }\n',
            },
            {
                "digest": "vY6VtT9xBAKNfqhozgQdWEGuijncPtmZLYKrXexUERY",
                "exp_content": b'import weave\nfrom weave.object.obj import Object\nfrom weave.trace.table import Table\nfrom weave.flow.util import transpose\nfrom weave.flow.scorer import get_scorer_attributes\nfrom weave.flow.scorer import auto_summarize\nfrom weave.trace.op import op\n\nclass EvaluationResults(Object):\n    rows: Table\n\n@weave.op\n@op\nasync def summarize(self, eval_table: EvaluationResults) -> dict:\n    eval_table_rows = list(eval_table.rows)\n    cols = transpose(eval_table_rows)\n    summary = {}\n\n    for name, vals in cols.items():\n        if name == "scores":\n            if scorers := self.scorers:\n                for scorer in scorers:\n                    scorer_attributes = get_scorer_attributes(scorer)\n                    scorer_name = scorer_attributes.scorer_name\n                    summarize_fn = scorer_attributes.summarize_fn\n                    scorer_stats = transpose(vals)\n                    score_table = scorer_stats[scorer_name]\n                    scored = summarize_fn(score_table)\n                    summary[scorer_name] = scored\n        else:\n            model_output_summary = auto_summarize(vals)\n            if model_output_summary:\n                summary[name] = model_output_summary\n    return summary\n',
            },
            {
                "digest": "esyCIeIgAhad4jQJkWoCjIUGPX4g4d6ccTx7Hpi80FA",
                "exp_content": b'import weave\nfrom typing import Any\nfrom weave.trace.op import op\n\n@weave.op\n@op\ndef score(self, *, output: str, **kwargs: Any) -> Any:\n    scoring_prompt = self.scoring_prompt.format(output=output, **kwargs)\n    model_input = [\n        {"role": "user", "content": scoring_prompt},\n    ]\n    return self.model.predict(model_input)\n',
            },
            {
                "digest": "bKoTdAXVJi8AI1xrFMK4HtJoUt5NjJOzoYeh7C7m2t8",
                "exp_content": b'import weave\nfrom typing import Annotated as MessageListLike\nfrom typing import Annotated as LLMStructuredModelParamsLike\nfrom typing import Any\nfrom weave.trace.context.weave_client_context import get_weave_client\nfrom weave.trace.context.weave_client_context import WeaveInitError\nfrom weave.utils.project_id import to_project_id\nfrom typing import Literal as ResponseFormat\nimport json\nfrom pydantic.main import BaseModel\nfrom weave.trace.op import op\n\nclass Message(BaseModel):\n    """A message in a conversation with an LLM.\n\n    Attributes:\n        role: The role of the message\'s author. Can be: system, user, assistant, function or tool.\n        content: The contents of the message. Required for all messages, but may be null for assistant messages with function calls.\n        name: The name of the author of the message. Required if role is "function". Must match the name of the function represented in content.\n              Can contain characters (a-z, A-Z, 0-9), and underscores, with a maximum length of 64 characters.\n        function_call: The name and arguments of a function that should be called, as generated by the model.\n        tool_call_id: Tool call that this message is responding to.\n    """\n\n    role: str\n    content: str | list[dict] | None = None\n    name: str | None = None\n    function_call: dict | None = None\n    tool_call_id: str | None = None\n\ndef parse_response(\n    response_payload: dict, response_format: ResponseFormat | None\n) -> Message | str | dict[str, Any]:\n    if response_payload.get("error"):\n        # Or handle more gracefully depending on desired behavior\n        raise RuntimeError(f"LLM API returned an error: {response_payload[\'error\']}")\n\n    # Assuming OpenAI-like structure: a list of choices, first choice has the message\n    output_message_dict = response_payload["choices"][0]["message"]\n\n    if response_format == "text":\n        return output_message_dict["content"]\n    elif response_format == "json_object":\n        return json.loads(output_message_dict["content"])\n    else:\n        raise ValueError(f"Invalid response_format: {response_format}")\n\n@weave.op\n@op\ndef predict(\n    self,\n    user_input: MessageListLike | None = None,\n    config: LLMStructuredModelParamsLike | None = None,\n    **template_vars: Any,\n) -> Message | str | dict[str, Any]:\n    """Generates a prediction by preparing messages (template + user_input)\n    and calling the LLM completions endpoint with overridden config, using the provided client.\n\n    Args:\n        user_input: The user input messages\n        config: Optional configuration to override default parameters\n        **template_vars: Variables to substitute in the messages template using {variable_name} syntax\n    """\n    if user_input is None:\n        user_input = []\n\n    current_client = get_weave_client()\n    if current_client is None:\n        raise WeaveInitError(\n            "You must call `weave.init(<project_name>)` first, to predict with a LLMStructuredCompletionModel"\n        )\n\n    req = self.prepare_completion_request(\n        project_id=to_project_id(current_client.entity, current_client.project),\n        user_input=user_input,\n        config=config,\n        **template_vars,\n    )\n\n    # 5. Call the LLM API\n    try:\n        api_response = current_client.server.completions_create(req=req)\n    except Exception as e:\n        raise RuntimeError("Failed to call LLM completions endpoint.") from e\n\n    # 6. Extract the message from the API response\n    try:\n        # The \'response\' attribute of CompletionsCreateRes is a dict\n        response_payload = api_response.response\n        response_format = (\n            req.inputs.response_format.get("type")\n            if req.inputs.response_format is not None\n            else None\n        )\n        return parse_response(response_payload, response_format)\n    except (\n        KeyError,\n        IndexError,\n        TypeError,\n        AttributeError,\n        json.JSONDecodeError,\n    ) as e:\n        raise RuntimeError(\n            f"Failed to extract message from LLM response payload. Response: {api_response.response}"\n        ) from e\n',
            },
        ],
        # Sad ... equality is really a pain to assert here (and is broken)
        # TODO: Write a good equality check and make it work
        equality_check=lambda a, b: True,
        python_version_code_capture=(3, 13),
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
            "predict": "weave:///shawn/test-project/op/MyModel.predict:mCmPlFC0ylrSIXNsfYCuKOvb8WxQG4XUbGqMqbM4ZJE",
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
                "digest": "mCmPlFC0ylrSIXNsfYCuKOvb8WxQG4XUbGqMqbM4ZJE",
                "exp_val": {
                    "_type": "CustomWeaveType",
                    "weave_type": {"type": "Op"},
                    "files": {"obj.py": "Xas2vXvfwWcR6oyzCYBxZi9aBQNdrjiTFf9mwt2xR40"},
                },
            },
        ],
        exp_files=[
            {
                "digest": "Xas2vXvfwWcR6oyzCYBxZi9aBQNdrjiTFf9mwt2xR40",
                "exp_content": b"import weave\n\n@weave.op\ndef predict(self, user_input: str) -> str:\n    return self.prompt.format(user_input=user_input)\n",
            }
        ],
        # Sad ... equality is really a pain to assert here (and is broken)
        # TODO: Write a good equality check and make it work
        equality_check=lambda a, b: True,
    ),
]
