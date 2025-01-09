# Working with Amazon Bedrock

Amazon Bedrock provides easy access to foundation models from providers like Anthropic, AI21 Labs, and Stability AI with a single API. With Weights & Biases (W&B) Weave, you can log, debug, and evaluate your Bedrock models to streamline your LLM application development workflow.

Amazon Bedrock simplifies access to leading foundation models, while Weave helps you:
- **Log and debug**: Keep track of LLM inputs, outputs, and traces for better transparency.
- **Evaluate models**: Build rigorous, direct comparisons between models to identify the best fit for your use case.
- **Organize workflows**: Structure and analyze information from experimentation to production with minimal effort.

:::note
Do you want to test Weave on Bedrock without any setup? Try this [Google Colab](https://colab.research.google.com/drive/1-KOjL-jA25nRyMPwKJjMg3jqL51m6J2k?usp=sharing#scrollTo=db351094-c5b7-4194-af04-b4ddc85399c6).
:::

## Get started with Bedrock and Weave

To get started with Weave on Bedrock, complete the prerequisites and the basic example. Once you've completed the basic example, try the [advanced examples](#advanced-usage).

### Prerequisites

1. Ensure access to [Amazon Bedrock](https://aws.amazon.com/bedrock/) and [Weights & Biases](https://wandb.ai/)
2. Install `weave` and `boto3`:
    ```bash
    pip install weave boto3
    ```

### Basic example 

Once you've completed the [prerequisites](#prerequisites), you can start using Weave to log your Bedrock model interactions. In the following code example:

1. `weave.init `initializes a new project called `bedrock-weave`.
2. `generate_text()` calls a Bedrock text generation model specified by its `model_id` to process the given `prompt`, and returns the response body.
3. `weave.op()` logs all `generate_text()` to Weave.
4. The Mistral 7B model generates a vegan recipe for carbonara. 

```python
import json
import boto3
import weave

weave.init('bedrock-weave')

@weave.op() # <- just add this 😎

def generate_text(
    model_id: str, 
    prompt: str, 
    max_tokens: int=400,
    temperature: float=0.7,
) -> dict:
    # Check your region model access page. 
    # In this case, on us-east-1 region.
    # https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess
    bedrock = boto3.client(service_name='bedrock-runtime')

    body = json.dumps({
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
    })
    
    response = bedrock.invoke_model(body=body, modelId=model_id)

    response_body = json.loads(response.get('body').read())
    return response_body.get('outputs')

# Example usage: The Mistral 7B model for recipe generation
model_id = 'mistral.mistral-7b-instruct-v0:2'
# The required prompt format for Mistral instruct
prompt = """<s>[INST] Create a Vegan Carbonara Recipe[/INST] """

outputs = generate_text(model_id, prompt)

for index, output in enumerate(outputs):
    print(f"Output {index + 1}\n----------")
    print(f"Text:\n{output['text']}\n")
    print(f"Stop reason: {output['stop_reason']}\n")
```

When you run the code sample above, you'll see output similar to the output shown below:

```plaintext
Output 1
----------
Text:
 Vegan Carbonara Recipe:


Ingredients:
- 12 oz (340g) spaghetti or other long pasta
- 1/2 cup (120ml) unsweetened almond milk or cashew cream
- 1/2 cup (100g) nutritional yeast
- 1/3 cup (80g) cooked and mashed sweet potato or pumpkin
- 1 tbsp olive oil
- 1 cup (200g) steamed or roasted vegetables such as zucchini, broccoli, or asparagus
- 1/2 cup (100g) chopped mushrooms
- 1/2 cup (100g) chopped onion
- 1 clove garlic, minced
- 1/2 cup (100g) chopped walnuts or cashews, toasted
- 1/2 cup (100g) vegetable bacon or pancetta, cooked and crumbled (optional)
- Salt and freshly ground black pepper, to taste
- Red pepper flakes, for serving (optional)
- Fresh parsley or basil, for serving (optional)

Instructions:
1. Cook the pasta according to package instructions in salted water until al dente. Drain and set aside, reserving 1 cup of the pasta water.
2. In a blender or food processor, combine the almond milk or cashew cream, nutritional yeast, mashed sweet potato or pumpkin, and olive oil. Blend until smooth and creamy. Taste and adjust seasoning with salt and pepper as needed.
3. In a large skillet, sauté the chopped onion, garlic, and

Stop reason: length
```

To view the code sample [trace](../tracking/index.md) in Weave, navigate **Traces** in the W&B console. 

## Advanced Usage

The following sections describe build off the [basic example](#basic-example) and demonstrate various advanced use cases of Weave on Bedrock.

- [Log nested calls](#log-nested-calls)
- [Try different Bedrock models](#try-different-bedrock-models)
- [Translate documents using Anthropic Claude on Bedrock](#translate-documents-using-anthropic-claude-on-bedrock)

### Log nested calls

You can use Weave to log nested calls. In the following code example, Weave is used to log both the nested `format_prompt()` function and its parent `run()`, which uses `format_prompt()` to format a prompt for `generate_text()` (defined in the [basic example](#basic-example)) before printing the output.

```python
@weave.op()
def format_prompt(prompt: str) -> str:
    return f"""<s>[INST] {prompt}[/INST] """ 


@weave.op()
def run(prompt: str) -> None:
    prompt = format_prompt(prompt)

    outputs = generate_text(model_id, prompt, max_tokens=1000)
    
    for index, output in enumerate(outputs):
        print(f"Output {index + 1}\n----------")
        print(f"Text:\n{output['text']}\n")
        print(f"Stop reason: {output['stop_reason']}\n")
        
run("What clothes do I need to pack in winter for a trip to Chamonix?")

```

To view the code sample [trace](../tracking/index.md) in Weave, navigate **Traces** in the W&B console. 

### Try different Bedrock models

You can easily switch between Bedrock models by changing the `model_id`. The following partial code example shows how to modify the `model_id` in the [basic example](#basic-example) to call the Mixtral-8x7B model.

:::note
Switching Bedrock models may require that you format your prompt differently. In this case, both models share the same prompt structure, so there is no need to modify.
:::

```python
model_id = 'mistral.mixtral-8x7b-instruct-v0:1'

prompt = """<s>[INST] Create a Vegan Carbonara Recipe[/INST] """

outputs = generate_text(model_id, prompt, max_tokens=1000)

for index, output in enumerate(outputs):
    print(f"Output {index + 1}\n----------")
    print(f"Text:\n{output['text']}\n")
    print(f"Stop reason: {output['stop_reason']}\n")
```

### Translate documents using Anthropic Claude on Bedrock

This section describes how to use Anthropic Claude on Bedrock to translate Markdown content, all while tracking everything in Weave. The following code sample:

1. Defines a `system_prompt` that instructs Anthropic Claude on how it should translate the Markdown chunk contained in `human_prompt`.
2. Defines a `human_prompt` which instructs Claude to translate a Markdown chunk according to the rules outlined in `system_prompt`.
3. Defines a dataclass `PromptTemplate` containing:
   - `system_prompt`
   - `human_prompt` 
   - The desired `translation` language
   - A function `format_claude()`, tracked in Weave, that formats the prompt for Anthropic models,
4. Defines a Weave Model called `ClaudeDocTranslator`, tracked in Weave, that uses `anthropic.claude-3-sonnet` to perform the tranlation.


```python
from pathlib import Path
from dataclasses import dataclass

system_prompt = """
# Instructions

You are a documentation translation assistant from English to {output_language}. We are translating valid docusaurus flavored markdown. Some rules to remember:

- Do not add extra blank lines.
- The results must be valid docusaurus markdown
- It is important to maintain the accuracy of the contents but we don't want the output to read like it's been translated. So instead of translating word by word, prioritize naturalness and ease of communication.
- In code blocks, just translate the comments and leave the code as is.

## Formatting Rules

Do not translate target markdown links. Never translate the part of the link inside (). For instance here [https://wandb.ai/site](https://wandb.ai/site) do not translate anything, but on this, you should translate the [] part:
[track metrics](./guides/track), [create logs](./guides/artifacts).
"""

human_prompt = """
Here is a chunk of documentation in docusaurus Markdown format to translate. Return the translation only, without adding anything else. 
<Markdown start>
{md_chunk}
<End of Markdown>
"""

@dataclass
class PromptTemplate:
    system_prompt: str
    human_prompt: str
    language: str
    
    @weave.op() 
    def format_claude(self, md_chunk):
        "A formatting function for Anthropic models"
        system_prompt = self.system_prompt.format(output_language=self.language)
        human_prompt = self.human_prompt.format(md_chunk=md_chunk)
        messages = [{"role":"user", "content":human_prompt}]
        return system_prompt, messages

class ClaudeDocTranslator(Model):
    model_id: str='anthropic.claude-3-sonnet-20240229-v1:0'
    max_tokens: int=2048
    prompt_template: PromptTemplate

    @weave.op()
    def translate(self, path: Path):
        with open(path) as f:
            doc = f.read()
        system_prompt, messages = self.prompt_template.format_claude(doc)
        return generate_text(self.model_id, messages)

translator = ClaudeDocTranslator(prompt_template=PromptTemplate(...))
translator.translate(Path('./docs/example.md'))
```

