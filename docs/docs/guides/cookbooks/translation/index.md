# Translation using Large Language Models

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/translation-cookbook/examples/cookbooks/translation/translation_cookbook.ipynb)

Translating text accurately while preserving nuances and cultural context is a challenging task. This guide demonstrates how to implement a robust translation pipeline using Large Language Models (LLMs) and Weave, a powerful framework for building, tracking, and evaluating LLM applications. By combining the effectiveness of LLMs with Weave's robust tooling, you'll learn to create a translation pipeline that produces high-quality translations while gaining insights into the translation process.

![Final Evaluation](./media/eval_comparison.gif)

## Why use Weave for Translation?

In this tutorial, we'll use Weave to implement and evaluate a translation pipeline for the OPUS-100 dataset. You'll learn how to:

1. **Track your LLM pipeline**: Use Weave to automatically log inputs, outputs, and intermediate steps of your translation process.
2. **Evaluate LLM outputs**: Create rigorous, apples-to-apples evaluations of your translations using Weave's built-in tools.
3. **Build composable operations**: Combine and reuse Weave operations across different parts of your translation pipeline.
4. **Integrate seamlessly**: Add Weave to your existing Python code with minimal overhead.

By the end of this tutorial, you'll have created a translation pipeline that leverages Weave's capabilities for model serving, evaluation, and result tracking.

## Set up the environment

First, let's set up our environment and import the necessary libraries:

```python
import weave
from pydantic import BaseModel
import litellm
import instructor
from instructor import Mode
import sacrebleu
from Levenshtein import distance as levenshtein_distance

weave.init("translation-cookbook")
client = instructor.from_litellm(litellm.completion, mode=Mode.JSON)
```

We're using Weave to track our experiment and LiteLLM with Instructor for text generation. The `weave.init()` call sets up a new Weave project for our translation task.

## Define the TranslationPair model

We'll create a simple `TranslationPair` class to represent our data:

```python
class TranslationPair(BaseModel):
    source: str
    target: str
    target_language: str
```

This class encapsulates the source text, target (reference) translation, and target language, which will be the input to our translation pipeline.

## Implement the translation pipeline

Now, let's implement the core translation logic using Weave operations:

```python
@weave.op()
def translate_text(text: str, target_language: str, model: str = "gpt-3.5-turbo") -> str:
    prompt = f"""
    Translate the following English text into {target_language} with accuracy, fluency, and cultural appropriateness.

    Source text (English):
    {text}

    Provide only the {target_language} translation below:
    """
    
    response = client.chat.completions.create(
        model=model,
        response_model=Translation,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.translation

class TranslationPipeline(weave.Model):
    model: str = "gpt-3.5-turbo"
    
    @weave.op()
    def predict(self, pair: TranslationPair) -> dict:
        translation = translate_text(pair["source"], pair["target_language"], self.model)
        return {"translation": translation}
```

By using `@weave.op()` decorators, we ensure that Weave tracks the inputs, outputs, and execution of these functions.

## Implement evaluation metrics

To assess the quality of our translations, we'll implement both LLM-based and traditional metrics:

```python
@weave.op()
def llm_evaluate_translation(source: str, reference: str, hypothesis: str, target_language: str, model: str = "gpt-4") -> TranslationEvaluation:
    # LLM-based evaluation logic here

@weave.op()
def calculate_translation_metrics(reference: str, hypothesis: str) -> dict:
    # Calculate BLEU, CER, and TER scores
```

These evaluation functions use both an LLM and traditional metrics to assess the quality of the generated translations.

## Create a Weave Dataset and run evaluation

To evaluate our pipeline, we'll create a Weave Dataset and run an evaluation:

```python
# Create a Weave Dataset
dataset = weave.Dataset(
    name="opus100_en_fr_sample",
    rows=[
        {
            "pair": TranslationPair(
                source=item['translation']['en'],
                target=item['translation']['fr'],
                target_language="French"
            )
        }
        for item in load_dataset("opus100", "en-fr", split="test[:5]")
    ]
)

weave.publish(dataset)

# Run evaluation
evaluation = weave.Evaluation(dataset=dataset, scorers=[llm_translation_quality_scorer, calculate_translation_metrics_scorer])
models = [
    TranslationPipeline(model="gpt-4-mini"),
    TranslationPipeline(model="gpt-3.5-turbo")
]

results = {}
for model in models:
    model_results = await evaluation.evaluate(model)
    results[model.model] = model_results
```

This code creates a dataset with sample translation pairs, defines quality scorers, and runs an evaluation of our translation pipeline across multiple models.

## Conclusion

In this example, we've demonstrated how to implement a translation pipeline using Large Language Models and Weave. We've shown how to:

1. Create Weave operations for each step of the translation process
2. Wrap the pipeline in a Weave Model for easy tracking and evaluation
3. Implement custom evaluation metrics using both LLM-based and traditional approaches
4. Create a dataset and run an evaluation of the pipeline across multiple models

Weave's seamless integration allows us to track inputs, outputs, and intermediate steps throughout the translation process, making it easier to debug, optimize, and evaluate our LLM application.

For more information on Weave and its capabilities, check out the [Weave documentation](https://docs.wandb.ai/weave). You can extend this example to handle larger datasets, implement more sophisticated evaluation metrics, or integrate with other LLM workflows.
