from typing import TYPE_CHECKING, Any, Optional, Union

from pydantic import Field, PrivateAttr, field_validator

import weave
from weave.scorers.base_scorer import Scorer
from weave.scorers.llm_scorer import LLMScorer
from weave.scorers.llm_utils import _LLM_CLIENTS, OPENAI_DEFAULT_MODERATION_MODEL

if TYPE_CHECKING:
    from torch import Tensor


class OpenAIModerationScorer(LLMScorer):
    """
    Use the OpenAI moderation API to check if the output is safe.

    The OpenAI moderation API returns a response with categories indicating different types of unsafe content:
    - `sexual`: Sexual content
    - `sexual/minors`: Sexual content involving minors
    - `harassment`: Harassment content
    - `harassment/threatening`: Threatening harassment
    - `hate`: Hate speech
    - `hate/threatening`: Threatening hate speech
    - `illicit`: Illicit content
    - `illicit/violent`: Violent illicit content
    - `self-harm`: Self-harm content
    - `self-harm/intent`: Intent of self-harm
    - `self-harm/instructions`: Instructions for self-harm
    - `violence`: Violent content
    - `violence/graphic`: Graphic violence

    Args:
        model_id (str): The OpenAI model to use for moderation. Defaults to `text-moderation-latest`.

    Returns:
        dict: A dictionary containing the `flagged` status and the detected `categories`.

    Example:
        >>> from weave.scorers.moderation_scorer import OpenAIModerationScorer
        >>> scorer = OpenAIModerationScorer()
        >>> result = await scorer.score("This is some sample text.")
        >>> print(result)
        {'flagged': False, 'categories': {}}
    """

    model_id: str = OPENAI_DEFAULT_MODERATION_MODEL

    @field_validator("client")
    def validate_openai_client(cls, v: _LLM_CLIENTS) -> _LLM_CLIENTS:
        # Method implementation
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ValueError("Install openai to use this scorer")

        if not isinstance(v, AsyncOpenAI):
            raise TypeError("Moderation scoring only works with AsyncOpenAI")
        return v

    @weave.op
    async def score(self, output: Any) -> dict:
        response = await self.client.moderations.create(
            model=self.model_id,
            input=output,
        )
        response = response.results[0]
        categories = {
            k: v
            for k, v in response.categories
            if v and ("/" not in k and "-" not in k)
        }
        return {"flagged": response.flagged, "categories": categories}


