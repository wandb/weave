import json
import os
from importlib.util import find_spec
from typing import Any, Optional, Union

import numpy as np
from pydantic import PrivateAttr

import weave
from weave.scorers.base_scorer import Scorer
from weave.scorers.llm_scorer import HuggingFaceScorer
from weave.scorers.llm_utils import MODEL_PATHS, download_model, set_device

RELEVANCE_INSTRUCTIONS = """You are an expert evaluator assessing the relevance of LLM-generated outputs relative to their input context.
Your goal is to provide a single relevance score and classification based on comprehensive analysis.
Relevance measures how effectively a generated output addresses its input context across three core dimensions:

1. **Semantic Alignment**
   - How directly does the output address key input requirements?
   - Does it maintain topical focus?
   - Does it provide complete coverage of necessary information?
   - Is unnecessary content avoided?

2. **Structural Coherence**
   - Does the output flow logically and show internal consistency?
   - Is the presentation of information clear and organized?
   - Is there a good balance between completeness and conciseness?

3. **Contextual Integration**
   - How well does the output use the provided context?
   - Does the output align with the broader discourse?
   - Is it consistent with background information?
   - Does it fulfill task-specific requirements?

## Evaluation Process

1. Review all input context (instructions, prompts, documents, chat history)
2. Identify core requirements and purpose
3. Analyze the LLM output across all three dimensions
4. Assign a single relevance score (1-5):
   - 5: Exceptional relevance across all dimensions
   - 4: Strong relevance with minor gaps
   - 3: Adequate relevance with some issues
   - 2: Significant relevance issues
   - 1: Major relevance problems
5. Classify as relevant (score ≥ 3.5) or not relevant (score < 3.5)

## Task-Specific Considerations

- **Summarization**: Focus on key information selection and density
- **Q&A**: Emphasize answer accuracy and completeness
- **Chat**: Consider conversation flow and context maintenance
- **RAG**: Evaluate retrieved information integration

## Output Format

Provide evaluation results in the following JSON format:

```json
{
  "relevance": [score from 1-5],
  "relevant": [true/false]
}
```
"""


