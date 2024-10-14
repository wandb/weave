# Evaluation Metrics

We call evaluation metrics "Scorers",

TODO:
- Why use Scorers (re-use?)
- Explain columm_map
    column_map: A `scorer parameter name : dataset column name` mapping.
    
    This summarization scorer expects the input column in the dataset to be named "input" \
        and the output column in the dataset to be named "summary".
        You can specify a different mapping in the `column_map` argument. For example, \
        if your dataset contains columns "news_article" and "news_summary" then you can \
        specify `column_map={"input": "news_article", "output": "news_summary"}`.

## LLM-powered Evaluators

### HallucinationFreeScorer

A Scorer that uses an LLM to determine if the model output contains any hallucinations
based on the input data.

Note:
    - The meaning of "hallucination" can vary from person to person, you will likely want to 
    customize the `system_prompt` and `user_prompt` to fit your specific needs.
    - This Scorer uses the `InstructorLLMScorer` class to generate structured outputs from the LLM 
    provider's response; you will have to install the `instructor` python package to use it.
    - The `score` method expects the input column from the dataset to be named "context". It will use
    this data as the ground-truth to check hallucinations against. If your dataset column has a 
    different name, you can specify a different mapping using the `column_map` argument in the init 
    of HallucinationFreeScorer by passing `column_map={"context": "context"}`.

Attributes:
    system_prompt (str): The prompt describing the task, defines what a "hallucination" is.
    user_prompt (str): The string template to pass the input and output data. The template must 
    contain placeholders for both `{input_data}` and `{output}`.
    model_id (str): The LLM model name, depends on the LLM's providers to be used `client` being used.
    temperature (float): LLM temperature setting.
    max_tokens (int): Maximum number of tokens in the LLM's response.

Methods:
    score(output: str, context: str) -> HallucinationResponse:
        Analyzes the output to detect hallucinations based on the given context.

### SummarizationScorer

A Scorer that evaluates the quality of summaries in two ways:
    - using an LLM to calculate the entity density of the summary, similar to how entity density is
    used in the Chain of Density paper, https://arxiv.org/abs/2309.04269. This is a rough measure for
    how information-dense the summary is.
    - using another LLM evaluator to grade the summary quality from `poor`, `ok`, to `excellent`. These
    grades are then mapped to numerical scores, {`poor`: 0.0, `ok`: 0.5, `excellent`: 1.0}, in order to
    be able to calculate an average score across a dataset of summaries if needed.

To customise the LLM evaluator you can customise the `summarization_evaluation_system_prompt`and
`summarization_evaluation_prompt` attributes to be tailored your specific definition of what a good summary
should look like.

Note:
    - This Scorer uses the `InstructorLLMScorer` class to generate structured outputs from the LLM 
    provider's response; you will have to install the `instructor` python package to use it.
    - The `score` method expects the input column from the dataset to be named "input". If your dataset
    column has a different name, you can specify a different mapping using the `column_map` argument in the 
    init of SummarizationScorer by passing `column_map={"input": "news_article"}`.

Attributes:
    extraction_system_prompt (str): System prompt to extract the distinct entities in the input. Customising 
    this can help ensure that the LLM identifies the `entities` that you care about.
    extraction_prompt (str): Prompt template for entity extraction; must contain a `{text}` placeholder.
    summarization_evaluation_system_prompt (str): System prompt defining how to evaluate the quality of a summary.
        Asks an LLM to grade the summary from `poor`, `ok`, to `excellent` and provide a rationale for the grade.
    summarization_evaluation_prompt (str): Prompt template for summarization evaluation instruction; must contain 
        `{input}` and `{summary}` placeholders. 
    entity_density_threshold (float): Threshold for determining if a summary is sufficiently entity-dense.
    model_id (str): The LLM model name, depends on the LLM's providers to be used `client` being used.
    temperature (float): LLM temperature setting.
    max_tokens (int): Maximum number of tokens in the LLM's response.

Methods:
    extract_entities(text: str) -> List[str]:
        Uses an LLM to extract unique entities from the text.

    evaluate_summary(input: str, summary: str) -> SummarizationEvaluationResponse:
        Evaluates the quality of a summary using an LLM.

    score(input: str, output: str, **kwargs: Any) -> dict:
        Calculates summarization score and entity density score for the given input and output.


## Programmatic Evaluators

### ValidJSONScorer

Validate whether a string is valid JSON.

```
from weave.scorers import ValidJSONScorer
```