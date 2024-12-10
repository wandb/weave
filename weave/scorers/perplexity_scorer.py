from typing import Union, Any

import numpy as np
from openai.types.chat import ChatCompletion

import weave
from weave.scorers.base_scorer import Scorer


class OpenAIPerplexityScorer(Scorer):
    """A scorer that computes perplexity for OpenAI outputs using log probabilities.
    Reference: https://cookbook.openai.com/examples/using_logprobs#5-calculating-perplexity
    """

    @weave.op()
    def score(self, output: Union[ChatCompletion, list]) -> dict:
        """
        Computes perplexity for OpenAI outputs using log probabilities.

        Args:
            output (Union[ChatCompletion, list]): Either:
                - An OpenAI `ChatCompletion` object with `logprobs`
                - A list of log probabilities (`floats`).

        Returns:
            dict: A dictionary containing the calculated perplexity.
        """
        if isinstance(output, ChatCompletion):
            assert (
                output.choices[0].logprobs is not None
            ), "Logprobs must be present in the output!"
            logprobs = [
                logprob.logprob for logprob in output.choices[0].logprobs.content
            ]
        elif isinstance(output, list):
            assert isinstance(output[0], float), "Logprobs must be a list of floats!"
            logprobs = output
        else:
            raise TypeError("Invalid input type!")

        assert len(logprobs) > 0, "Logprobs must be a non-empty list!"
        assert all(
            isinstance(logprob, float) for logprob in logprobs
        ), "Logprobs must be a list of floats!"

        # Correct perplexity calculation
        nll = -np.mean(logprobs)
        perplexity = np.exp(nll).item()
        return {"perplexity": perplexity}


class HuggingFacePerplexityScorer(Scorer):
    """A scorer that computes perplexity for Hugging Face outputs using log probabilities."""
    def model_post_init(self, __context: Any) -> None:
        """
        Initialize the model and tokenizer. Imports are performed here to ensure they're only
        loaded when an instance of LlamaGuard is created.
        """
        try:
            import torch
        except ImportError as e:
            raise ImportError(
                "The `transformers` and `torch` packages are required to use LlamaGuard. "
                "Please install them by running `pip install transformers torch`."
            ) from e



    @weave.op()
    def score(self, output: dict) -> dict:
        """
        Computes perplexity for Hugging Face outputs using log probabilities.

        Args:
            output (dict): A dictionary containing:
                - "logits" (torch.Tensor): Logits from the model with shape (batch_size, seq_length, vocab_size).
                - "input_ids" (torch.Tensor): Input IDs (ground truth) with shape (batch_size, seq_length).

        Returns:
            dict: A dictionary containing the calculated perplexity.
        """
        import torch
        import torch.nn.functional as F

        logits = output["logits"]
        input_ids = output["input_ids"]

        # Shift logits and labels for causal language modeling
        shift_logits = logits[
            :, :-1, :
        ]  # Ignore the last logit (no next token to predict)
        shift_labels = input_ids[
            :, 1:
        ]  # Ignore the first input token (no previous context)

        # Compute log probabilities
        log_probs = F.log_softmax(shift_logits, dim=-1)

        # Gather log probabilities corresponding to the actual tokens
        token_log_probs = torch.gather(
            log_probs, dim=-1, index=shift_labels.unsqueeze(-1)
        ).squeeze(-1)  # Shape: (batch_size, seq_length - 1)

        # Compute negative log-likelihood (NLL)
        nll = -token_log_probs.mean().item()

        # Compute perplexity
        perplexity = torch.exp(torch.tensor(nll)).item()

        return {"perplexity": perplexity}
