---
title: Translation
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/translation_cookbook.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/translation_cookbook.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



# Translation using Large Language Models

Translating text accurately while preserving nuances and cultural context is a challenging task. This guide demonstrates how to implement a robust translation pipeline using Large Language Models (LLMs) and Weave, a powerful framework for building, tracking, and evaluating LLM applications. By combining the effectiveness of LLMs with Weave's robust tooling, you'll learn to create a translation pipeline that produces high-quality translations while gaining insights into the translation process.

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
!pip install -qU weave litellm datasets transformers pydantic set-env-colab-kaggle-dotenv instructor python-Levenshtein nltk
```


```python
import weave
from pydantic import BaseModel, Field
from set_env import set_env
from datasets import load_dataset
import litellm
import instructor
from instructor import Mode
from typing import List
import sacrebleu
from Levenshtein import distance as levenshtein_distance

set_env("WANDB_API_KEY")
set_env("OPENAI_API_KEY")

print("Weave version:", weave.__version__)
```


```python
weave.init("translation-cookbook")
# Patch OpenAI client with Instructor
client = instructor.from_litellm(litellm.completion, mode=Mode.JSON)
```

We're using Weave to track our experiment and LiteLLM with Instructor for text generation. The `weave.init()` call sets up a new Weave project for our translation task.

LiteLLM is a Python library that simplifies the integration of various Large Language Model (LLM) APIs, allowing seamless access to over 100 LLM services from different providers using a standardized OpenAI-like format.

Instructor, created by Jason Liu, is a powerful library that makes it easy to get structured data like JSON from LLMs, supporting a wide range of models and providing features like validation context, retries, and streaming responses

## Define the TranslationPair model

We'll create a simple `TranslationPair` class to represent our data:


```python
# Define TranslationPair model
class TranslationPair(BaseModel):
    source: str
    target: str
    target_language: str
```

This class encapsulates the source text, target (reference) translation, and target language, which will be the input to our translation pipeline.


```python
# Load a small sample of the OPUS-100 dataset
dataset = load_dataset("opus100", "en-fr", split="test[:5]")

# Create sample TranslationPair
sample_pair = TranslationPair(
    source=dataset[0]['translation']['en'],
    target=dataset[0]['translation']['fr'],
    target_language="French"
)
```

## Implement the translation pipeline

Now, let's implement the core translation logic using Weave operations:


```python
# Define structured output for translation
class Translation(BaseModel):
    translation: str

# Define structured output for translation evaluation
class TranslationEvaluation(BaseModel):
    adequacy: int = Field(..., ge=1, le=5)
    adequacy_explanation: str
    fluency: int = Field(..., ge=1, le=5)
    fluency_explanation: str
```


```python
@weave.op()
def translate_text(text: str, target_language: str, model: str = "gpt-3.5-turbo") -> str:
    prompt = f"""You are a highly skilled professional translator with expertise in both the source language (English) and the target language ({target_language}). Translate the following English text into {target_language} with accuracy, fluency, and cultural appropriateness.

Instructions:
1. Maintain the original meaning and tone of the text.
2. Use natural and idiomatic expressions in the target language.
3. Preserve any specialized terminology or proper nouns.
4. Adapt cultural references when necessary for the target audience.
5. Ensure grammatical correctness and appropriate style for the target language.
6. Do not add any explanations or comments to the translation.
7. Translate acronyms only if they have a standard equivalent in the target language.

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

By using `@weave.op()` decorators, we ensure that Weave tracks the inputs, outputs, and execution of these functions. This allows us to monitor the progress of our translation pipeline and evaluate its performance.

## Create a Weave Dataset and run evaluation

To evaluate our pipeline, we'll create a Weave Dataset and run an evaluation:


```python
# Create a Weave Dataset
weave_dataset = weave.Dataset(
    name="opus100_en_fr_sample",
    rows=[
        {
            "pair": TranslationPair(
                source=item['translation']['en'],
                target=item['translation']['fr'],
                target_language="French"
            )
        }
        for item in dataset
    ]
)

weave.publish(weave_dataset)
```

## Implement evaluation metrics

To assess the quality of our translations, we'll implement both LLM-based and traditional metrics:


```python
@weave.op()
def llm_evaluate_translation(source: str, reference: str, hypothesis: str, target_language: str, model: str = "gpt-4o") -> TranslationEvaluation:
    prompt = f"""
    Source (English): {source}
    Reference ({target_language}): {reference}
    Hypothesis ({target_language}): {hypothesis}

    Evaluate the translation based on the following criteria:
    1. Adequacy (1-5): How well does the translation convey the meaning of the source text?
       - Consider accuracy of information, preservation of nuances, and completeness.
    2. Fluency (1-5): How natural and fluent is the translation in the target language?
       - Consider grammar, word choice, idiomatic expressions, and overall readability.

    Additional aspects to consider:
    - Terminology consistency
    - Cultural appropriateness
    - Handling of proper nouns and acronyms
    - Preservation of tone and style

    Provide a score (1-5) and a brief explanation (max 50 words) for each criterion.
    """
        
    evaluation = client.chat.completions.create(
        model=model,
        response_model=TranslationEvaluation,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return evaluation


# Define the scorer function
@weave.op()
def llm_translation_quality_scorer(pair: TranslationPair, model_output: dict) -> dict:
    evaluation = llm_evaluate_translation(
        pair["source"],
        pair["target"],
        model_output["translation"],
        pair["target_language"]
    )
    return {
        "adequacy": evaluation.adequacy,
        "fluency": evaluation.fluency,
        "adequacy_explanation": evaluation.adequacy_explanation,
        "fluency_explanation": evaluation.fluency_explanation
    }
```


```python
@weave.op()
def calculate_translation_metrics(reference: str, hypothesis: str) -> dict:
    # BLEU score
    bleu = sacrebleu.corpus_bleu([hypothesis], [[reference]])
    
    # Character Error Rate (CER)
    cer = levenshtein_distance(reference, hypothesis) / max(len(reference), len(hypothesis))
    
    # Translation Edit Rate (TER)
    ter = sacrebleu.sentence_ter(hypothesis, [reference])
    
    return {
        "bleu": bleu.score,
        "cer": cer,
        "ter": ter.score
    }

@weave.op()
def calculate_translation_metrics_scorer(pair: TranslationPair, model_output: dict) -> dict:
    evaluation = calculate_translation_metrics(pair["source"], model_output["translation"])
    return evaluation


```

- **BLEU (Bilingual Evaluation Understudy)**:
  - Measures translation quality by comparing n-gram overlap between hypothesis and reference
  - Range: 0-100, higher is better
  - Limitations: Insensitive to meaning, favors shorter translations

- **CER (Character Error Rate)**:
  - Calculates the Levenshtein distance between hypothesis and reference at character level
  - Range: 0-1, lower is better
  - Useful for capturing minor errors and differences in spelling

- **TER (Translation Edit Rate)**:
  - Measures the number of edits required to transform hypothesis into reference
  - Range: 0-1 (or higher), lower is better
  - Accounts for insertions, deletions, substitutions, and shifts

These metrics provide complementary views of translation quality, capturing different aspects such as precision, character-level accuracy, and edit distance.

These evaluation functions use both an LLM and traditional metrics to assess the quality of the generated translations.


```python
# Run evaluation
evaluation = weave.Evaluation(dataset=weave_dataset, scorers=[llm_translation_quality_scorer, calculate_translation_metrics_scorer])

# Define multiple translation models
models = [
    TranslationPipeline(model="gpt-4o-mini"),
    TranslationPipeline(model="gpt-3.5-turbo")
]
```


```python
# Evaluate all models
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

