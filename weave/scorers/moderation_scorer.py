import os
from typing import TYPE_CHECKING, Any, Optional, Union

from pydantic import PrivateAttr, field_validator

import weave
from weave.scorers.llm_scorer import LLMScorer, RollingWindowScorer
from weave.scorers.llm_utils import (
    _LLM_CLIENTS,
    MODEL_PATHS,
    OPENAI_DEFAULT_MODERATION_MODEL,
    download_model,
)

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
        device (str): The device to use for inference. Defaults to `"cuda"` if available, otherwise `"cpu"`.
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

    base_url: Optional[str] = None
    total_threshold: int = 5
    category_threshold: int = 2
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

    def load_model(self) -> None:
        if self.base_url:
            print(f"Using external API at {self.base_url} for scoring.")
            return  # Skip local model loading if base_url is provided
        try:
            from transformers import AutoModelForSequenceClassification
        except ImportError:
            print(
                "The `transformers` package is required to use {self.__class__.__name__}, please run `pip install transformers`"
            )
        """Initialize the toxicity model and tokenizer."""
        if os.path.isdir(self.model_name_or_path):
            self._local_model_path = self.model_name_or_path
        else:
            self._local_model_path = download_model(MODEL_PATHS["toxicity_scorer"])

        self.model = AutoModelForSequenceClassification.from_pretrained(
            self._local_model_path, device_map=self.device, trust_remote_code=True
        )
        self.model.eval()

    def load_tokenizer(self) -> None:
        if self.base_url:
            print(f"Using external API at {self.base_url} for scoring.")
            return  # Skip local model loading if base_url is provided
        try:
            from transformers import AutoTokenizer
        except ImportError:
            print(
                "The `transformers` package is required to use {self.__class__.__name__}, please run `pip install transformers`"
            )
        self.tokenizer = AutoTokenizer.from_pretrained(self._local_model_path)
        print(f"Model and tokenizer loaded on {self.device}")

    def predict_chunk(self, input_ids: "Tensor") -> list[Union[int, float]]:
        """
        Predict toxicity scores for a chunk of tokenized input.

        Args:
            input_ids: Tokenized input IDs for the chunk.

        Returns:
            A list of prediction scores for each category.
        """
        import torch

        with torch.inference_mode():
            attention_mask = (input_ids != 0).long()
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
            predictions = outputs.logits.argmax(dim=-1).squeeze().tolist()
        if isinstance(predictions, int):
            return [predictions]
        return predictions

    def _score_via_api(self, output: str) -> dict[str, Any]:
        import requests

        assert self.base_url is not None
        response = requests.post(self.base_url, json={"output": output})
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
            "extras": dict(zip(self._categories, predictions)),
            "flagged": flagged,
        }


class BiasScorer(RollingWindowScorer):
    """
    Moderation scorer that assesses gender and race/origin bias using a custom-trained model.

    This model is trained from scratch on a custom dataset of 260k samples.

    Reference: https://huggingface.co/wandb/bias-scorer

    Args:
        model_name_or_path (str): The name of the model to use. Defaults to `"wandb/bias_scorer"`.
        task (str): The pipeline task type. Defaults to `"text-classification"`.
        device (str): The device to use for inference. Defaults to `None`, which will use `cuda` if available.
        threshold (float): The threshold for the bias score to flag the input. Defaults to `0.5`.
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

    base_url: Optional[str] = None
    threshold: float = 0.65
    _categories: list[str] = PrivateAttr(
        default=[
            "gender_bias",
            "racial_bias",
        ]
    )

    def load_model(self) -> None:
        if self.base_url:
            print(f"Using external API at {self.base_url} for scoring.")
            return  # Skip local model loading if base_url is provided
        try:
            from transformers import AutoModelForSequenceClassification
        except ImportError:
            print(
                "The `transformers` package is required to use {self.__class__.__name__}, please run `pip install transformers`"
            )

        """Initialize the bias model and tokenizer."""
        if os.path.isdir(self.model_name_or_path):
            self._local_model_path = self.model_name_or_path
        elif self.model_name_or_path != "":
            self._local_model_path = download_model(self.model_name_or_path)
        else:
            self._local_model_path = download_model(MODEL_PATHS["bias_scorer"])

        self.model = AutoModelForSequenceClassification.from_pretrained(
            self._local_model_path, device_map=self.device, trust_remote_code=True
        )
        self.model.eval()

    def load_tokenizer(self) -> None:
        if self.base_url:
            print(f"Using external API at {self.base_url} for scoring.")
            return  # Skip local model loading if base_url is provided
        try:
            from transformers import AutoTokenizer
        except ImportError:
            print(
                f"The `transformers` package is required to use {self.__class__.__name__}, please run `pip install transformers`"
            )
        self.tokenizer = AutoTokenizer.from_pretrained(self._local_model_path)
        print(f"Model and tokenizer loaded on {self.device}")

    def predict_chunk(self, input_ids: "Tensor") -> list[float]:
        import torch

        with torch.inference_mode():
            attention_mask = (input_ids != 0).long()
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
            predictions = outputs.logits.sigmoid().tolist()[0]
        return predictions

    def _score_via_api(self, output: str, verbose: bool = False) -> dict[str, Any]:
        import requests

        assert self.base_url is not None
        response = requests.post(
            self.base_url,
            json={"output": output, "verbose": verbose},
        )
        response.raise_for_status()
        return response.json()

    @weave.op
    def score(self, output: str, verbose: bool = False) -> dict[str, Any]:
        if self.base_url:
            return self._score_via_api(output, verbose)
        predictions = self.predict(output)
        scores = [o >= self.threshold for o in predictions]
        if verbose:
            categories = dict(zip(self._categories, predictions))
        else:
            categories = dict(zip(self._categories, scores))
        return {
            "extras": categories,
            "flagged": any(scores),
        }
