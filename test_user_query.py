"""Test script to verify W&B inference configuration works."""

import os

# Set a test API key for verification
os.environ["WANDB_API_KEY"] = os.environ.get("WANDB_API_KEY", "test-key")
os.environ["GOOGLE_API_KEY"] = os.environ.get("GOOGLE_API_KEY", "test-google-key")

from weave.analytics.clustering import get_llm_kwargs


def test_gemini_model():
    """Test Gemini model configuration."""
    kwargs = get_llm_kwargs("gemini/gemini-2.5-flash")
    print("Gemini model kwargs:")
    print(f"  model: {kwargs['model']}")
    print(
        f"  api_key: {'*' * 8}...{kwargs['api_key'][-4:] if len(kwargs['api_key']) > 4 else '****'}"
    )
    print(f"  api_base: {kwargs.get('api_base', 'default')}")
    assert kwargs["model"] == "gemini/gemini-2.5-flash"
    assert "api_base" not in kwargs  # Gemini uses default
    print("✓ Gemini model test passed\n")


def test_wandb_inference_model():
    """Test W&B inference model configuration."""
    kwargs = get_llm_kwargs("wandb/meta-llama/Llama-4-Scout-17B-16E-Instruct")
    print("W&B inference model kwargs:")
    print(f"  model: {kwargs['model']}")
    print(
        f"  api_key: {'*' * 8}...{kwargs['api_key'][-4:] if len(kwargs['api_key']) > 4 else '****'}"
    )
    print(f"  api_base: {kwargs.get('api_base', 'default')}")
    # W&B models should be converted to openai/ format
    assert kwargs["model"] == "openai/meta-llama/Llama-4-Scout-17B-16E-Instruct"
    assert kwargs["api_base"] == "https://api.inference.wandb.ai/v1"
    print("✓ W&B inference model test passed\n")


def test_openai_model():
    """Test OpenAI model configuration."""
    os.environ["OPENAI_API_KEY"] = "test-openai-key"
    kwargs = get_llm_kwargs("openai/gpt-4o")
    print("OpenAI model kwargs:")
    print(f"  model: {kwargs['model']}")
    print(
        f"  api_key: {'*' * 8}...{kwargs['api_key'][-4:] if len(kwargs['api_key']) > 4 else '****'}"
    )
    print(f"  api_base: {kwargs.get('api_base', 'default')}")
    assert kwargs["model"] == "openai/gpt-4o"
    assert "api_base" not in kwargs  # OpenAI uses default
    print("✓ OpenAI model test passed\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing W&B Inference Configuration")
    print("=" * 60 + "\n")

    test_gemini_model()
    test_wandb_inference_model()
    test_openai_model()

    print("=" * 60)
    print("All tests passed! W&B inference is properly configured.")
    print("=" * 60)


if __name__ == "__main__":
    main()
