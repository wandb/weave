from typing import Any, Union

import numpy as np

import weave
from weave.scorers.llm_scorer import HuggingFaceScorer
from weave.scorers.utils import (
    MODEL_PATHS,
    WeaveScorerResult,
    check_score_param_type,
    ensure_hf_imports,
    load_hf_model_weights,
)

CONTEXT_RELEVANCE_SCORER_THRESHOLD = 0.55


class WeaveContextRelevanceScorer(HuggingFaceScorer):
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
        threshold (float): Threshold for relevance classification, defaults to 0.7
        debug (bool): Enable debug logging, defaults to False

    Note: This Scorer's `score` method expects the context to be passed to its `output` parameter as
    a string or list of strings.

    Returns:
        dict: A dictionary containing:
            - pass (bool): Whether the output was flagged as relevant (score >= threshold)
            - extras (dict): Contains:
                - score (float): Overall relevance score between 0 and 1
                - all_spans (list[dict], optional): If verbose=True, includes list of all relevant
                  text spans with their scores, where each dict has:
                    - text (str): The relevant text span
                    - score (float): The relevance score for this span

    Example:
        >>> scorer = ContextRelevanceScorer()
        >>> result = scorer.score(
        ...     query="What is the capital of France?",
        ...     context=["Paris is the capital of France."],
        ...     verbose=True
        ... )
        >>> print(result)
        {
            'pass': True,
            'extras': {
                'score': 0.92,
                'all_spans': [
                    {'text': 'Paris is the capital of France', 'score': 0.92}
                ]
            }
        }
    """

    threshold: float = CONTEXT_RELEVANCE_SCORER_THRESHOLD
    model_max_length: int = 1280

    def load_model(self) -> None:
        ensure_hf_imports()
        from transformers import AutoModelForTokenClassification

        self._local_model_path = load_hf_model_weights(
            self.model_name_or_path, MODEL_PATHS["relevance_scorer"]
        )
        assert (
            self._local_model_path
        ), "model_name_or_path local path or artifact path not found"
        self.model = AutoModelForTokenClassification.from_pretrained(
            self._local_model_path, device_map=self.device
        )
        self.model.eval()

    def load_tokenizer(self) -> None:
        ensure_hf_imports()
        from transformers import AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(
            self._local_model_path,
            model_max_length=self.model_max_length,
        )
        print(f"Model and tokenizer loaded on {self.device}")

    def _score_document(
        self, query: str, document: str, threshold: float
    ) -> tuple[list[dict[str, Any]], int, int]:
        """Score a single document."""
        import torch

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
            results = self.model(**model_inputs)
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

    @weave.op
    def score(
        self,
        query: str,
        output: Union[str, list[str]],  # Pass the context to the `output` parameter
        verbose: bool = False,
    ) -> WeaveScorerResult:
        """
        Scores the relevance of the context against the query. Uses a weighted average of
        relevant tokens in the context against the query to compute a final score.

        Args:
            query: str, The query to score the context against, must be a string
            output: Union[str, list[str]], The context to score, must be a string or list of strings
            verbose: bool, Whether to return all relevant spans from the output
        """
        check_score_param_type(query, str, "query", self)
        check_score_param_type(output, (str, list), "output", self)

        all_spans = []
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
        extras = {"score": final_score}
        if verbose:
            extras["all_spans"] = all_spans  # type: ignore
        return WeaveScorerResult(
            passed=final_score >= self.threshold,
            extras=extras,
        )
