# Evaluators

TODO:
- Why use Scorers (re-use?)
- Explain columm map
    column_map: A `scorer parameter name : dataset column name` mapping.
    
    This summarization scorer expects the input column in the dataset to be named "input" \
        and the output column in the dataset to be named "summary".
        You can specify a different mapping in the `column_map` argument. For example, \
        if your dataset contains columns "news_article" and "news_summary" then you can \
        specify `column_map={"input": "news_article", "output": "news_summary"}`.

## LLM-powered Evaluators

### Hallucination Scorer

A Scorer that uses an LLM to determine if the model output contains any hallucinations
based on the input data.

Note:
    - The meaning of "hallucination" can vary from person to person, you will likely want to 
    customize the `system_prompt` and `user_prompt` to fit your specific needs.
    - This Scorer uses the `InstructorLLMScorer` class to generate structured outputs from the LLM 
    provider's response; you will have to install the `instructor` python package to use it.

Attributes:
    system_prompt (str): The prompt describing the task, defines what a "hallucination" is.
    user_prompt (str): The string template to pass the input and output data. The template must 
    contain placeholders for both `input_data` and `output`.

### Summarization Scorer


## Programmatic Evaluators


### ValidJSONScorer

Validate whether a string is valid JSON.

```
from weave.scorers import ValidJSONScorer
```