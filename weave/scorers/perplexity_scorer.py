from typing import Any

from litellm import acompletion
import numpy as np

import weave
# from weave.scorers.llm_scorer import LLMScorer
# from weave.scorers.default_models import OPENAI_DEFAULT_MODEL



# class OpenAIPerplexityScorer(LLMScorer):
#     """A scorer that computes perplexity for OpenAI outputs using log probabilities.
#     Reference: https://cookbook.openai.com/examples/using_logprobs#5-calculating-perplexity
#     """
#     model_id = OPENAI_DEFAULT_MODEL

#     @weave.op()
#     def score(self, output: Any) -> dict:
#         """
#         Computes perplexity for OpenAI outputs using log probabilities.

#         Args:
#             output (Union[ChatCompletion, list]): Either:
#                 - An OpenAI `ChatCompletion` object with `logprobs`
#                 - A list of log probabilities (`floats`).

#         Returns:
#             dict: A dictionary containing the calculated perplexity.
#         """

#         if isinstance(output, ChatCompletion):
#             assert (
#                 output.choices[0].logprobs is not None
#             ), "Logprobs must be present in the output!"
#             logprobs = [
#                 logprob.logprob for logprob in output.choices[0].logprobs.content
#             ]
#         elif isinstance(output, list):
#             assert isinstance(output[0], float), "Logprobs must be a list of floats!"
#             logprobs = output
#         else:
#             raise TypeError("Invalid input type!")

#         assert len(logprobs) > 0, "Logprobs must be a non-empty list!"
#         assert all(
#             isinstance(logprob, float) for logprob in logprobs
#         ), "Logprobs must be a list of floats!"

#         # Correct perplexity calculation
#         nll = -np.mean(logprobs)
#         perplexity = np.exp(nll).item()
#         return {"perplexity": perplexity}


class HuggingFacePerplexityScorer(weave.Scorer):
    """A scorer that computes perplexity for Hugging Face outputs using log probabilities."""

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
