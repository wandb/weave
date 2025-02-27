import os
import random
from typing import Optional, Union

import torch
from pydantic import BaseModel
from torch import Tensor

from weave.scorers.utils import download_model, stringify

# Model paths for various scorers
TINY_MODEL_PATHS = {
    "fluency_scorer": "c-metrics/weave-scorers/fluency_scorer_tiny:latest",
    "hallucination_scorer": "c-metrics/weave-scorers/hallucination_hhem_scorer_tiny:latest",
    "coherence_scorer": "c-metrics/weave-scorers/coherence_scorer_tiny:latest",
    "toxicity_scorer": "c-metrics/weave-scorers/toxicity_scorer_tiny:latest",
    "bias_scorer": "c-metrics/weave-scorers/bias_scorer_tiny:latest",
    "relevance_scorer": "c-metrics/weave-scorers/relevance_scorer_tiny:latest",
    "llamaguard_scorer": "c-metrics/weave-scorers/llamaguard_scorer_tiny:latest",
}


class TokenizedText(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    input_ids: Union[list[int], Tensor]
    attention_mask: Union[list[int], Tensor]


class RandomTokenizer:
    def __init__(self, seed: int = 42, vocab_size: int = 32_000):
        self.seed = seed
        self.vocab_size = vocab_size
        random.seed(self.seed)

    def __call__(self, text: str, return_tensors=None, **kwargs) -> list[list[int]]:
        tokenized_text = [random.randint(0, self.vocab_size - 1) for _ in text]
        attention_mask = [1] * len(tokenized_text)
        if return_tensors == "pt":
            tokenized_text = torch.tensor(tokenized_text).unsqueeze(0)
            attention_mask = torch.tensor(attention_mask).unsqueeze(0)
        return TokenizedText(input_ids=tokenized_text, attention_mask=attention_mask)


_default_pattern = (
    "The quick brown fox jumps over the lazy dog. "
    "A wizard's job is to vex chumps quickly in fog. "
    "Pack my box with five dozen liquor jugs. "
)


def generate_large_text(
    tokens: int = 100_000, pattern: Optional[str] = _default_pattern
) -> str:
    words_per_pattern = len(pattern.split())
    tokens_per_pattern = words_per_pattern * 1.5
    multiplier = int(tokens / tokens_per_pattern)

    text = pattern * max(1, multiplier)

    return text


def generate_context_and_output(
    total_tokens: int = 100_000, context_ratio: float = 0.5
) -> tuple[str, str]:
    context_tokens = int(total_tokens * context_ratio)
    output_tokens = total_tokens - context_tokens

    context = generate_large_text(context_tokens)
    output = generate_large_text(output_tokens)

    return context, output


def test_stringify():
    assert stringify("Hello, world!") == "Hello, world!"
    assert stringify(123) == "123"
    assert stringify([1, 2, 3]) == "[\n  1,\n  2,\n  3\n]"
    assert stringify({"a": 1, "b": 2}) == '{\n  "a": 1,\n  "b": 2\n}'


def test_generate_large_text():
    text = generate_large_text()
    assert len(text) > 0
    words = text.split()
    assert len(words) > 60000

    small_text = generate_large_text(1000)
    assert len(small_text) > 0
    small_words = small_text.split()
    assert len(small_words) > 600

    custom_text = generate_large_text(1000, pattern="Test pattern. ")
    assert len(custom_text) > 0
    assert "Test pattern" in custom_text


def test_generate_context_and_output():
    context, output = generate_context_and_output()
    assert len(context) > 0
    assert len(output) > 0
    context_words = context.split()
    output_words = output.split()
    assert len(context_words) > 30000
    assert len(output_words) > 30000

    context, output = generate_context_and_output(10000, context_ratio=0.8)
    context_words = context.split()
    output_words = output.split()
    assert len(context_words) > len(output_words)


def test_download_model_default_env_var():
    tiny_model_path = download_model(TINY_MODEL_PATHS["bias_scorer"])
    assert tiny_model_path.exists()


def test_download_model_custom_env_var():
    os.environ["WEAVE_SCORERS_DIR"] = "/tmp/weave-scorers"
    tiny_model_path = download_model(TINY_MODEL_PATHS["bias_scorer"])
    assert tiny_model_path.exists()
