from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from pydantic import Field, PrivateAttr, field_validator

import weave
from weave.scorers.utils import set_device

if TYPE_CHECKING:
    import torch
    from transformers.modeling_utils import PreTrainedModel
    from transformers.pipelines.base import Pipeline
    from transformers.tokenization_utils import PreTrainedTokenizer


class LLMScorer(weave.Scorer):
    """Score model outputs using a Large Language Model (LLM).

    This scorer leverages LLMs to evaluate and score model outputs. It provides a flexible
    way to use different LLM providers for scoring purposes.

    We are using litellm to support multiple LLM providers.

    Attributes:
        model_id: The specific model identifier to use for scoring
        temperature: Controls randomness in the LLM's responses (0.0 to 1.0)
        max_tokens: Maximum number of tokens allowed in the LLM's response
    """

    model_id: str = Field(
        description="The model to use, check https://docs.litellm.ai/docs/providers for supported models"
    )
    temperature: float = Field(
        ..., description="The temperature to use for the response"
    )
    max_tokens: int = Field(
        ..., description="The maximum number of tokens in the response"
    )

    # TODO: check if we can validate the model_id with litellm on a post_init method


class InstructorLLMScorer(LLMScorer):
    def __new__(cls, *args, **kwargs):  # type: ignore
        raise DeprecationWarning(
            "InstructorLLMScorer is deprecated and will be removed in a future version. "
            "Use LLMScorer directly instead, which now has built-in support for structured outputs."
        )


