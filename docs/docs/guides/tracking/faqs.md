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

- **Additional information you choose** - You can choose to log [custom metadata with `weave.attributes`](/guides/core-types/models#track-production-calls) as part of your call or attach [feedback](/guides/tracking/feedback#add-feedback-to-a-call) to a call.

## How can I disable code capture?

You can disable code capture during Weave client initialization: `weave.init("entity/project", settings={"capture_code": False})`.
You can also use the [environment variable](/guides/core-types/env-vars) `WEAVE_CAPTURE_CODE=false`.

## How can I disable system information capture?

You can disable system information capture during Weave client initialization: `weave.init("entity/project", settings={"capture_system_info": False})`.

## How can I disable client information capture?

You can disable client information capture during Weave client initialization: `weave.init("entity/project", settings={"capture_client_info": False})`.

## How do I render Python datetime values in the UI?

Use Python’s `datetime.datetime` (with timezone info), and publish the object using `weave.publish(...)`. Weave recognizes this type and renders it as a timestamp.

## How do I render Markdown in the UI?

Wrap your string with `weave.Markdown(...)` before saving, and use `weave.publish(...)` to store it. Weave uses the object’s type to determine rendering, and `weave.Markdown` maps to a known UI renderer.  The value will be shown as a formatted Markdown object in the UI. For a full code sample, see [Viewing calls](./tracing.mdx#viewing-calls).

## Will Weave affect my function's execution speed?

The overhead of Weave logging is typically negligible compared to making a call to an LLM.
To minimize Weave's impact on the speed of your Op's execution, its network activity happens on a background thread.
When your program is exiting it may appear to pause while any remaining enqueued data is logged.

## How is Weave data ingestion calculated?

We define ingested bytes as bytes that we receive, process, and store on your behalf. This includes trace metadata, LLM inputs/outputs, and any other information you explicitly log to Weave, but does not include communication overhead (e.g., HTTP headers) or any other data that is not placed in long-term storage. We count bytes as "ingested" only once at the time they are received and stored.

## What is pairwise evaluation and how do I do it?

When [scoring](../evaluation/scorers.md) models in a Weave [evaluation](../core-types/evaluations.md), absolute value metrics (e.g. `9/10` for Model A and `8/10` for Model B) are typically harder to assign than relative ones (e.g. Model A performs better than Model B). _Pairwise evaluation_ allows you to compare the outputs of two models by ranking them relative to each other. This approach is particularly useful when you want to determine which model performs better for subjective tasks such as text generation, summarization, or question answering. With pairwise evaluation, you can obtain a relative preference ranking that reveals which model is best for specific inputs.

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
            input_text (str): The input text used to generate the outputs.
        Returns:
            dict: A flat dictionary containing the comparison result and reason.
        """
        other_output = await self._get_other_model_output(
            {"input_text": input_text}
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

## Pricing FAQs

The following section provides answers to pricing FAQs. For the latest information, see the [pricing page](https://wandb.ai/site/pricing/).

### How is Weave data ingestion calculated?
We define ingested bytes as bytes that we receive, process, and store on your behalf. This includes trace metadata, LLM inputs/outputs, and any other information you explicitly log to Weave, but does not include communication overhead (e.g., HTTP headers) or any other data that is not placed in long term storage. We count bytes as "ingested" only once at the time they are received and stored.

### How much Weave data ingestion do I need?
We recommend using the free trial to estimate how much data ingestion you can expect to use. An average trace is approximately 0.22 MB, but the distribution is wide and varies depending on the use case and type of data sent.

### How much does Inference cost?
Each inference API has different costs for input and output tokens. Explore detailed pricing.

### What is a tracked hour?
A tracked hour is wall-clock time when training a model. If your model takes 8 hours to train, you have used 8 tracked hours. Today, this is irrespective of GPU quality, speed, etc. Importing runs from other platforms or syncing offline runs will contribute to your organization's tracked hour limit.

### How is storage calculated?
Storage includes both artifacts and data logged to runs.

Weights & Biases calculates your storage usage over the last 30 days. For example, if you use 100 GB of storage for 15 days of March, 200 GB for 1 day of March, and 300GB over 14 days of March your storage usage would be:

100 GB x 15 days = 1500 GB-days  
200 GB x 1 day x = 200 GB-days  
300 GB x 14 days x = 4200 GB-days  
5900 GB-days / (30 days) = 196.6 GB

At the end of 30 days, Weights & Biases rounds your storage to the nearest MB. Therefore, your storage usage for March would be 197 GB.

### Does tracked data stored on an external server count against my storage quota?
Absolutely not. Only the size of the metadata that you actually store in Weights & Biases counts against your storage quota. Reference artifacts and data stored in an external storage bucket will not count.

### Who qualifies as an academic?
Weights & Biases provides a free Pro license to academic institutions pursuing research not connected to a for-profit entity. This license is intended for students, professors, and postdoctoral researchers. An active email address affiliated with an academic institution is required.

### What does the academic license include?
The free academic license comes with all the product features included on Pro, 200GB of cloud storage, unlimited tracked hours, and up to 100 seats. Additional cloud storage can be purchased for $0.03 per GB, billed monthly. If you host Weights & Biases locally, cloud storage limits do not apply.
