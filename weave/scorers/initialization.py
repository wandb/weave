"""Module to handle initialization of LLM-related dependencies."""


def check_litellm_installation() -> None:
    """Check if litellm is installed and raise an informative error if not."""
    try:
        from litellm import acompletion  # noqa: F401
    except ImportError:
        raise ImportError(
            "litellm is required to use the LLM-powered scorers, please install it with `pip install litellm`"
        )
    else:
        return
