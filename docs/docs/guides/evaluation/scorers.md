import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Using Scorers in Evaluation Workflows

In Weave, _scorers_ are used to evaluate AI outputs and return evaluation metrics. A scorer takes the AI's output, analyzes it, and return a dictionary of results. Scorers can use your input data as reference if needed and can also output extra information, such as explanations or reasonings from the evaluation.

## Types of scorers

The types of scorers available depend on whether you are using Python or Typescript.

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    Scorers are passed to a `weave.Evaluation` object during evaluation. There are three types of scorers available for Python:
    
    :::tip
    [Predefined scorers](../evaluation/predefined-scorers.md) are available for many common use cases. Before creating a custom scorer, check if one of the predefined scorers can address your use case.
    :::

    1. [Predefined scorers](../evaluation/predefined-scorers.md): Pre-built scorers designed for common use cases.
    2. [Function-based scorers](../evaluation/custom-scorers#function-based-scorers): Simple Python functions decorated with `@weave.op`.
    3. [Class-based scorers](../evaluation/custom-scorers.md#class-based-scorers): Python classes that inherit from `weave.Scorer` for more complex evaluations.

    Scorers must return a dictionary and can return multiple metrics, nested metrics and non-numeric values such as text returned from a LLM-evaluator about its reasoning. See the [Custom scorers page](../evaluation/custom-scorers.md) for more information.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    Scorers are special `ops` passed to a `weave.Evaluation` object during evaluation.

    Only [function-based scorers](../evaluation/custom-scorers.md#function-based-scorers) are available for Typescript. For [class-based](../evaluation/custom-scorers.md#class-based-scorers) and [predefined scorers](../evaluation/predefined-scorers.md), you must use Python.
  </TabItem>
</Tabs>

## Working with scorers

The following section provides information on how to:

- [Initialize scorers with local models](#initialize-scorers-with-local-models)
- [Initialize scorers with hosted models](#initialize-scorers-with-hosted-models)
- [Run scorers](#run-scorers)
- [Download model weights from W&B Artifacts](#download-model-weights-from-wb-artifacts)
- Access [input](#access-input-from-the-dataset-row) and [output](#access-output-from-the-dataset-row) from a datset row. 
- [Map column names](#map-column-names-with-column_map) if the `score` argument names don't match the column names in your dataset.
- [Access or customize a final summarization from the scorer](#final-summarization-of-the-scorer)

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    These are functions decorated with `@weave.op` that return a dictionary. They're great for simple evaluations like:

### Initialize scorers with local models

If you are running W&B customised models locally on a CPU or GPU, then you must load the model weights from disk to use scorers. In the following example, the model weights for the `HallucinationScorer` are downloaded from `model_path`:

```python
from weave.scorers import HallucinationScorer

hallu_scorer = HallucinationScorer(model_path="path/to/model/weights")
```

### Initializing scorers with hosted models

If you are calling W&B customized models that are being hosted on your own infrastructure, then you will need to pass your vLLM endpoint URL to the scorer:

```python
from weave.scorers import HallucinationScorer

hallu_scorer = HallucinationScorer(base_url="http://localhost:8000/v1")
```
    
  </TabItem>
</Tabs>

### Class-based Scorers

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    For more advanced evaluations, especially when you need to keep track of additional scorer metadata, try different prompts for your LLM-evaluators, or make multiple function calls, you can use the `Scorer` class.

Running a scorer does not depend on where the underlying model is being run. In the initialization examples above, a set of texts can be scored using the same code.

```python
scores = hallu_scorer.score(
  query="what is the capital of antartica?"
  context="Penguins love antartica."
  output="The capital of antartica is Quito"
)
```

### Download model weights from W&B Artifacts

Model weights are stored in [W&B Artifacts](https://docs.wandb.ai/guides/artifacts/). The Python example below shows how to download the model weights for the `ToxicityScorer`.

```python
from wandb import Api

api = Api()

model_artifact_path = f"weave-assets/weave-scorers/toxicity_scorer:v0"

model_name = model_artifact_path.split("/")[-1].replace(":", "_")
art = api.artifact(
    type="model",
    name=model_artifact_path,
)

local_model_path = f"models/toxicity_scorer"
art.download(local_model_path)
```

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>

  ### Access input from the dataset row
    
  If you want your scorer to use data from your dataset row, such as a `label` or `target` column, then you can make this available to the scorer by adding a `label` or `target` keyword argument to your scorer definition.

  For example, if you wanted to use a column called `label` from your dataset, then your scorer function (or `score` class method) would have a parameter list like this:

  ```python
  @weave.op
  def my_custom_scorer(output: str, label: int) -> dict:
      ...
  ```
   
  ### Access output from the dataset row

  To access the AI system's output, include an `output` parameter in your scorer function's signature.

  When a Weave `Evaluation` is run, the output of the AI system is passed to the `output` parameter. The `Evaluation` also automatically tries to match any additional scorer argument names to your dataset columns. If you are customizing your scorer arguments, or dataset columns is not feasible, you can use [column mapping](#mapping-column-names-with-column_map).

  ### Map column names with `column_map`

  Sometimes, the `score` argument names don't match the column names in your dataset. You can fix this using a `column_map`.

  If you're using a class-based scorer, pass a dictionary to the `column_map` attribute of `Scorer` when you initialise your scorer class. This dictionary maps your `score` method's argument names to the dataset's column names, in the order: `{scorer_keyword_argument: dataset_column_name}`.

  In the following example, the `text` argument in the `score` method will receive data from the `news_article` dataset column:

  ```python
  import weave
  from weave import Scorer

  # A dataset with news articles to be summarised
  dataset = [
      {"news_article": "The news today was great...", "date": "2030-04-20", "source": "Bright Sky Network"},
      ...
  ]

  # Scorer class
  class SummarizationScorer(Scorer):

      @weave.op
      def score(output, text) -> dict:
          """
              output: output summary from a LLM summarization system
              text: the text being summarised
          """
          ...  # evaluate the quality of the summary

  # create a scorer with a column mapping the `text` argument to the `news_article` data column
  scorer = SummarizationScorer(column_map={"text" : "news_article"})
  ```

  Another option to map your columns is to subclass the `Scorer` and overload the `score` method to map the columns explicitly.

  ```python
  import weave
  from weave import Scorer

  class MySummarizationScorer(SummarizationScorer):

      @weave.op
      def score(self, output: str, news_article: str) -> dict:  # Added type hints
          # overload the score method and map columns manually
          return super().score(output=output, text=news_article)
  ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    Scorers can access both the output from your AI system and the contents of the dataset row.

    You can easily access relevant columns from the dataset row by adding a `datasetRow` keyword argument to your scorer definition.

    ```typescript
    const myScorer = weave.op(
        ({modelOutput, datasetRow}) => {
            return modelOutput * 2 === datasetRow.expectedOutputTimesTwo;
        },
        {name: 'myScorer'}
    );
    ```
    
    ### Mapping column names with `columnMapping`
    
    :::important
    In TypeScript, this feature is currently available only from the `Evaluation` object, not individual scorers.
    :::

    Sometimes your `datasetRow` keys will not exactly match the scorer's naming scheme, but they are semantically similar. In this case, you can map the columns using the `Evaluation`'s `columnMapping` option.

    The mapping is always from the scorer's perspective. This means that the output is your `score` method's argument names to the dataset's column names, in the order: `{scorer_keyword_argument: dataset_column_name}`.


    ```typescript
    const myScorer = weave.op(
        ({modelOutput, datasetRow}) => {
            return modelOutput * 2 === datasetRow.expectedOutputTimesTwo;
        },
        {name: 'myScorer'}
    );

    const myEval = new weave.Evaluation({
        dataset: [{expected: 2}],
        scorers: [myScorer],
        columnMapping: {expectedOutputTimesTwo: 'expected'}
    });
    ```

  </TabItem>
</Tabs>

### Final summarization of the scorer

The following section describes how to output the standard final summarization from a scorer, alternatively, output a custom summarization.

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    During the evaluation, the score will be computed for each row of your dataset. To provide a final score for the evaluation, you can use the provided `auto_summarize` method depending on the returning type of the output. In the `auto_summarize` method: 

    - Averages are computed for numerical columns
    - Count and ratios are computed for boolean columns
    - Other column types are ignored

  #### Custom summarization

    If you need to customize how final scores are computed, you can override the `summarize` method on the `Scorer` class. The `summarize` function has the following input and output:

    - Input: A single list of dictionaries called `score_rows`, where each dictionary contains the scores returned by the `score` method for a single row of your dataset.
    - Output: A dictionary containing the summarized scores.

    Overriding the `summarize` method is useful when you need to score all rows before deciding on the final value of the score for the dataset. For a deeper dive, see the[`CorrectnessLLMJudge` tutorial](/tutorial-rag#optional-defining-a-scorer-class).

    In the following example, `summarize` is overrided to return `True` if the full output matches the target and `False` if not.

    ```python
    class MyBinaryScorer(Scorer):
        """
        Returns True if the full output matches the target, False if not
        """

        @weave.op
        def score(output, target):
            return {"match": if output == target}

        def summarize(self, score_rows: list) -> dict:
            full_match = all(row["match"] for row in score_rows)
            return {"full_match": full_match}
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    During evaluation, the scorer will be computed for each row of your dataset. To provide a final score, the `summarizeResults` function performs an aggregation depending on the output type.

    - Averages are computed for numerical columns
    - Count and fraction for boolean columns
    - Other column types are ignored

    Custom summarization is not currently supported for Typescript
  </TabItem>
</Tabs>

## Predefined Scorers

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    **Installation**

    To use Weave's predefined scorers you need to install some additional dependencies:

    ```bash
    pip install weave[scorers]
    ```

    **LLM-evaluators**

    The pre-defined scorers that use LLMs support the OpenAI, Anthropic, Google GenerativeAI and MistralAI clients. They also use `weave`'s `InstructorLLMScorer` class, so you'll need to install the [`instructor`](https://github.com/instructor-ai/instructor) Python package to be able to use them. You can get all necessary dependencies with `pip install "weave[scorers]"`

    ### `HallucinationFreeScorer`

    This scorer checks if your AI system's output includes any hallucinations based on the input data.

    ```python
    from weave.scorers import HallucinationFreeScorer

    llm_client = ... # initialize your LLM client here

    scorer = HallucinationFreeScorer(
        client=llm_client,
        model_id="gpt-4o"
    )
    ```

    **Customization:**

    - Customize the `system_prompt` and `user_prompt` attributes of the scorer to define what "hallucination" means for you.

    **Notes:**

    - The `score` method expects an input column named `context`. If your dataset uses a different name, use the `column_map` attribute to map `context` to the dataset column.

    Here you have an example in the context of an evaluation:

    ```python
    import asyncio
    from openai import OpenAI
    import weave
    from weave.scorers import HallucinationFreeScorer

    # Initialize clients and scorers
    llm_client = OpenAI()
    hallucination_scorer = HallucinationFreeScorer(
        client=llm_client,
        model_id="gpt-4o",
        column_map={"context": "input", "output": "other_col"}
    )

    # Create dataset
    dataset = [
        {"input": "John likes various types of cheese."},
        {"input": "Pepe likes various types of cheese."},
    ]

    @weave.op
    def model(input: str) -> str:
        return "The person's favorite cheese is cheddar."

    # Run evaluation
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[hallucination_scorer],
    )
    result = asyncio.run(evaluation.evaluate(model))
    print(result)
    # {'HallucinationFreeScorer': {'has_hallucination': {'true_count': 2, 'true_fraction': 1.0}}, 'model_latency': {'mean': 1.4395725727081299}}
    ```

    ---

    ### `SummarizationScorer`

    Use an LLM to compare a summary to the original text and evaluate the quality of the summary.

    ```python
    from weave.scorers import SummarizationScorer

    llm_client = ... # initialize your LLM client here

    scorer = SummarizationScorer(
        client=llm_client,
        model_id="gpt-4o"
    )
    ```

    **How It Works:**

    This scorer evaluates summaries in two ways:

    1. **Entity Density:** Checks the ratio of unique entities (like names, places, or things) mentioned in the summary to the total word count in the summary in order to estimate the "information density" of the summary. Uses an LLM to extract the entities. Similar to how entity density is used in the Chain of Density paper, https://arxiv.org/abs/2309.04269

    2. **Quality Grading:** Uses an LLM-evaluator to grade the summary as `poor`, `ok`, or `excellent`. These grades are converted to scores (0.0 for poor, 0.5 for ok, and 1.0 for excellent) so you can calculate averages.

    **Customization:**

    - Adjust `summarization_evaluation_system_prompt` and `summarization_evaluation_prompt` to define what makes a good summary.

    **Notes:**

    - This scorer uses the `InstructorLLMScorer` class.
    - The `score` method expects the original text that was summarized to be present in the `input` column of the dataset. Use the `column_map` class attribute to map `input` to the correct dataset column if needed.

    Here you have an example usage of the `SummarizationScorer` in the context of an evaluation:

    ```python
    import asyncio
    from openai import OpenAI
    import weave
    from weave.scorers import SummarizationScorer

    class SummarizationModel(weave.Model):
        @weave.op()
        async def predict(self, input: str) -> str:
            return "This is a summary of the input text."

    # Initialize clients and scorers
    llm_client = OpenAI()
    model = SummarizationModel()
    summarization_scorer = SummarizationScorer(
        client=llm_client,
        model_id="gpt-4o",
    )
    # Create dataset
    dataset = [
        {"input": "The quick brown fox jumps over the lazy dog."},
        {"input": "Artificial Intelligence is revolutionizing various industries."}
    ]

    # Run evaluation
    evaluation = weave.Evaluation(dataset=dataset, scorers=[summarization_scorer])
    results = asyncio.run(evaluation.evaluate(model))
    print(results)
    # {'SummarizationScorer': {'is_entity_dense': {'true_count': 0, 'true_fraction': 0.0}, 'summarization_eval_score': {'mean': 0.0}, 'entity_density': {'mean': 0.0}}, 'model_latency': {'mean': 6.210803985595703e-05}}
    ```

    ---
  </TabItem>
</Tabs>
