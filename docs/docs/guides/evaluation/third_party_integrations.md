import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Third Party Integrations

## NVIDIA NeMo Evaluator

The NVIDIA NeMo Evaluator service provides model evaluation capabilities through a REST API. Weave integrates with this service through the `NvidiaNeMoEvaluatorScorer` class.

### Prerequisites

To use the NeMo Evaluator scorer, you'll need:

- Access to a NeMo Evaluator service endpoint
- Access to a NeMo Datastore service endpoint 
- Valid authentication tokens for both services
- A namespace and repository name for storing evaluation data

### Basic Usage

There are three main ways to use the NeMo Evaluator scorer:

1. Direct scoring with a new configuration and target
2. Scoring using existing configuration and target
3. Using it within a Weave evaluation

#### Direct Scoring with New Configuration

This approach creates a new configuration and target for the evaluation and utilizes NeMo Evaluator's LLM as a judge functionality:

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    ```python
    import weave
    
    @weave.op()
    def run_scorer():
      # Initialize the scorer with service details and judge configuration
      nemo_eval_scorer = NvidiaNeMoEvaluatorScorer(
        evaluator_url="http://0.0.0.0:7331",
        datastore_url="http://0.0.0.0:3000", 
        namespace = "temp-wv-ns",
        repo_name = "weave-ds",
        judge_prompt_template=prompt_messages,
        judge_metrics=metrics,
        judge_url="https://integrate.api.nvidia.com/v1",
        judge_model_id="meta/llama-3.3-70b-instruct",
        judge_api_key="YOUR_API_KEY"
      )

      # Score a single output
      output = "This movie truly sucked"
      score = nemo_eval_scorer.score(output)
      return score
    ```
  </TabItem>
</Tabs>

#### Using Existing Configuration and Target

If you already have a configuration and target set up in the NeMo Evaluator service:

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    ```python
    @weave.op()
    def run_scorer_w_config_target():
      # Initialize scorer with existing configuration and target
      nemo_eval_scorer = NvidiaNeMoEvaluatorScorer(
        evaluator_url="http://0.0.0.0:7331",
        datastore_url="http://0.0.0.0:3000",
        namespace = "temp-wv-ns",
        repo_name = "weave-ds",
        configuration_name="eval-config-weave-ds-KNH1ABNO",
        target_name="eval-target-weave-ds-KNH1ABNO"
      )

      score = nemo_eval_scorer.score()
      return score
    ```
  </TabItem>
</Tabs>

Note in this approach we do not pass anything to the score method, the Scorer is simply serving as the trigger point for the evaluation and will register with Weave aggregate results.

#### Using Within a Weave Evaluation

The scorer can be used as part of a Weave evaluation to score multiple outputs:

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    ```python
    @weave.op()
    async def run_evaluation():
      # Initialize the scorer
      nemo_eval_scorer = NvidiaNeMoEvaluatorScorer(
        evaluator_url="http://0.0.0.0:7331",
        datastore_url="http://0.0.0.0:3000",
        namespace = "temp-wv-ns",
        repo_name = "weave-ds",
        judge_prompt_template=prompt_messages,
        judge_metrics=metrics,
        judge_url="https://integrate.api.nvidia.com/v1",
        judge_model_id="meta/llama-3.3-70b-instruct",
        judge_api_key="YOUR_API_KEY"
      )

      # Create dataset with multiple outputs to evaluate
      dataset = weave.Dataset(rows = [
        {"output": "This movie truly sucked"}, 
        {"output": "This movie was great"}
      ])
      
      # Run evaluation
      eval = weave.Evaluation(dataset=dataset, scorers=[nemo_eval_scorer])
      results = await eval.evaluate(model)
      return results
    ```
  </TabItem>
</Tabs>

The scorer will automatically handle:
- Creating/managing evaluation configurations
- Managing evaluation targets
- Uploading datasets
- Running evaluation jobs
- Retrieving and processing results

:::note
Remember to replace placeholder values like `YOUR_API_KEY` with your actual credentials.
:::