class RollingWindowScorer(Scorer):
    """
    Base Scorer class that handles rolling window processing for long inputs.

    Args:
        max_tokens: Maximum number of tokens per window.
        overlap: Number of overlapping tokens between consecutive windows.
        device: The device to use for inference.
        aggregation_method: The method to aggregate predictions ("max" or "average").
    """

    max_tokens: int = 512  # Default maximum tokens per window
    overlap: int = 50
    device: str = "cpu"
    aggregation_method: str = "max"  # New class attribute for aggregation method
    _model: Any = PrivateAttr()
    _tokenizer: Any = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        """Initialize the model and tokenizer. To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement model_post_init method.")

    def tokenize_input(self, prompt: str) -> "Tensor":
        """
        Tokenize the input prompt without truncation.

        Args:
            prompt: The input text to tokenize.

        Returns:
            A tensor of tokenized input IDs.
        """
        return self._tokenizer(
            prompt, return_tensors="pt", truncation=False
        ).input_ids.to(self.device)

    def predict_chunk(self, input_ids: "Tensor") -> list[int]:
        raise NotImplementedError("Subclasses must implement predict_chunk method.")

    def aggregate_predictions(
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
            elif self.aggregation_method == "average":
                aggregated.append(sum(category_scores) / len(category_scores))
            else:
                raise ValueError(
                    f"Unsupported aggregation method: {self.aggregation_method}"
                )

        return aggregated

    def predict_long(self, input_ids: "Tensor") -> list[float]:
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

        for i in range(0, total_tokens, stride):
            print("Running window", i)
            chunk_input_ids = input_ids[:, i : i + self.max_tokens]
            chunk_predictions = self.predict_chunk(chunk_input_ids)
            all_predictions.append(chunk_predictions)
        print("All predictions", all_predictions)
        # Aggregate predictions using the specified aggregation method
        final_predictions: list[float] = self.aggregate_predictions(all_predictions)

        return final_predictions

    def predict(self, prompt: str) -> list[float]:
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
        input_ids: Tensor = self.tokenize_input(prompt)
        return self.predict_long(input_ids)

    @weave.op
    async def score(self, output: str) -> dict[str, Any]:
        raise NotImplementedError("Subclasses must implement score method.")


class ToxicityScorer(RollingWindowScorer):
    """
    Moderation scorer using the Celadon model.

    Celadon is a DeBERTa-v3-small fine-tuned model with five classification heads, trained on 600k samples from the Toxic Commons dataset.

    It classifies toxicity along five dimensions:
    - **Race and Origin-based Bias**: Includes racism and bias against someone’s country, region of origin, or immigration status.
    - **Gender and Sexuality-based Bias**: Includes sexism, misogyny, homophobia, transphobia, and sexual harassment.
    - **Religious Bias**: Any bias or stereotype based on someone’s religion.
    - **Ability Bias**: Bias according to someone’s physical, mental, or intellectual ability or disability.
    - **Violence and Abuse**: Overly graphic descriptions of violence, threats of violence, or incitement of violence.

    Args:
        model_name_or_path (str): The name of the model to use. Defaults to `"wandb/celadon"`.
        total_threshold (int): The threshold for the total moderation score to flag the input. Defaults to `5`.
        category_threshold (int): The threshold for individual category scores to flag the input. Defaults to `2`.
        device (str): The device to use for inference. Defaults to `"cpu"`.
        max_tokens (int): Maximum number of tokens per window. Defaults to `512`.
        overlap (int): Number of overlapping tokens between windows. Defaults to `50`.

    Returns:
        dict[str, Any]: A dictionary containing the `categories` with their respective scores and a `flagged` boolean.

    Example:
        >>> from weave.scorers import ToxicityScorer
        >>> scorer = ToxicityScorer()
        >>> result = scorer.score("This is a hateful message.")
        >>> print(result)
        {
            'categories': {
                'Race/Origin': 3,
                'Gender/Sex': 0,
                'Religion': 0,
                'Ability': 0,
                'Violence': 1
            },
            'flagged': True
        }
    """

    model_name_or_path: str = "wandb/celadon"
    base_url: Optional[str] = None
    total_threshold: int = 5
    category_threshold: int = 2
    device: str = "cpu"
    max_tokens: int = 512
    overlap: int = 50
    _categories: list[str] = PrivateAttr(
        default=[
            "Race/Origin",
            "Gender/Sex",
            "Religion",
            "Ability",
            "Violence",
        ]
    )

    def model_post_init(self, __context: Any) -> None:
        if self.base_url:
            print(f"Using external API at {self.base_url} for scoring.")
            return  # Skip local model loading if base_url is provided
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError:
            print(
                "The `transformers` package is required to use ToxicScorer, please run `pip install transformers`"
            )
        """Initialize the toxicity model and tokenizer."""
        if not torch.cuda.is_available() and self.device == "cuda":
            raise ValueError("CUDA is not available")
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name_or_path, device_map=self.device, trust_remote_code=True
        )
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path)
        print(f"Model and tokenizer loaded on {self.device}")
        self._model.eval()

    def predict_chunk(self, input_ids: "Tensor") -> list[int]:
        """
        Predict toxicity scores for a chunk of tokenized input.

        Args:
            input_ids: Tokenized input IDs for the chunk.

        Returns:
            A list of prediction scores for each category.
        """
        attention_mask = (input_ids != 0).long()
        outputs = self._model(input_ids=input_ids, attention_mask=attention_mask)
        predictions = outputs.logits.argmax(dim=-1).squeeze().tolist()
        if isinstance(predictions, int):
            return [predictions]
        return predictions

    def _score_via_api(self, output: str) -> dict[str, Any]:
        import requests
        response = requests.post(
            self.base_url,
            json={"output": output}
        )
        response.raise_for_status()
        return response.json()

    @weave.op
    def score(self, output: str) -> dict[str, Any]:
        # remote scoring
        if self.base_url:
            return self._score_via_api(output=output)
        
        # local scoring
        flagged: bool = False
        predictions: list[float] = self.predict(output)
        if (sum(predictions) >= self.total_threshold) or any(
            o >= self.category_threshold for o in predictions
        ):
            flagged = True

        return {
            "categories": dict(zip(self._categories, predictions)),
            "flagged": flagged,
        }


class PipelineScorer(Scorer):
    """
    Base class for using Hugging Face pipelines for moderation scoring.

    This class simplifies the use of Hugging Face pipelines by handling the initialization and providing a common interface for scoring.

    Args:
        task (str): The pipeline task type (e.g., `"text-classification"`).
        model_name_or_path (str): The name or path of the model to use.
        device (str): The device to use for inference. Defaults to `"cpu"`.
        pipeline_kwargs (dict[str, Any]): Additional keyword arguments for the pipeline. Defaults to `{}`.

    Returns:
        list[dict[str, Any]]: The pipeline's output after processing the input text.

    Example:
        >>> from weave.scorers.moderation_scorer import PipelineScorer
        >>> scorer = PipelineScorer(
        ...     task="text-classification",
        ...     model_name_or_path="distilbert-base-uncased-finetuned-sst-2-english"
        ... )
        >>> output = scorer.pipe("This is a great movie!")
        >>> print(output)
        [{'label': 'POSITIVE', 'score': 0.9998}]
    """

    task: str
    model_name_or_path: str
    device: str = "cpu"
    pipeline_kwargs: dict[str, Any] = Field(default_factory=dict)
    _pipeline: Any = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        try:
            from transformers import pipeline
        except ImportError:
            print(
                "The `transformers` package is required to use PipelineScorer, please run `pip install transformers`"
            )
        self._pipeline = pipeline(
            self.task,
            model=self.model_name_or_path,
            device=self.device,
            **self.pipeline_kwargs,
        )

    def pipe(self, prompt: str) -> list[dict[str, Any]]:
        return self._pipeline(prompt)[0]

    @weave.op
    def score(self, output: str) -> dict[str, Any]:
        return self.pipe(output)


class BiasScorer(RollingWindowScorer):
    """
    Moderation scorer that assesses gender and race/origin bias using a custom-trained model.

    This model is trained from scratch on a custom dataset of 260k samples.

    Reference: https://huggingface.co/wandb/bias-scorer

    Args:
        model_name_or_path (str): The name of the model to use. Defaults to `"wandb/bias_scorer"`.
        task (str): The pipeline task type. Defaults to `"text-classification"`.
        device (str): The device to use for inference. Defaults to `"cpu"`.
        threshold (float): The threshold for the bias score to flag the input. Defaults to `0.45`.
        pipeline_kwargs (dict[str, Any]): Additional keyword arguments for the pipeline. Defaults to `{"top_k": 2}`.

    Returns:
        dict[str, Any]: A dictionary indicating whether each bias category is detected.

    Example:
        >>> from weave.scorers.moderation_scorer import CustomBiasScorer
        >>> scorer = CustomBiasScorer()
        >>> result = scorer.score("This text contains gender bias.")
        >>> print(result)
        {
            'gender_bias': True,
            'racial_bias': False
        }
    """

    model_name_or_path: str = "wandb/bias_scorer"
    base_url: Optional[str] = None
    device: str = "cpu"
    threshold: float = 0.5
    _categories: list[str] = PrivateAttr(
        default=[
            "gender_bias",
            "racial_bias",
        ]
    )

    def model_post_init(self, __context: Any) -> None:
        if self.base_url:
            print(f"Using external API at {self.base_url} for scoring.")
            return  # Skip local model loading if base_url is provided
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError:
            print(
                "The `transformers` package is required to use ToxicScorer, please run `pip install transformers`"
            )
        """Initialize the toxicity model and tokenizer."""
        if not torch.cuda.is_available() and self.device == "cuda":
            raise ValueError("CUDA is not available")
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name_or_path, device_map=self.device, trust_remote_code=True
        )
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path)
        print(f"Model and tokenizer loaded on {self.device}")
        self._model.eval()

    def predict_chunk(self, input_ids: "Tensor") -> list[float]:
        attention_mask = (input_ids != 0).long()
        outputs = self._model(input_ids=input_ids, attention_mask=attention_mask)
        predictions = outputs.logits.sigmoid().tolist()[0]
        return predictions

    def _score_via_api(self, output: str, return_all_scores: bool = False) -> dict[str, Any]:
        import requests
        response = requests.post(
            self.base_url,
            json={"output": output, "return_all_scores": return_all_scores}
        )
        response.raise_for_status()
        return response.json()

    @weave.op
    def score(self, output: str, return_all_scores: bool = False) -> dict[str, Any]:
        if self.base_url:
            return self._score_via_api(output, return_all_scores)
        predictions = self.predict(output)
        scores = [o >= self.threshold for o in predictions]
        if return_all_scores:
            categories = dict(zip(self._categories, predictions))
        else:
            categories = dict(zip(self._categories, scores))
        return {
            "categories": categories,
            "flagged": any(scores),
        }
