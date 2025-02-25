# FAQs

The following page provides answers to common questions about Weave tracing.

## What information does Weave capture for a function?

A function can be designated as a Weave [Op](/guides/tracking/ops) either manually through a decorator or automatically as part of an enabled integration. When an Op executes, Weave captures detailed information to support your analysis. Weave provides you with fine grained control over what is logged in case you would like something different than the default; see below for configuration examples.

- **Code capture** - Weave captures a representation of the Op's source code. This includes inline comments as well as recursively capturing the value of variables or the source of non-Op functions that were called. Code capture allows you to see what your function was doing even if the change was not saved to your source control system. Code capture is used as part of Op versioning, allowing you to understand the evaluation of your code over time. If code capture is disabled, a hash value will be used instead.

- **Function name, inputs, and outputs** - The name of the function will be captured but can be [overridden](/guides/tracking/tracing/#call-display-name). A JSON-based representation of the inputs and outputs will be captured. For inputs, argument name will be capture in addition to value. Weave lets you [customize the logging](/guides/tracking/ops#customize-logged-inputs-and-outputs) of inputs and outputs - you can specify a function to add/remove/modify what is logged.

- **Op call hierarchy** - When an Op is called within the context of another Op executing, this relationship is captured, even in cases
  where there is an intermediate non-Op function executing. This relationship between Op calls is used to provide a "Trace tree".

- **Execution status and exceptions** - Weave tracks whether a function is executing, finished, or errored. If an exception occurs during execution the error message and a stack track is recorded.

- **System information** - Weave may capture information about which operating system the client is running on including detailed version information.

- **Client information** - Weave may capture information about the Weave client itself, such as the programming language in use and detailed version information for that language and the Weave client library.

- **Timing** - The execution start and end time is captured and also used for latency calculations.

- **Token usage** - In some [integrations](/guides/integrations/) LLM token usage counts may be automatically logged.

- **User and run context** - Logging is associated with a W&B user account. That will be captured along with any wandb Run context.

- **Derived information** - Weave may compute derived information from the raw information logged, for example a cost estimate may be calculated based on token usage and knowledge of the model used. Weave also aggregates some information over calls.

- **Additional information you choose** - You can choose to log [custom attributes](/guides/core-types/models#track-production-calls) as part of your call or attach [feedback](/guides/tracking/feedback#add-feedback-to-a-call) to a call.

## How can I disable code capture?

You can disable code capture during Weave client initialization: `weave.init("entity/project", settings={"capture_code": False})`.
You can also use the [environment variable](/guides/core-types/env-vars) `WEAVE_CAPTURE_CODE=false`.

## How can I disable system information capture?

You can disable system information capture during Weave client initialization: `weave.init("entity/project", settings={"capture_system_info": False})`.

## How can I disable client information capture?

You can disable client information capture during Weave client initialization: `weave.init("entity/project", settings={"capture_client_info": False})`.

## Will Weave affect my function's execution speed?

The overhead of Weave logging is typically negligible compared to making a call to an LLM.
To minimize Weave's impact on the speed of your Op's execution, its network activity happens on a background thread.
When your program is exiting it may appear to pause while any remaining enqueued data is logged.

## How is Weave data ingestion calculated?

We define ingested bytes as bytes that we receive, process, and store on your behalf. This includes trace metadata, LLM inputs/outputs, and any other information you explicitly log to Weave, but does not include communication overhead (e.g., HTTP headers) or any other data that is not placed in long-term storage. We count bytes as "ingested" only once at the time they are received and stored.

## What is pairwise evaluation and how do I do it?

When [scoring](../evaluation/scorers.md) models in a Weave [evaluation](../core-types/evaluations.md), absolute value metrics (e.g. `9/10` for Model A and `8/10` for Model B) are typically harder to assign than than relative ones (e.g. Model A performs better than Model B). _Pairwise evaluation_ allows you to compare the outputs of two models by ranking them relative to each other. This approach is particularly useful when you want to determine which model performs better for subjective tasks such as text generation, summarization, or question answering. With pairwise evaluation, you can obtain a relative preference ranking that reveals which model is best for specific inputs.

:::important
This approach is a workaround and may change in future releases. We are actively working on a more robust API to support pairwise evaluations. Stay tuned for updates!
:::

The following code sample demonstrates how to implement a pairwise evaluation in Weave by creating a [class-based scorer](../evaluation/scorers.md#class-based-scorers) called `PreferenceScorer`. The `PreferenceScorer` compares two models, `ModelA` and `ModelB`, and returns a relative score of the model outputs based on explicit hints in the input text.

```python
from weave import Model, Evaluation, Scorer, Dataset
from weave.flow.model import ApplyModelError, apply_model_async

class ModelA(Model):
    @weave.op
    def predict(self, input_text: str):
        if "Prefer model A" in input_text:
            return {"response": "This is a great answer from Model A"}
        return {"response": "Meh, whatever"}

class ModelB(Model):
    @weave.op
    def predict(self, input_text: str):
        if "Prefer model B" in input_text:
            return {"response": "This is a thoughtful answer from Model B"}
        return {"response": "I don't know"}

class PreferenceScorer(Scorer):
    @weave.op
    async def _get_other_model_output(self, example: dict) -> Any:
        """Get output from the other model for comparison.
        Args:
            example: The input example data to run through the other model
        Returns:
            The output from the other model
        """

        other_model_result = await apply_model_async(
            self.other_model,
            example,
            None,
        )

        if isinstance(other_model_result, ApplyModelError):
            return None

        return other_model_result.model_output

    @weave.op
    async def score(self, output: dict, input_text: str) -> dict:
        """Compare the output of the primary model with the other model.
        Args:
            output (dict): The output from the primary model.
            other_output (dict): The output from the other model being compared.
            inputs (str): The input text used to generate the outputs.
        Returns:
            dict: A flat dictionary containing the comparison result and reason.
        """
        other_output = await self._get_other_model_output(
            {"input_text": inputs}
        )
        if other_output is None:
            return {"primary_is_better": False, "reason": "Other model failed"}

        if "Prefer model A" in input_text:
            primary_is_better = True
            reason = "Model A gave a great answer"
        else:
            primary_is_better = False
            reason = "Model B is preferred for this type of question"

        return {"primary_is_better": primary_is_better, "reason": reason}

dataset = Dataset(
    rows=[
        {"input_text": "Prefer model A: Question 1"},  # Model A wins
        {"input_text": "Prefer model A: Question 2"},  # Model A wins
        {"input_text": "Prefer model B: Question 3"},  # Model B wins
        {"input_text": "Prefer model B: Question 4"},  # Model B wins
    ]
)

model_a = ModelA()
model_b = ModelB()
pref_scorer = PreferenceScorer(other_model=model_b)
evaluation = Evaluation(dataset=dataset, scorers=[pref_scorer])
evaluation.evaluate(model_a)
```
