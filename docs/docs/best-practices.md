# Best Practices on instrumenting your code

Adding weave to any codebase can be very powerful, enabling you to keep an eye on inputs and outputs and disentangling complex workflows by exposing intermediate results.

## Simple Weave instrumentation

Let's start by instrumenting a simple function. We will use the `weave.op` decorator to instrument the function.

```python
def compute_some_values(a: int, b: int, coolness: str):
    "Simple function to compute some values"
    total = a + b
    is_divisible = a % b == 0
    return coolness, total, is_divisible
```

We need to add the `weave.op` decorator to the function to instrument it.

```python
@weave.op
def compute_some_values(a: int, b: int, coolness: str):
    "Simple function to compute some values"
    total = a + b
    is_divisible = a % b == 0
    return coolness, total, is_divisible
```

 Also, if we want the output to be stored and rendered on the UI on individual columns, we need to return a dict with the name of each attribute.

 ![](./imgs/simple_trace.png)

 As you can see, the output gets rendered as a list in the `output` column. We can unpack the list to render the output on individual columns. To do so, we need to return a dict with the name of each attribute.


```python
@weave.op
def compute_some_values(a: int, b: int, coolness: str):
    "Simple function to compute some values"
    total = a + b
    is_divisible = a % b == 0
    return {"coolness": coolness, "total": total, "is_divisible": is_divisible}
```
![](./imgs/dict_output_trace.png)

It is up to you if you want to change the output or not, but it may be useful to have the output in a dict. Also, most of the LLMs APIs return some kind of structured output, so it is a good idea to return a dict on other parts of your codebase too.

## Weave uses Pydantic

bla bla bla about Pydantic and how Weave uses Pydantic BaseModel everywhere

### weave.Object and weave.Model

A `weave.Model` is a `BaseModel` with ... some explanation about how to use it. We should be explicit about the `weave.Model` and attributes like `generate`, `predict`, `__call__`, etc...

### model_validator and delayed init

We need to document the `model_validator` decorator and when to use it. Typically, we use it to validate the data in the `__init__` method of a Pydantic BaseModel. For LLM use cases this is a good place to define the client or load the model weights.

Let's consider the following example:

```python
import json
import openai
import weave

class LLMModel(weave.Model):
    model_name: str
    prompt_template: str

    @weave.op()
    async def predict(self, sentence: str) -> dict:
        client = openai.AsyncClient()

        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "user", "content": self.prompt_template.format(sentence=sentence)}
            ],
        )
        return response.choices[0].message.content
```
Everytime we call `predict`, we create a new `openai.AsyncClient`. This is not efficient and can lead to a problems when we have a lot of requests to the model and the way Python handles processes. An alternative to this, is using the `PrivateAttr` annotation. As a `weave.Model` is a subclass of `pydantic.BaseModel`, we can use the `PrivateAttr` annotation to create the client before the model is initialized. You will need to name the attribute with an underscore to avoid name clashing with the model attributes.

```python
import json
import openai
import weave
# highlight-next-line
from pydantic import PrivateAttr

class LLMModel(weave.Model):
    model_name: str
    prompt_template: str
    # highlight-next-line
    _client: openai.AsyncClient = PrivateAttr(default_factory=openai.AsyncClient)
    
    @weave.op()
    async def predict(self, topic: str) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "user", "content": self.prompt_template.format(topic=topic)}
            ],
        )
        return response.choices[0].message.content
```
This way, the client becomes a model attribute and we can reuse the client to make requests to the API.
- The `default_factory` is a function that returns a default value for the attribute, in this case, a new `openai.AsyncClient`.

### Hugging Face model

When you need to intitialize attributes that depends on the input, for instance when loading a model and the tokenizer, you can use the `model_post_init` method. Here you can define the logic to load the model and the tokenizer.

 This is a good idea as you want to know exactly what is being sent to the model before tokenization.

When using Hugging Face and `weave.Model` you will want to use `model_post_init` on the step where you load the model weights and tokenizer. A simple example of this is the following:

```python
import weave
from pydantic import PrivateAttr
from transformers import LlamaForCausalLM, LlamaTokenizerFast
class LlamaModel(weave.Model):
    """A model class for MetaAI-LLama models"""
    model_id: str
    temperature: float = 0.5
    max_new_tokens: int = 128

    _model: LlamaForCausalLM = PrivateAttr()
    _tokenizer: LlamaTokenizerFast = PrivateAttr()

    def model_post_init(self, __context):
        self._model = LlamaForCausalLM.from_pretrained(self.model_id)
        self._tokenizer = LlamaTokenizerFast.from_pretrained(self.model_id)

    @weave.op
    def format_prompt(self, messages: list[dict[str, str]]):
        "A simple function to apply the chat template to the prompt"
        formatted_prompt = self._tokenizer.apply_chat_template(messages, tokenize=False)
        return formatted_prompt

    @weave.op()
    def predict(self, messages: list[dict[str, str]]) -> str:
        formatted_prompt = self.format_prompt(messages)
        tokenized_prompt = self._tokenizer.encode(formatted_prompt, return_tensors="pt").to(self._model.device)
        outputs = self._model.generate(
            tokenized_prompt,
            max_new_tokens=self.max_new_tokens,
            pad_token_id=self._tokenizer.eos_token_id,
            temperature=self.temperature,
            do_sample=True,
        )
        generated_text = self._tokenizer.decode(outputs[0][len(tokenized_prompt[0]):], skip_special_tokens=True)
        return {"generated_text": generated_text}
```
Some explanation about the code above.
- We define model and tokenizer as private attributes, this way Pydantic will not try to validate them.
- In this code we have a `model_post_init` that loads the model and the tokenizer.
- We have a `apply_chat_template` method that formats the prompt to be sent to the model. This is a good idea as you want to know exactly what is being sent to the model before tokenization.
- We have a `predict` method that generates a response from the model. Depending on the use case, you may want to return the raw output from the model or the decoded output.


