import json
import os
from typing import Any, List, Optional, Union, Dict, Tuple
import numpy as np
from pydantic import PrivateAttr

import weave
from weave.scorers.base_scorer import Scorer
from weave.scorers.llm_utils import download_model, MODEL_PATHS, set_device

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
                - all_spans (list, optional): If verbose=True, includes list of relevant
                  text spans and their scores

    Example:
        >>> scorer = ContextRelevanceScorer(model_name_or_path="path/to/model")
        >>> result = scorer.score(
        ...     query="What is the capital of France?",
        ...     documents=["Paris is the capital of France."]
        ... )
        >>> print(result)
        {
            'flagged': False,
            'extras': {
                'score': 0.92,
                'all_spans': [  # Only included if verbose=True
                    {'text': 'Paris is the capital of France', 'scores': 0.92}
                ]
            }
        }
    """

    model_name_or_path: str = None
    base_url: Optional[str] = None
    device: str = "cpu"
    threshold: float = 0.5
    model_max_length: int = 2048
    _max_num_sentences: int = 20
    _classifier: Any = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        try:
            import torch
            from transformers import pipeline
            import nltk

            nltk.download("punkt_tab")
            from nltk.tokenize import sent_tokenize
        except ImportError:
            print(
                "The `transformers`, `torch` and `nltk` packages are required to use the ContextRelevanceScorer, please run `pip install transformers torch nltk`"
            )
        """Initialize the model, tokenizer and device after pydantic initialization."""
        if os.path.isdir(self.model_name_or_path):
            self._local_model_path = self.model_name_or_path
        else:
            self._local_model_path = download_model(MODEL_PATHS["relevance_scorer"])
        assert self._local_model_path, "Model path not found"

        self.device = set_device(self.device)
        self._classifier = pipeline(
            "context-relevance",
            model=self._local_model_path,
            trust_remote_code=True,
            device=self.device,
        )

    def _score_document(
        self, query: str, document: str, response: str
    ) -> list[dict[str, Any]]:
        """Score a single document."""
        document_sentences = document.split("\n")
        document_sentences = [sent_tokenize(doc) for doc in document_sentences]
        document_sentences = [s for doc in document_sentences for s in doc]
        context_scores = []
        for batch in range(0, len(document_sentences), self._max_num_sentences):
            inputs = {
                "question": query,
                "context": document_sentences[batch : batch + self._max_num_sentences],
                "response": response,
            }
            res = self._classifier(inputs, threshold=self.threshold)[0]
            context_scores.extend(res["sentences"])

        return context_scores

    @weave.op
    def score(
        self,
        output: str,
        query: str,
        context: Union[str, List[str]],
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Score multiple documents and compute weighted average relevance."""
        if isinstance(context, str):
            context = [context]
        context_scores = []
        for doc in context:
            doc_scores = self._score_document(
                query=query, document=doc, response=output
            )
            context_scores.extend(doc_scores)

        relevant_sentences = [
            score for score in context_scores if score["label"] == "relevant"
        ]
        for score in relevant_sentences[:]:
            score.update({"span": score.pop("sentence")})
        final_score = len(relevant_sentences) / len(context_scores)
        res = {"flagged": final_score > self.threshold}
        res["extras"] = {"score": final_score}
        if verbose:
            res["extras"]["all_spans"] = relevant_sentences

        return res
