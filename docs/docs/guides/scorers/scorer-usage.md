import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Working With Scorers

The following page provides information about working with scorers. You can use this page to learn how to:

- [Initialize scorers with local models](#initialize-scorers-with-local-models)
- [Initialize scorers with hosted models](#initialize-scorers-with-hosted-models)
- [Run scorers](#run-scorers)
- [Download model weights from W&B Artifacts](#download-model-weights-from-wb-artifacts)
- Access [input](#access-input-from-the-dataset-row) and [output](#access-output-from-the-dataset-row) from a datset row. 
- [Map column names](#map-column-names-with-column_map) if the `score` argument names don't match the column names in your dataset.
- [Access or customize a final summarization from the scorer](#final-summarization-of-the-scorer)

:::tip
Toggle between tabs to view code samples and details specific to Python or TypeScript.
:::

## Initialize scorers with local models

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    If you are running W&B customised models locally on a CPU or GPU, then you must load the model weights from disk to use scorers. In the following example, the model weights for the `HallucinationScorer` are downloaded from `model_path`:

    ```python
    from weave.scorers import HallucinationScorer

    hallu_scorer = HallucinationScorer(model_path="path/to/model/weights")
    ```
   </TabItem>
   <TabItem value="typescript" label="TypeScript">
        Check back for Typescript-specific information.
   </TabItem>
</Tabs>

## Initializing scorers with hosted models

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    If you are calling W&B customized models that are being hosted on your own infrastructure, then you will need to pass your [vLLM endpoint URL](https://docs.vllm.ai/en/latest/index.html) to the scorer:

    ```python
    from weave.scorers import HallucinationScorer

    hallu_scorer = HallucinationScorer(base_url="http://localhost:8000/v1")
    ```
   </TabItem>
   <TabItem value="typescript" label="TypeScript">
        Check back for Typescript-specific information.
   </TabItem>
</Tabs>

## Run scorers

Running a scorer does not depend on where the underlying model is being run. In the initialization examples above, a set of texts can be scored using the same code.

```python
scores = hallu_scorer.score(
  query="what is the capital of antartica?"
  context="Penguins love antartica."
  output="The capital of antartica is Quito"
)
```

## Download model weights from W&B Artifacts

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

## Access input and output from the dataset row

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    
  If you want your scorer to use data from your dataset row, such as a `label` or `target` column, then you can make this available to the scorer by adding a `label` or `target` keyword argument to your scorer definition.

  For example, if you wanted to use a column called `label` from your dataset, then your scorer function (or `score` class method) would have a parameter list like this:

  ```python
  @weave.op
  def my_custom_scorer(output: str, label: int) -> dict:
      ...
  ```

  To access the AI system's output, include an `output` parameter in your scorer function's signature.

  When a Weave `Evaluation` is run, the output of the AI system is passed to the `output` parameter. The `Evaluation` also automatically tries to match any additional scorer argument names to your dataset columns. If you are customizing your scorer arguments, or dataset columns is not feasible, you can use [column mapping](#mapping-column-names-with-column_map).

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
  </TabItem>
 </Tabs>   

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
  
  ## Map column names


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
    :::note

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

## Final summarization of the scorer

The following section describes how to output the standard final summarization from a scorer, alternatively, output a custom summarization.

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    During the evaluation, the score will be computed for each row of your dataset. To provide a final score for the evaluation, you can use the provided `auto_summarize` method depending on the returning type of the output. In the `auto_summarize` method: 

    - Averages are computed for numerical columns
    - Count and ratios are computed for boolean columns
    - Other column types are ignored

  ### Custom summarization

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

    Custom summarization not currently supported for Typescript

  </TabItem>
</Tabs>