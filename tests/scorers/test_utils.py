from typing import Any, Optional
from weave.scorers.utils import stringify


def generate_large_text(tokens: int = 100_000, pattern: Optional[str] = None) -> str:
    if pattern is None:
        pattern = (
            "The quick brown fox jumps over the lazy dog. "
            "A wizard's job is to vex chumps quickly in fog. "
            "Pack my box with five dozen liquor jugs. "
        )

    words_per_pattern = len(pattern.split())
    tokens_per_pattern = words_per_pattern * 1.5
    multiplier = int(tokens / tokens_per_pattern)

    text = pattern * max(1, multiplier)

    return text


def generate_context_and_output(
    total_tokens: int = 100_000,
    context_ratio: float = 0.5
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
