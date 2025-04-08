import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Weave Local Scorers

<a target="_blank" href="https://colab.research.google.com/github/wandb/examples/blob/master/weave/docs/scorers_local_weave_scorers.ipynb">
<img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/>
</a>

Weave's local scorers are a suite of small language models that run locally on your machine with minimal latency. These models evaluate the safety and quality of your AI system’s inputs, context, and outputs.

Some of these models are fine-tuned by Weights & Biases, while others are state-of-the-art open-source models trained by the community. Weights & Biases (W&B) Reports were used for training and evaluation. You can find the full details in this [list of W&B Reports](https://wandb.ai/c-metrics/weave-scorers/reports/Weave-Scorers-v1--VmlldzoxMDQ0MDE1OA).

The model weights are publicly available in W&B Artifacts, and are automatically downloaded when you instantiate the scorer class. The artifact paths can be found here if you'd like to download them yourself: `weave.scorers.default_models`

The object returned by these scorers contains a `passed` boolean attribute indicating whether the input text is safe or high quality, as well as a `metadata` attribute that contains more detail such as the raw score from the model.

:::tip
While local scorers can be run on CPUs and GPUs, use GPUs for best performance.  
:::

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>

    ## Prerequisites

    Before you can use Weave local scorers, install additional dependencies:

    ```bash
    pip install weave[scorers]
    ```

    ## Select a scorer

    The following local scorers are available. Select a scorer based on your use case.

    | Scorer                           | Scenario                                                                                                                                                                      |
    |----------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
    | [WeaveToxicityScorerV1](#weavetoxicityscorerv1)                  | Identify toxic or harmful content in your AI system's inputs and outputs, including hate speech or threats.                                                       |
    | [WeaveBiasScorerV1](#weavebiasscorerv1)                          | Detect biased or stereotypical content in your AI system's inputs and outputs. Ideal for reducing harmful biases in generated text.                               |
    | [WeaveHallucinationScorerV1](#weavehallucinationscorerv1)       | Identify whether your RAG system generates hallucinations in its output based on the input and context provided.                                                  |
    | [WeaveContextRelevanceScorerV1](#weavecontextrelevancescorerv1) | Measure whether the AI system's output is relevant to the input and context provided.                                                                             |
    | [WeaveCoherenceScorerV1](#weavecoherencescorerv1)                | Evaluate the coherence and logical structure of the AI system's output.                                                                                           |
    | [WeaveFluencyScorerV1](#weavefluencyscorerv1)                    | Measure whether the AI system's output is fluent.                                                                                                                  |
    | [WeaveTrustScorerV1](#weavetrustscorerv1)                        | An aggregate scorer that leverages the toxicity, hallucination, context relevance, fluency, and coherence scorers.                                                |
    | [PresidioScorer](#presidioscorer)                                | Detect Personally Identifiable Information (PII) in your AI system's inputs and outputs using the Presidio library from Microsoft.                                |

    ## `WeaveBiasScorerV1`

    This scorer assesses gender and race/origin bias along two dimensions:
        
        - Race and Origin: Racism and bias against a country or region of origin, immigration status, ethnicity, etc.
        - Gender and Sexuality: Sexism, misogyny, homophobia, transphobia, sexual harassment, etc.

    `WeaveBiasScorerV1` uses a fine-tuned [deberta-small-long-nli](https://huggingface.co/tasksource/deberta-small-long-nli) model. For more details on the model, dataset, and calibration process, see the [WeaveBiasScorerV1 W&B Report](https://wandb.ai/c-metrics/bias-benchmark/reports/Bias-Scorer--VmlldzoxMDM2MTgzNw).

    ### Usage notes 

    - The `score` method expects a string to be passed to the `output` parameter. 
    - A higher score means that there is a stronger prediction of bias in the text.
    - The `threshold` parameter is set but can also be overridden on initialization.
    
    ### Usage example

    ```python
    import weave
    from weave.scorers import WeaveBiasScorerV1

    bias_scorer = WeaveBiasScorerV1()
    result = bias_scorer.score(output="Martian men are terrible at cleaning")

    print(f"The text is biased: {not result.passed}")
    print(result)
    ```

    ---

    ## `WeaveToxicityScorerV1`

    This scorer assesses the input text for toxicity along five dimensions:
    
        - Race and Origin: Racism and bias against a country or region of origin, immigration status, ethnicity, etc.
        - Gender and Sexuality: Sexism, misogyny, homophobia, transphobia, sexual harassment, etc.
        - Religious: Bias or stereotypes against someone's religion.
        - Ability: Bias related to someone's physical, mental, or intellectual ability or disability.
        - Violence and Abuse: Overly graphic descriptions of violence, threats of violence, or incitement of violence.
    
    The `WeaveToxicityScorerV1` uses the open source [Celadon](https://huggingface.co/PleIAs/celadon) model from PleIAs. For more information, see the [WeaveToxicityScorerV1 W&B Report](https://wandb.ai/c-metrics/toxicity-benchmark/reports/Toxicity-Scorer--VmlldzoxMDMyNjc0NQ).

    ### Usage notes

    - The `score` method expects a string to be passed to the `output` parameter. 
    - The model returns scores from `0` to `3` across five different categories: 
      - If the sum of these scores is above `total_threshold` (default value `5`), the input is flagged as toxic. 
      - If any single category has a score higher than `category_threshold` (default `2`), the input is flagged as toxic.
    - To make filtering more aggressive, override `category_threshold` or `total_threshold` during initialization.

    ### Usage example

    ```python
    import weave
    from weave.scorers import WeaveToxicityScorerV1

    toxicity_scorer = WeaveToxicityScorerV1()
    result = toxicity_scorer.score(output="people from the south pole of Mars are the worst")

    print(f"Input is toxic: {not result.passed}")
    print(result)
    ```

    ---

    ## `WeaveHallucinationScorerV1`

    This scorer checks if your AI system's output contains any hallucinations based on the input data.

    The `WeaveHallucinationScorerV1` uses the open source [HHEM 2.1 model](https://huggingface.co/vectara/hallucination_evaluation_model) from Vectara. For more information, see the [WeaveHallucinationScorerV1 W&B Report](https://wandb.ai/c-metrics/hallucination/reports/Hallucination-Scorer--VmlldzoxMDM3NDA3MA).

    ### Usage notes

    - The `score` method expects values to be passed to the `query` and `output` parameters.  
    - The context should be passed to the `output` parameter (as a string or list of strings).  
    - A higher output score means a stronger prediction of hallucination in the output.
    - The `threshold` parameter is set but can be overridden on initialization.

    ### Usage example 

    ```python
    import weave
    from weave.scorers import WeaveHallucinationScorerV1

    hallucination_scorer = WeaveHallucinationScorerV1()

    result = hallucination_scorer.score(
        query="What is the capital of Antarctica?",
        context="People in Antarctica love the penguins.",
        output="While Antarctica is known for its sea life, penguins aren't liked there."
    )

    print(f"Output is hallucinated: {not result.passed}")
    print(result)
    ```

    ---

    ## `WeaveContextRelevanceScorerV1`

    This scorer is designed to be used when evaluating RAG systems. It scores the relevance of the context to the query.

    The `WeaveContextRelevanceScorerV1` uses a fine-tuned [deberta-small-long-nli](https://huggingface.co/tasksource/deberta-small-long-nli) model from tasksource. For more details, see the [WeaveContextRelevanceScorerV1 W&B Report](https://wandb.ai/c-metrics/context-relevance-scorer/reports/Context-Relevance-Scorer--VmlldzoxMDYxNjEyNA).

    ### Usage notes

    - The `score` method expects values for `query` and `output`.  
    - The context should be passed to the `output` parameter (string or list of strings).
    - A higher score means a stronger prediction that the context is relevant to the query.
    - You can pass `verbose=True` to the `score` method to get per-chunk scores.

    ### Usage example

    ```python
    import weave
    from weave.scorers import WeaveContextRelevanceScorerV1

    context_relevance_scorer = WeaveContextRelevanceScorerV1()

    result = context_relevance_scorer.score(
        query="What is the capital of Antarctica?",
        output="The Antarctic has the happiest penguins."  # context is passed to the output parameter
    )

    print(f"Output is relevant: {result.passed}")
    print(result)
    ```

    ## `WeaveCoherenceScorerV1`

    This scorer checks whether the input text is coherent.

    The `WeaveCoherenceScorerV1` uses a fine-tuned [deberta-small-long-nli](https://huggingface.co/tasksource/deberta-small-long-nli) model from tasksource. For more information, see the [WeaveCoherenceScorerV1 W&B Report](https://wandb.ai/c-metrics/coherence_scorer/reports/Coherence-Scorer--VmlldzoxMDI5MjA1MA).

    ### Usage notes

    - The `score` method expects text to be passed to the `query` and `output` parameters.
    - A higher output score means a stronger prediction of coherence.

    ### Usage example 

    ```python
    import weave
    from weave.scorers import WeaveCoherenceScorerV1

    coherence_scorer = WeaveCoherenceScorerV1()

    result = coherence_scorer.score(
        query="What is the capital of Antarctica?",
        output="but why not monkey up day"
    )

    print(f"Output is coherent: {result.passed}")
    print(result)
    ```

    ---

    ## `WeaveFluencyScorerV1`

    This scorer checks whether the input text is fluent—that is, easy to read and understand, similar to natural human language. It evaluates grammar, syntax, and overall readability.

    The `WeaveFluencyScorerV1` uses a fine-tuned [ModernBERT-base](https://huggingface.co/answerdotai/ModernBERT-base) model from AnswerDotAI. For more information, see the [WeaveFluencyScorerV1 W&B Report](https://wandb.ai/c-metrics/fluency-eval/reports/Fluency-Scorer--VmlldzoxMTA3NzE2Ng).

    ### Usage notes

    - The `score` method expects text to be passed to the `output` parameter.
    - A higher output score indicates higher fluency.

    ### Usage example 

    ```python
    import weave
    from weave.scorers import WeaveFluencyScorerV1

    fluency_scorer = WeaveFluencyScorerV1()

    result = fluency_scorer.score(
        output="The cat did stretching lazily into warmth of sunlight."
    )

    print(f"Output is fluent: {result.passed}")
    print(result)
    ```

    ---

    ## `WeaveTrustScorerV1`

    The `WeaveTrustScorerV1` is a composite scorer for RAG systems that evaluates the trustworthiness of model outputs by grouping other scorers into two categories: Critical and Advisory. Based on the composite score, it returns a trust level:

    - `high`: No issues detected  
    - `medium`: Only Advisory issues detected  
    - `low`: Critical issues detected or input is empty  

    Any input that fails a Critical scorer results in a `low` trust level. Failing an Advisory scorer results in `medium`.

    - **Critical:**
        - `WeaveToxicityScorerV1`
        - `WeaveHallucinationScorerV1`
        - `WeaveContextRelevanceScorerV1`

    - **Advisory:**
        - `WeaveFluencyScorerV1`
        - `WeaveCoherenceScorerV1`

    ### Usage notes

    - This scorer is designed for evaluating RAG pipelines.  
    - It requires `query`, `context`, and `output` keys for correct scoring.

    ### Usage example

    ```python
    import weave
    from weave.scorers import WeaveTrustScorerV1

    trust_scorer = WeaveTrustScorerV1()

    def print_trust_scorer_result(result):
        print()
        print(f"Output is trustworthy: {result.passed}")
        print(f"Trust level: {result.metadata['trust_level']}")
        if not result.passed:
            print("Triggered scorers:")
            for scorer_name, scorer_data in result.metadata['raw_outputs'].items():
                if not scorer_data.passed:
                    print(f"  - {scorer_name} did not pass")
        print()
        print(f"WeaveToxicityScorerV1 scores: {result.metadata['scores']['WeaveToxicityScorerV1']}")
        print(f"WeaveHallucinationScorerV1 scores: {result.metadata['scores']['WeaveHallucinationScorerV1']}")
        print(f"WeaveContextRelevanceScorerV1 score: {result.metadata['scores']['WeaveContextRelevanceScorerV1']}")
        print(f"WeaveCoherenceScorerV1 score: {result.metadata['scores']['WeaveCoherenceScorerV1']}")
        print(f"WeaveFluencyScorerV1: {result.metadata['scores']['WeaveFluencyScorerV1']}")
        print()

    result = trust_scorer.score(
        query="What is the capital of Antarctica?",
        context="People in Antarctica love the penguins.",
        output="The cat stretched lazily in the warm sunlight."
    )

    print_trust_scorer_result(result)
    print(result)
    ```

    ---

    ## `PresidioScorer`

    This scorer uses the [Presidio library](https://github.com/microsoft/presidio) to detect Personally Identifiable Information (PII) in your AI system's inputs and outputs.

    ### Usage notes

    - To specify specific entity types, such as emails or phone numbers, pass a list of Presidio entities to the `selected_entities` parameter. Otherwise, Presidio will detect all entity types in its default entities list.
    - To detect specific entity types, such as emails or phone numbers, pass a list to the `selected_entities` parameter.
    - You can pass custom recognizers via the `custom_recognizers` parameter as a list of `presidio.EntityRecognizer` instances.
    - To handle non-English input, use the `language` parameter to specify the language.

    ### Usage example

    ```python
    import weave
    from weave.scorers import PresidioScorer

    presidio_scorer = PresidioScorer()

    result = presidio_scorer.score(
        output="Mary Jane is a software engineer at XYZ company and her email is mary.jane@xyz.com."
    )

    print(f"Output contains PII: {not result.passed}")
    print(result)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    Weave local scorers are not available in TypeScript yet. Stay tuned!

    To use Weave scorers in TypeScript, see [function-based scorers](scorers#function-based-scorers).
  </TabItem>
</Tabs>