class OldRelevanceScorer(Scorer):
    """
    Use wandb/relevance_scorer to check if the model output is relevant.

    Args:
        model_name: The name of the relevance scorer model to use. Defaults to `wandb/relevance_scorer`.
        device: The device to use for inference. Defaults to `auto`, which will use `cuda` if available.
    """

    model_name_or_path: str = ""
    device: str = "auto"
    _classifier: Any = PrivateAttr()
    _tokenizer: Any = PrivateAttr()
    _id2label: dict[int, str] = PrivateAttr()
    _system_prompt: str = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        try:
            if find_spec("torch") is None:
                raise ImportError("torch is required but not installed")
            from transformers import pipeline
        except ImportError:
            print(
                "The `transformers` package is required to use the ContextRelevanceScorer, please run `pip install transformers`"
            )

        """Initialize the coherence model and tokenizer."""
        self.device = set_device(self.device)
        if os.path.isdir(self.model_name_or_path):
            self._local_model_path = self.model_name_or_path
        else:
            self._local_model_path = download_model(MODEL_PATHS["relevance_scorer"])

        self._classifier = pipeline(
            task="text-generation", model=self._local_model_path, device=self.device
        )
        self._tokenizer = self._classifier.tokenizer
        self._id2label = {
            0: "Unknown",
            1: "Completely Irrelevant",
            2: "Mostly Irrelevant",
            3: "A Little Irrelevant",
            4: "Mostly Relevant",
            5: "Perfectly Relevant",
        }
        self._system_prompt = RELEVANCE_INSTRUCTIONS.strip()

    @weave.op
    def score_messages(self, messages: str) -> dict[str, Any]:
        """Score a prompt response pair."""
        generated_output = self._classifier(
            messages,
            max_new_tokens=20,
            stop_strings=["}"],
            tokenizer=self._tokenizer,
            penalty_alpha=0.6,
            top_k=4,
        )
        assistant_output = generated_output[0].get("generated_text", [])[-1]
        classification = assistant_output.get("content", "")
        try:
            classification = json.loads(classification)
            relevance = classification.get("relevance", 0)
            relevance = int(relevance)
            relevance = max(0, min(5, relevance))
        except Exception:
            relevance = 0

        passed = False
        if relevance > 3:
            passed = True
        return {
            "pass": passed,
            "extras": {
                "relevance_id": relevance,
                "relevance_label": self._id2label.get(relevance, "Unknown"),
            },
        }

    def _format_messages(
        self,
        prompt: str,
        completion: str,
        context: Optional[list[str]],
        chat_history: Optional[list[dict[str, str]]],
    ) -> list[dict[str, str]]:
        """Format the prompt for the model."""
        chat_history = chat_history if isinstance(chat_history, list) else []
        context = context if isinstance(context, list) else []
        if context:
            joined_context = "\n".join(context).strip()
            joined_context = f"<documents>\n{joined_context}\n</documents>"
        else:
            joined_context = ""
        prompt = f"{joined_context}\n\n{prompt}".strip()

        messages = chat_history + [{"role": "user", "content": prompt}]

        messages = [
            f"<|msg_start|>{message['role']}\n{message['content']}<|msg_end|>"  # type: ignore
            for message in messages
        ]
        joined_messages = "\n".join(messages)  # type: ignore

        final_context = f"<context>{joined_messages}</context>\n"
        completion = f"<completion>{completion}</completion>\n"

        context_and_completion = final_context + completion

        return [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": context_and_completion},
        ]

    @weave.op
    def score(
        self,
        input: str,
        output: str,
        context: Optional[list[str]] = None,
        chat_history: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        messages = self._format_messages(
            prompt=input, completion=output, context=context, chat_history=chat_history
        )
        return self.score_messages(messages)

CONTEXT_RELEVANCE_SCORER_THRESHOLD = 0.55

class ContextRelevanceScorer(HuggingFaceScorer):
    """
    A scorer that evaluates the relevance of model outputs relative to input queries and context.

    This scorer uses a fine-tuned model to analyze whether outputs are semantically relevant to their
    input queries and context. It processes text in chunks and returns both binary relevance flags
    and detailed span-level scores.

    Args:
        model_name_or_path (str): Path or name of model weights to load
        device (str): Device to run model on, defaults to "cpu"
        threshold (float): Threshold for relevance classification, defaults to 0.7
        debug (bool): Enable debug logging, defaults to False

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
        try:
            if find_spec("torch") is None:
                raise ImportError("torch is required but not installed")
            from transformers import AutoModelForTokenClassification
        except ImportError:
            print(
                "The `transformers` and `torch` packages are required to use the ContextRelevanceScorer, please run `pip install transformers torch`"
            )
        """Initialize the model, tokenizer and device after pydantic initialization."""
        if os.path.isdir(self.model_name_or_path):
            self._local_model_path = self.model_name_or_path
        elif self.model_name_or_path != "":
            self._local_model_path = download_model(self.model_name_or_path)
        else:
            self._local_model_path = download_model(MODEL_PATHS["relevance_scorer"])
        assert self._local_model_path, "model_name_or_path local path or artifact path not found"
        self.model = AutoModelForTokenClassification.from_pretrained(
            self._local_model_path, device_map=self.device
        )
        self.model.eval()

    def load_tokenizer(self) -> None:
        try:
            from transformers import AutoTokenizer
        except ImportError:
            print(
                f"The `transformers` is required to use the {self.__class__.__name__}, please run `pip install transformers torch`"
            )
        self.tokenizer = AutoTokenizer.from_pretrained(
            self._local_model_path,
            model_max_length=self.model_max_length,
        )
        print(f"Model and tokenizer loaded on {self.device}")

    def _score_document(
        self, query: str, document: str, threshold: float
    ) -> tuple[list[dict[str, Any]], int, int]:
        """Score a single document."""
        import torch

        input_text = query + f" {self.tokenizer.sep_token} " + document
        model_inputs = self.tokenizer(
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
            span_text = self.tokenizer.decode(token_ids[start:end])
            span_prob = positive_probs[start:end].mean()
            spans_with_probs.append({"text": span_text, "score": float(span_prob)})

        return spans_with_probs, int(label_mask.sum()), int(len(label_mask))

    @weave.op
    def score(
        self,
        query: str,
        context: Union[str, list[str]],
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Score multiple documents and compute weighted average relevance."""
        all_spans = []
        total_weighted_score = 0.0
        total_length = 0

        if isinstance(context, str):
            context = [context]
        for doc in context:
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
        res = {"pass": final_score >= self.threshold}
        extras = {"score": final_score}
        if verbose:
            extras["all_spans"] = all_spans  # type: ignore
        res["extras"] = extras  # type: ignore
        return res
