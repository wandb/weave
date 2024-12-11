import json
import os
from typing import Any, Optional
import numpy as np
from pydantic import PrivateAttr

import weave
from weave.scorers.base_scorer import Scorer
from weave.scorers.llm_utils import download_model, scorer_model_paths, set_device

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
        device: The device to use for inference. Defaults to `None`, which will use `cuda` if available.
    """

    model_name_or_path: str = None
    base_url: Optional[str] = None
    device: str = None
    _classifier: Any = PrivateAttr()
    _tokenizer: Any = PrivateAttr()
    _id2label: dict[int, str] = PrivateAttr()
    _system_prompt: str = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        try:
            import torch
            from transformers import pipeline
        except ImportError:
            print(
                "The `transformers` package is required to use the ContextRelevanceScorer, please run `pip install transformers`"
            )
        if self.base_url:
            print(f"Using external API at {self.base_url} for scoring.")
            return  # Skip local model loading if base_url is provided

        """Initialize the coherence model and tokenizer."""
        self.device = set_device(self.device)
        if os.path.isdir(self.model_name_or_path):
            self._local_model_path = self.model_name_or_path
        else:
            self._local_model_path = download_model(
                scorer_model_paths["relevance_scorer"]
            )

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

        flagged = True
        if relevance > 3:
            flagged = False
        return {
            "flagged": flagged,
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
            context = "\n".join(context).strip()
            context = f"<documents>\n{context}\n</documents>"
        else:
            context = ""
        prompt = f"{context}\n\n{prompt}".strip()

        messages = chat_history + [{"role": "user", "content": prompt}]

        messages = [
            f"<|msg_start|>{message['role']}\n{message['content']}<|msg_end|>"
            for message in messages
        ]
        messages = "\n".join(messages)

        context = f"<context>{messages}</context>\n"
        completion = f"<completion>{completion}</completion>\n"

        context_and_completion = context + completion

        return [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": context_and_completion},
        ]

    def _score_via_api(
        self,
        input: str,
        output: str,
        context: Optional[list[str]] = None,
        chat_history: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        import requests

        response = requests.post(
            self.base_url,
            json={
                "input": input,
                "output": output,
                "context": context,
                "chat_history": chat_history,
            },
        )
        response.raise_for_status()
        return response.json()

    @weave.op
    def score(
        self,
        input: str,
        output: str,
        context: Optional[list[str]] = None,
        chat_history: Optional[list[dict[str, str]]] = None,
    ) -> dict[str, Any]:
        if self.base_url:
            return self._score_via_api(input, output, context, chat_history)
        messages = self._format_messages(
            prompt=input, completion=output, context=context, chat_history=chat_history
        )
        return self.score_messages(messages)


class ContextRelevanceScorer(Scorer):
    """
    A scorer that evaluates the relevance of model outputs relative to input queries and context.

    This scorer uses a fine-tuned model to analyze whether outputs are semantically relevant to their
    input queries and context. It processes text in chunks and returns both binary relevance flags
    and detailed span-level scores.

    Args:
        model_name_or_path (str): Path or name of model weights to load
        base_url (Optional[str]): Optional URL for external API scoring instead of local model
        device (str): Device to run model on, defaults to "cpu"
        threshold (float): Threshold for relevance classification, defaults to 0.7
        debug (bool): Enable debug logging, defaults to False

    Returns:
        dict: A dictionary containing:
            - flagged (bool): Whether the output was flagged as irrelevant
            - extras (dict): Contains:
                - score (float): Overall relevance score
                - document_scores (list[float]): List of relevance scores for each document
                - relevant_sentences (list[dict]): List of dictionaries containing:
                    - document (str): The document text
                    - relevant_sentences (list[tuple[str, float]]): List of tuples with relevant sentence and its score

    Example:
        >>> scorer = ContextRelevanceScorer(model_name_or_path="path/to/model")
        >>> result = scorer.score(
        ...     query="What is the capital of France?",
        ...     context=["Paris is the capital of France."]
        ... )
        >>> print(result)
        {
            'flagged': False,
            'extras': {
                'score': 0.92,
                'document_scores': [0.92],
                'relevant_sentences': [
                    {
                        'document': 'Paris is the capital of France.',
                        'relevant_sentences': [
                            ('Paris is the capital of France.', 0.92)
                        ]
                    }
                ]
            }
        }
    """

    model_name_or_path: str = None
    base_url: Optional[str] = None
    device: str = "cpu"
    threshold: float = 0.7
    _model: Any = PrivateAttr()
    _tokenizer: Any = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        try:
            import torch
            from transformers import AutoModelForTokenClassification, AutoTokenizer
            import nltk

            nltk.download("punkt")

        except ImportError:
            print(
                "The `transformers`, `torch` and `nltk` packages are required to use the ContextRelevanceScorer, please run `pip install transformers torch nltk`"
            )
        """Initialize the model, tokenizer and device after pydantic initialization."""
        if os.path.isdir(self.model_name_or_path):
            self._local_model_path = self.model_name_or_path
        else:
            self._local_model_path = download_model(
                scorer_model_paths["relevance_scorer"]
            )
        assert self._local_model_path, "Model path not found"
        self._model = AutoModelForTokenClassification.from_pretrained(
            self._local_model_path, device_map=self.device
        )
        self._tokenizer = AutoTokenizer.from_pretrained(self._local_model_path)
        self._model.eval()
        self.device = set_device(self.device)

    @staticmethod
    def sentence_level_aggregation(
        document, label_mask, offsets, threshold=0.5
    ) -> tuple[Any, Any]:
        """Compute sentence-level relevance scores."""
        from nltk.tokenize import sent_tokenize

        sentences = [sent_tokenize(chunk) for chunk in document.split("\n")]
        sentences = [sent for sent_list in sentences for sent in sent_list]

        char_index = 0
        sentence_spans = []
        for sent in sentences:
            start_idx = document.find(sent, char_index)
            end_idx = start_idx + len(sent)
            sentence_spans.append((start_idx, end_idx))
            char_index = end_idx

        sentence_relevances = []
        for sent_start, sent_end in sentence_spans:
            token_indices_in_sentence = []
            for i, (t_start, t_end) in enumerate(offsets):
                if t_start < sent_end and t_end > sent_start:
                    token_indices_in_sentence.append(i)

            if not token_indices_in_sentence:
                sentence_relevances.append((document[sent_start:sent_end], 0.0))
                continue

            token_indices_in_sentence = np.array(token_indices_in_sentence)
            relevant_count = label_mask[token_indices_in_sentence].sum()
            total_count = len(token_indices_in_sentence)
            fraction_relevant = relevant_count / total_count
            sentence_text = document[sent_start:sent_end]
            sentence_relevances.append((sentence_text, fraction_relevant))

        relevant_sentences = [
            (sent, round(float(frac), 4))
            for (sent, frac) in sentence_relevances
            if frac >= threshold
        ]
        return sentence_relevances, relevant_sentences

    def _score_document(
        self, query: str, document: str, threshold: float
    ) -> tuple[list[tuple[str, float]], float, int, int]:
        """Score a single document and compute sentence-level scores and relevant sentences."""
        import torch

        with torch.no_grad():
            input_text = query + f" {self._tokenizer.sep_token} " + document
            model_inputs = self._tokenizer(
                input_text,
                truncation=True,
                padding=False,
                return_tensors="pt",
                return_special_tokens_mask=True,
                return_offsets_mapping=True,
            )
            model_inputs = {k: v.to(self.device) for k, v in model_inputs.items()}

            offsets = model_inputs.pop("offset_mapping")[0].cpu().numpy()
            special_tokens_mask = model_inputs.pop("special_tokens_mask")

            results = self._model(**model_inputs)
            logits = results.logits[0].detach()
            probabilities = torch.nn.functional.softmax(logits, dim=-1).detach()

            sep_token_id = self._tokenizer.sep_token_id
            input_ids = model_inputs["input_ids"][0]  # assuming a batch size of 1

            sep_positions = (input_ids == sep_token_id).nonzero(as_tuple=True)[0]

            if len(sep_positions) < 2:
                # If there's only one or no SEP token found, this logic won't hold.
                raise ValueError(
                    "Expected at least two SEP tokens (one after query, one after document)."
                )

            doc_start = sep_positions[0].item() + 1
            doc_end = sep_positions[-1].item()

            combined_mask = np.zeros_like(
                special_tokens_mask.cpu().numpy()[0], dtype=bool
            )
            combined_mask[doc_start:doc_end] = True

            pred_mask = (
                (probabilities[:, 1] > threshold).cpu().numpy().astype(int).flatten()
            )
            label_mask = pred_mask & combined_mask

            doc_start_str = query + f" {self._tokenizer.sep_token} "
            doc_start_char = len(doc_start_str)

            doc_token_indices = np.where(combined_mask == 1)[0]
            doc_offsets = offsets[doc_token_indices]
            doc_offsets_adjusted = doc_offsets - doc_start_char
            doc_label_mask = label_mask[doc_token_indices]

            sentence_relevances, relevant_sentences = self.sentence_level_aggregation(
                document=document,
                label_mask=doc_label_mask,
                offsets=doc_offsets_adjusted,
                threshold=0.5,
            )

            if len(sentence_relevances) > 0:
                doc_score = len(relevant_sentences) / len(sentence_relevances)
            else:
                doc_score = 0.0

            return (
                relevant_sentences,
                doc_score,
                int(doc_label_mask.sum()),
                int(len(doc_label_mask)),
            )

    @weave.op
    def score(
        self, output: str, query: str, context: str | list[str], verbose: bool = False
    ) -> dict[str, Any]:
        """Score multiple documents and compute weighted average relevance."""
        total_weighted_score = 0.0
        total_length = 0
        all_relevant_sentences = []

        if isinstance(context, str):
            context = [context]
        if not query:
            raise ValueError(
                "The query must not be empty to score relevance of the context."
            )

        doc_scores = []
        for doc in context:
            relevant_sents, doc_score, relevant_tokens, total_tokens = (
                self._score_document(query, doc, self.threshold)
            )
            doc_scores.append(doc_score)
            if verbose:
                all_relevant_sentences.append(
                    {"document": doc, "relevant_sentences": relevant_sents}
                )

            if total_tokens > 0:
                doc_weight = total_tokens
                total_weighted_score += doc_score * doc_weight
                total_length += doc_weight

        final_score = total_weighted_score / total_length if total_length > 0 else 0.0
        res = {"flagged": final_score > self.threshold}
        extras = {"score": round(final_score, 4), "document_scores": doc_scores}
        if verbose:
            extras["relevant_sentences"] = all_relevant_sentences
        res["extras"] = extras
        return res
