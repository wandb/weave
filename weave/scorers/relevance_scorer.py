from typing import Any, Optional

from pydantic import PrivateAttr

import weave
from weave.scorers.base_scorer import Scorer
import json

try:
    import torch
    from transformers import pipeline
except ImportError:
    import_failed = True
    print(
        "The `transformers` package is required to use the RelevanceScorer, please run `pip install transformers`"
    )

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


class RelevanceScorer(Scorer):
    """
    Use wandb/relevance_scorer to check if the model output is relevant.

    Args:
        model_name: The name of the relevance scorer model to use. Defaults to `wandb/relevance_scorer`.
        device: The device to use for inference. Defaults to `cpu`.
    """

    device: str = "cpu"
    model_name: str = "wandb/relevance_scorer"
    _classifier: Any = PrivateAttr()
    _tokenizer: Any = PrivateAttr()
    _id2label: dict[int, str] = PrivateAttr()
    _system_prompt: str = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        if not torch.cuda.is_available() and "cuda" in self.device:
            raise ValueError("CUDA is not available")
        self._classifier = pipeline(
            task="text-generation", model=self.model_name, device=self.device
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

        relevant = False
        if relevance > 3:
            relevant = True
        return {
            "is_relevant": relevant,
            "score": relevance,
            "relevance": self._id2label.get(relevance, "Unknown"),
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
