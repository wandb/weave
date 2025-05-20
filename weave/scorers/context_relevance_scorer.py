from typing import Any, Union

import numpy as np
from pydantic import Field, validate_call

import weave
from weave.flow.scorer import WeaveScorerResult
from weave.scorers.default_models import MODEL_PATHS
from weave.scorers.scorer_types import HuggingFaceScorer
from weave.scorers.utils import load_hf_model_weights

CONTEXT_RELEVANCE_SCORER_THRESHOLD = 0.55


class WeaveContextRelevanceScorerV1(HuggingFaceScorer):
    """
    A scorer that evaluates the relevance of model outputs relative to input queries and context.
    The scorer uses a fine-tuned deberta-small-long-nli model from tasksource;
    https://huggingface.co/tasksource/deberta-small-long-nli

    This scorer uses a fine-tuned model to analyze whether outputs are semantically relevant to their
    input queries and context. It processes text in chunks and returns both binary relevance flags
    and detailed span-level scores.

    Args:
        model_name_or_path (str): Path or name of model weights to load
        device (str): Device to run model on, defaults to "cpu"
        threshold (float): Threshold for relevance classification, defaults to 0.55
        return_all_spans (bool): Return all spans, defaults to False

    Note: This Scorer's `score` method expects the context to be passed to its `output` parameter as
    a string or list of strings.

    Returns:
        WeaveScorerResult: An object containing:
            - passed (bool): Whether the output was flagged as relevant (score >= threshold)
            - metadata (dict): Contains:
                - score (float): Overall relevance score between 0 and 1
                - all_spans (list[dict], optional): If `return_all_spans` is True, includes list of all relevant
                  text spans with their scores, where each dict has:
                    - text (str): The relevant text span
                    - score (float): The relevance score for this span

    Example:
        >>> scorer = WeaveContextRelevanceScorerV1(return_all_spans=True)
        >>> result = scorer.score(
        ...     query="What is the capital of France?",
        ...     output=["Paris is the capital of France."], # the context to score
        ... )
        >>> print(result)
        WeaveScorerResult(
            passed=True,
            metadata={
                'score': 0.92,
                'all_spans': [
                    {'text': 'Paris is the capital of France', 'score': 0.92}
                ]
            }
        )
    """

    threshold: float = Field(
        default=CONTEXT_RELEVANCE_SCORER_THRESHOLD,
        description="The threshold for relevance classification.",
    )
    return_all_spans: bool = Field(
        default=False,
        description="Whether to return all spans.",
    )
    model_max_length: int = 1280

    def load_model(self) -> None:
        from transformers import AutoModelForTokenClassification

        self._local_model_path = load_hf_model_weights(
            self.model_name_or_path, MODEL_PATHS["relevance_scorer"]
        )
        self._model = AutoModelForTokenClassification.from_pretrained(
            self._local_model_path
        ).to(self.device)
        self._model.eval()

    def load_tokenizer(self) -> None:
        from transformers import AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(
            self._local_model_path,
            model_max_length=self.model_max_length,
        )

    def _score_document(
        self, query: str, document: str, threshold: float
    ) -> tuple[list[dict[str, Any]], int, int]:
        """Score a single document."""
        import torch

        assert self._tokenizer is not None  # keep mypy happy
        assert self._model is not None  # keep mypy happy

        input_text = query + f" {self._tokenizer.sep_token} " + document
        model_inputs = self._tokenizer(
            input_text,
            truncation=True,
            max_length=self.model_max_length,
            padding=False,
            return_tensors="pt",
            return_special_tokens_mask=True,
        )

        model_inputs = {k: v.to(self.device) for k, v in model_inputs.items()}

        special_tokens_mask = model_inputs.pop("special_tokens_mask")
        combined_mask = (
            ~((model_inputs["input_ids"] == 2).bool() | special_tokens_mask.bool())
            .cpu()
            .numpy()
            .flatten()
        )
        # we should mask the query up to the sep token,
        # on the combined mask we have to search for the first False
        # TODO: Check that this is not wrong
        false_indices = np.where(~combined_mask)[0]
        start = false_indices[0]
        end = false_indices[1]
        combined_mask[start:end] = False

        with torch.inference_mode():
            results = self._model(**model_inputs)
            logits = results.logits[0].detach()
            probabilities = torch.nn.functional.softmax(logits, dim=-1).detach()

        pred_mask = (
            (probabilities[:, 1] > threshold).cpu().numpy().astype(int).flatten()
        )
        label_mask = pred_mask & combined_mask

        positive_probs = probabilities[:, 1].cpu().numpy()
        transitions = np.diff(np.concatenate([[0], label_mask, [0]]))
        starts = np.where(transitions == 1)[0]
        ends = np.where(transitions == -1)[0]

        spans_with_probs = []
        token_ids = model_inputs["input_ids"].cpu().numpy()[0]

        for start, end in zip(starts, ends):
            span_text = self._tokenizer.decode(token_ids[start:end])
            span_prob = positive_probs[start:end].mean()
            spans_with_probs.append({"text": span_text, "score": float(span_prob)})

        return spans_with_probs, int(label_mask.sum()), int(len(label_mask))

    @validate_call
    @weave.op
    def score(
        self,
        query: str,
        output: Union[str, list[str]],  # Pass the context to the `output` parameter
        **kwargs: Any,
    ) -> WeaveScorerResult:
        all_spans: list[dict[str, Any]] = []
        total_weighted_score = 0.0
        total_length = 0

        if isinstance(output, str):
            output = [output]
        for doc in output:
            spans, relevant_tokens, total_tokens = self._score_document(
                query, doc, self.threshold
            )

            all_spans.extend(spans)

            if total_tokens > 0:
                doc_score = relevant_tokens / total_tokens
                doc_weight = total_tokens
                total_weighted_score += doc_score * doc_weight
                total_length += total_tokens

        final_score = total_weighted_score / total_length if total_length > 0 else 0.0
        metadata: dict[str, Any] = {"score": final_score}
        if self.return_all_spans:
            metadata["all_spans"] = all_spans
        return WeaveScorerResult(
            passed=final_score >= self.threshold,
            metadata=metadata,
        )
