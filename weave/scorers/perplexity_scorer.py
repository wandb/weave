import weave
from weave.scorers.utils import WeaveScorerResult


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
            dict: A unified dictionary containing:
                  - "passed": Always True (no threshold defined for perplexity).
                  - "extras": A dictionary with 'perplexity'.
        """
        import torch
        import torch.nn.functional as F

        logits = output["logits"]
        input_ids = output["input_ids"]

        # Shift logits and labels for causal language modeling
        shift_logits = logits[:, :-1, :]
        shift_labels = input_ids[:, 1:]

        # Compute log probabilities
        log_probs = F.log_softmax(shift_logits, dim=-1)

        # Gather log probabilities corresponding to the actual tokens
        token_log_probs = torch.gather(
            log_probs, dim=-1, index=shift_labels.unsqueeze(-1)
        ).squeeze(-1)

        # Compute negative log-likelihood (NLL)
        nll = -token_log_probs.mean().item()

        # Compute perplexity
        perplexity = torch.exp(torch.tensor(nll)).item()

        return WeaveScorerResult(passed=True, extras={"perplexity": perplexity})