class HuggingFacePipelineScorer(weave.Scorer):
    """
    Base class for using Hugging Face pipelines for moderation scoring.

    This class simplifies the use of Hugging Face pipelines by handling the initialization and providing a common interface for scoring.

    Args:
        task (str): The pipeline task type (e.g., `"text-classification"`).
        model_name_or_path (str): The name or path of the model to use.
        device (str): The device to use for inference. Defaults to `"auto"`.

    Example:
        >>> from weave.scorers.moderation_scorer import PipelineScorer
        >>> scorer = PipelineScorer(
        ...     task="text-classification",
        ...     model_name_or_path="distilbert-base-uncased-finetuned-sst-2-english",
        ...     device="auto"
        ... )
        >>> output = scorer.pipe("This is a great movie!")
        >>> print(output)
        [{'label': 'POSITIVE', 'score': 0.9998}]
    """

    task: str = Field(
        description="The task to use for the pipeline, for example 'text-classification'"
    )
    model_name_or_path: str = Field(default="", description="The path to the model")
    device: str = Field(default="auto", description="The device to use for the model")
    _pipeline: Optional["Pipeline"] = PrivateAttr(default=None)

    @field_validator("device", mode="before")
    def validate_device(cls, v):  # type: ignore
        if isinstance(v, "torch.device"):
            return v
        else:
            return set_device(v)

    def model_post_init(self, __context: Any) -> None:
        if self._pipeline is None:
            self.load_pipeline()

    def load_pipeline(self) -> None:
        raise NotImplementedError(
            "Subclasses must implement the `_load_pipeline` method."
        )

    @weave.op
    def score(self, *, output: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


class HuggingFaceScorer(weave.Scorer):
    """Score model outputs using a Hugging Face model."""

    model_name_or_path: str = Field(default="", description="The path to the model")
    device: str = Field(default="auto", description="The device to use for the model")
    _model: Optional["PreTrainedModel"] = PrivateAttr(default=None)
    _tokenizer: Optional["PreTrainedTokenizer"] = PrivateAttr(default=None)

    @field_validator("device", mode="before")
    def validate_device(cls, v):  # type: ignore
        if isinstance(v, "torch.device"):
            return v
        else:
            return set_device(v)

    def model_post_init(self, __context: Any = None) -> None:
        """Template method for post-initialization."""
        if self._model is None:
            self.load_model()
        else:
            print("Using user-provided model.")

        if self._tokenizer is None:
            self.load_tokenizer()
        else:
            print("Using user-provided tokenizer.")

        assert self._model is not None, "Model must be loaded, implement `load_model`"
        assert (
            self._tokenizer is not None
        ), "Tokenizer must be loaded, implement `load_tokenizer`"

    def load_model(self) -> None:
        raise NotImplementedError("Subclasses must implement the `_load_model` method.")

    def load_tokenizer(self) -> None:
        raise NotImplementedError(
            "Subclasses must implement the `_load_tokenizer` method."
        )

    @weave.op
    def score(self, *, output: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


class RollingWindowScorer(HuggingFaceScorer):
    """
    Base Scorer class that handles rolling window processing for long inputs.

    Args:
        max_tokens: Maximum number of tokens per window.
        overlap: Number of overlapping tokens between consecutive windows.
        device: The device to use for inference.
        aggregation_method: The method to aggregate predictions ("max" or "mean").
    """

    max_tokens: int = 512  # Default maximum tokens per window
    overlap: int = Field(
        default=50,
        description="The number of overlapping tokens between consecutive windows",
    )
    aggregation_method: Literal["max", "mean"] = Field(
        default="max",
        description="The method to aggregate predictions",
    )

    def predict_chunk(self, input_ids: "torch.Tensor") -> list[Union[int, float]]:
        raise NotImplementedError("Subclasses must implement predict_chunk method.")

    def _tokenize_input(self, prompt: str) -> "torch.Tensor":
        """
        Tokenize the input prompt without truncation.

        Args:
            prompt: The input text to tokenize.

        Returns:
            A tensor of tokenized input IDs.
        """
        assert self._tokenizer is not None
        return self._tokenizer(
            prompt, return_tensors="pt", truncation=False
        ).input_ids.to(self.device)

    def _aggregate_predictions(
        self, all_predictions: list[list[Union[int, float]]]
    ) -> list[float]:
        """
        Aggregate predictions using the specified class attribute method.

        Args:
            all_predictions: List of prediction lists from chunks.

        Returns:
            Aggregated prediction scores per category.
        """
        if not all_predictions:
            return []

        num_categories = len(all_predictions[0])
        aggregated = []

        for i in range(num_categories):
            category_scores = [pred[i] for pred in all_predictions]
            if self.aggregation_method == "max":
                aggregated.append(max(category_scores))
            elif self.aggregation_method == "mean":
                aggregated.append(sum(category_scores) / len(category_scores))
            else:
                raise ValueError(
                    f"Unsupported aggregation method: {self.aggregation_method}"
                )

        return aggregated

    def _predict_long(self, input_ids: "torch.Tensor") -> list[float]:
        """
        Handle prediction for long inputs by processing in overlapping windows.

        Args:
            input_ids: Tokenized input IDs.

        Returns:
            A list of aggregated prediction scores for each category.
        """
        total_tokens: int = input_ids.size(1)

        if total_tokens <= self.max_tokens:
            return self.predict_chunk(input_ids)

        all_predictions: list[list[float]] = []
        stride: int = self.max_tokens - self.overlap

        for i in range(0, total_tokens - self.overlap, stride):
            chunk_input_ids = input_ids[:, i : i + self.max_tokens]
            chunk_predictions = self.predict_chunk(chunk_input_ids)
            all_predictions.append(chunk_predictions)
        # Aggregate predictions using the specified aggregation method
        final_predictions: list[float] = self._aggregate_predictions(all_predictions)

        return final_predictions

    def _predict(self, prompt: str) -> list[float]:
        """
        Predict scores for the input prompt, handling long inputs if necessary.

        Args:
            prompt (str): The input text to evaluate.

        Returns:
            list[float]: A list of prediction scores for each category.

        Example:
            >>> scorer = RollingWindowScorer()
            >>> predictions = scorer.predict("Some long input text...")
            >>> print(predictions)
            [0.5, 0.3, 0.0, 0.2, 0.7]
        """
        input_ids: torch.Tensor = self._tokenize_input(prompt)
        return self._predict_long(input_ids)
