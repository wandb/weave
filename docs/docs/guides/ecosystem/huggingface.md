---
sidebar_position: 1
hide_table_of_contents: true
---


# Huggingface

Recording traces of LLM applications in a centralized database is crucial during both development and production phases. These traces are invaluable for debugging and for creating a dataset of challenging examples to test and enhance your application.

You can use models from the Hugging Face ecosystem with Weave to keep track of all your interactions and generate insights.

## Using a models locally

You have fine-tuned a model from the Hugging Face HUB a now you want to interact with it. You can start tracing your model by wrapping the model call with a `weave.op()`:

1. Using the `pipeline` API:
    ```python
    import weave
    from transformers import pipeline

    @weave.op()
    def generate(model_name: str, prompt: str, temperature: float = 0.7) -> str:
        messages = [
            {"role": "user", "content": prompt},
        ]
        pipe = pipeline("text-generation", model=model_name, temperature=temperature)
        return pipe(messages)
    ```
    
    this is very inefficient as the model is instantiated every time the function is called.

2. Explicitly using the `AutoModel` and `generate` methods:
    ```python
    import weave
    from transformers import AutoModel, AutoTokenizer

    model = AutoModel.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    @weave.op
    def generate(prompt: str, temperature: float = 0.7) -> str:
        messages = [{"role": "user", "content": prompt}]
        input_ids = tokenizer.apply_chat_template(messages, return_tensors="pt").to(model.device)
        output = model.generate(input_ids, temperature=temperature, do_sample=True)
        return outputs[0][input_ids.shape[-1]:] # we remove the input from the generation
    ```

3. Explicitly using the `AutoModel` and `generate` methods:
    ```python
    import weave
    from transformers import AutoModel, AutoTokenizer

    model = AutoModel.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    @weave.op
    def apply_chat_template(messages: str, tokenizer):
         formatted_prompt = tokenizer.apply_chat_template(messages, return_tensors="text")
         return formatted_prompt

    @weave.op
    def generate(prompt: str, temperature: float = 0.7) -> str:
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = apply_chat_template(messages, tokenizer)
        input_ids = tokenizer(formatted_prompt, return_tensors="pt").to(model.device)
        output = model.generate(input_ids, temperature=temperature, do_sample=True)
        return outputs[0][input_ids.shape[-1]:] # we remove the input from the generation
    ```

4. If you want to organize the model and parameters in a single `Model` class where you organize the loading of the checkpoints, the prompt formatting and the generation of the output, you can do so:

    ```python
    import weave
    from pydantic import model_validator
    from transformers import AutoModel
    from transformers import PeftModelForCausalLM, LlamaForCausalLM, LlamaTokenizerFast

    class LlamaModel(weave.Model):
        """A model class for MetaAI-LLama models"""
        model_id: str
        temperature: float = 0.5
        max_new_tokens: int = 128
        model: PeftModelForCausalLM | LlamaForCausalLM  # we may want to support LoRA fine-tunes
        tokenizer: LlamaTokenizerFast

        @model_validator(mode='before')
        def load_model_and_tokenizer(cls, v):
            "Pydantic validator to load the model and the tokenizer"
            model_id = v["model_id"]
            if model_id is None:
                raise ValueError("model_id is required")
            model = AutoModel.from_pretrained(model_id)
            tokenizer = LlamaTokenizerFast.from_pretrained(model_id)
            v["model"] = model
            v["tokenizer"] = tokenizer
            return v

        @weave.op()
        def format_prompt(self, messages: list[dict[str, str]]) -> str:
            "A simple function to apply the chat template to the prompt"
            return  self.tokenizer.apply_chat_template(messages, return_tensors="pt").to(self.model.device)

        @weave.op()
        def predict(self, messages: list[dict[str, str]]) -> str:
            tokenized_prompt = self.format_prompt(messages)
            outputs = self.model.generate(
                tokenized_prompt,
                max_new_tokens=self.max_new_tokens,
                pad_token_id=self.tokenizer.eos_token_id,
                temperature=self.temperature,
            )
            generated_text = self.tokenizer.decode(outputs[0][len(tokenized_prompt[0]):], skip_special_tokens=True)
            return {"generated_text": generated_text}
    ```

