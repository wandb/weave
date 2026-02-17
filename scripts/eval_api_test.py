#!/usr/bin/env python3
"""Run a realistic evaluation with LLM model + mixed scorers against a dev trace server.

This script creates:
- a Q&A dataset with varied difficulty
- a model that calls OpenAI (gpt-4.1-nano) to answer questions
- deterministic scorers (exact match, token distance, overlap)
- an LLM-as-judge scorer that returns structured reasoning
- pass/fail criteria on aggregate metrics

It initializes Weave with project `eval-api-test` and executes the evaluation.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

import weave


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

DATASET = [
    # --- Short / exact answers (1-2 words) ---
    {"prompt": "What is 2 + 2?", "expected": "4", "category": "math"},
    {"prompt": "What is the capital of France?", "expected": "Paris", "category": "geography"},
    {"prompt": "What is the chemical symbol for water?", "expected": "H2O", "category": "science"},
    {"prompt": "What is the square root of 144?", "expected": "12", "category": "math"},
    {"prompt": "What is the boiling point of water in Celsius?", "expected": "100", "category": "science"},
    {"prompt": "Translate 'hello' to Spanish.", "expected": "hola", "category": "language"},
    {"prompt": "What is the largest planet in our solar system?", "expected": "Jupiter", "category": "science"},
    {"prompt": "What color do you get mixing red and blue?", "expected": "purple", "category": "general"},
    {"prompt": "How many sides does a hexagon have?", "expected": "6", "category": "math"},
    {"prompt": "What is the symbol for gold on the periodic table?", "expected": "Au", "category": "science"},
    # --- Medium answers (2-5 words) ---
    {"prompt": "Who wrote Romeo and Juliet?", "expected": "William Shakespeare", "category": "literature"},
    {"prompt": "Who painted the Mona Lisa?", "expected": "Leonardo da Vinci", "category": "art"},
    {"prompt": "What is the smallest prime number?", "expected": "2", "category": "math"},
    {"prompt": "In what year did World War II end?", "expected": "1945", "category": "history"},
    {"prompt": "Name the closest star to Earth.", "expected": "The Sun", "category": "science"},
    {"prompt": "What programming language is known for its use in data science?", "expected": "Python", "category": "tech"},
    {"prompt": "What is the tallest mountain on Earth?", "expected": "Mount Everest", "category": "geography"},
    {"prompt": "What organ pumps blood through the human body?", "expected": "The heart", "category": "biology"},
    {"prompt": "What is the freezing point of water in Fahrenheit?", "expected": "32 degrees Fahrenheit", "category": "science"},
    {"prompt": "What is the currency of Japan?", "expected": "Yen", "category": "geography"},
    # --- Longer / trickier answers (many words, easy to paraphrase differently) ---
    {"prompt": "Explain what photosynthesis is in one sentence.", "expected": "Photosynthesis is the process by which plants convert sunlight into energy", "category": "biology"},
    {"prompt": "What are the three states of matter?", "expected": "solid, liquid, and gas", "category": "science"},
    {"prompt": "Name the first three planets from the Sun.", "expected": "Mercury, Venus, and Earth", "category": "science"},
    {"prompt": "Describe the Pythagorean theorem in one sentence.", "expected": "In a right triangle, the square of the hypotenuse equals the sum of the squares of the other two sides", "category": "math"},
    {"prompt": "What is the purpose of the Bill of Rights?", "expected": "To protect individual freedoms and rights of citizens from government overreach", "category": "history"},
    # --- Intentionally hard / ambiguous (likely wrong or partial) ---
    {"prompt": "What is the exact value of pi to 10 decimal places?", "expected": "3.1415926535", "category": "math"},
    {"prompt": "Recite the first line of the US Constitution.", "expected": "We the People of the United States, in Order to form a more perfect Union", "category": "history"},
    {"prompt": "What is the airspeed velocity of an unladen swallow?", "expected": "About 11 meters per second", "category": "trivia"},
    {"prompt": "Name all noble gases.", "expected": "helium, neon, argon, krypton, xenon, and radon", "category": "science"},
    {"prompt": "What is the chemical formula for glucose?", "expected": "C6H12O6", "category": "science"},
]


# ---------------------------------------------------------------------------
# Model -- calls OpenAI gpt-4.1-nano
# ---------------------------------------------------------------------------

_openai_client = AsyncOpenAI()


class QAModel(weave.Model):
    """Question-answering model backed by gpt-4.1-nano."""

    system_prompt: str = (
        "You are a concise Q&A assistant. Answer the question in as few words "
        "as possible. Give only the answer, no explanation."
    )

    @weave.op
    async def predict(self, prompt: str) -> str:
        """Call gpt-4.1-nano and return the answer text.

        Args:
            prompt: The question to answer.

        Returns:
            The model's answer string.
        """
        response = await _openai_client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=100,
            temperature=0.7,
        )
        return (response.choices[0].message.content or "").strip()


# ---------------------------------------------------------------------------
# Deterministic scorers
# ---------------------------------------------------------------------------


@weave.op
def exact_match(output: str, expected: str) -> bool:
    """Case-insensitive exact match.

    Args:
        output: Model output.
        expected: Expected answer.

    Returns:
        True when normalized strings match.
    """
    return output.strip().lower() == expected.strip().lower()


@weave.op
def contains_expected_text(output: str, expected: str) -> dict[str, Any]:
    """Check if output contains the expected text, with overlap ratio.

    Args:
        output: Model output.
        expected: Expected answer.

    Returns:
        Dict with ``passed`` bool and ``overlap_ratio`` float.
    """
    out_lower = output.strip().lower()
    exp_lower = expected.strip().lower()
    contained = exp_lower in out_lower
    out_tokens = set(out_lower.split())
    exp_tokens = set(exp_lower.split())
    overlap = len(out_tokens & exp_tokens) / max(len(exp_tokens), 1)
    return {
        "passed": contained,
        "overlap_ratio": round(overlap, 4),
    }


@weave.op
def token_distance(output: str, expected: str) -> dict[str, Any]:
    """Token-level distance metrics.

    Args:
        output: Model output.
        expected: Expected answer.

    Returns:
        Dict with ``passed``, ``distance_tokens``, and ``normalized`` score.
    """
    distance = abs(len(output.split()) - len(expected.split()))
    return {
        "passed": distance == 0,
        "distance_tokens": distance,
        "normalized": round(1.0 / (1.0 + float(distance)), 4),
    }


@weave.op
def starts_with_same_letter(output: str, expected: str) -> dict[str, bool]:
    """Check if output and expected start with the same letter.

    Args:
        output: Model output.
        expected: Expected answer.

    Returns:
        Dict with ``same_first_letter`` bool.
    """
    return {
        "same_first_letter": bool(output)
        and bool(expected)
        and output[0].lower() == expected[0].lower()
    }


# ---------------------------------------------------------------------------
# Pure-numeric scorers (no pass/fail)
# ---------------------------------------------------------------------------


@weave.op
def answer_relevance(output: str, expected: str) -> float:
    """Compute a 0-1 character-level similarity score with no pass/fail.

    Args:
        output: Model output.
        expected: Expected answer.

    Returns:
        Float similarity score between 0 and 1.
    """
    o = output.strip().lower()
    e = expected.strip().lower()
    if not e:
        return 0.0
    common = sum(1 for c in o if c in e)
    return round(min(common / len(e), 1.0), 4)


@weave.op
def text_statistics(output: str, expected: str) -> dict[str, float]:
    """Return purely numeric text comparison metrics with no pass/fail.

    Args:
        output: Model output.
        expected: Expected answer.

    Returns:
        Dict with ``length_ratio``, ``word_count``, and ``char_diff``.
    """
    out_len = len(output.strip())
    exp_len = len(expected.strip())
    return {
        "length_ratio": round(out_len / max(exp_len, 1), 4),
        "word_count": float(len(output.split())),
        "char_diff": float(abs(out_len - exp_len)),
    }


@weave.op
def string_similarity(output: str, expected: str) -> dict[str, float]:
    """Multi-faceted string similarity metrics producing continuous 0-100 scores.

    Args:
        output: Model output.
        expected: Expected answer.

    Returns:
        Dict with ``char_score``, ``word_score``, ``prefix_score``, ``length_penalty``.
    """
    o = output.strip().lower()
    e = expected.strip().lower()

    # Character bigram overlap → 0-100
    def bigrams(s: str) -> list[str]:
        return [s[i : i + 2] for i in range(len(s) - 1)] if len(s) > 1 else [s]

    o_bg = bigrams(o)
    e_bg = bigrams(e)
    if e_bg:
        bg_overlap = sum(1 for b in o_bg if b in e_bg) / max(len(e_bg), 1)
    else:
        bg_overlap = 1.0 if not o_bg else 0.0
    char_score = round(min(bg_overlap, 1.0) * 100, 2)

    # Word-level Jaccard → 0-100
    o_words = set(o.split())
    e_words = set(e.split())
    union = o_words | e_words
    word_score = round((len(o_words & e_words) / max(len(union), 1)) * 100, 2)

    # Longest common prefix ratio → 0-100
    prefix_len = 0
    for a, b in zip(o, e):
        if a == b:
            prefix_len += 1
        else:
            break
    prefix_score = round((prefix_len / max(len(e), 1)) * 100, 2)

    # Length penalty: how far off the output length is, as 0-100 (100 = same length)
    ratio = len(o) / max(len(e), 1)
    length_penalty = round(max(0, 100 - abs(1 - ratio) * 100), 2)

    return {
        "char_score": char_score,
        "word_score": word_score,
        "prefix_score": prefix_score,
        "length_penalty": length_penalty,
    }


# ---------------------------------------------------------------------------
# LLM-as-judge scorer -- returns structured reasoning
# ---------------------------------------------------------------------------


class CorrectnessJudgement(BaseModel):
    """Structured output from the LLM judge."""

    reasoning: str
    is_correct: bool
    confidence: float


class CorrectnessJudge(weave.Scorer):
    """LLM-based scorer that evaluates semantic correctness with reasoning.

    Uses gpt-4.1-nano to judge whether the model output is semantically
    correct given the expected answer, returning structured reasoning.
    """

    @weave.op
    async def score(self, *, output: str, expected: str) -> dict[str, Any]:
        """Judge correctness via LLM and return structured result.

        Args:
            output: The model's answer.
            expected: The ground truth answer.

        Returns:
            Dict with ``passed``, ``confidence``, and ``reasoning``.
        """
        response = await _openai_client.beta.chat.completions.parse(
            model="gpt-4.1-nano",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an evaluation judge. Determine if the model output "
                        "is semantically correct given the expected answer. "
                        "Minor formatting differences are acceptable. "
                        "Be strict about factual accuracy."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Expected answer: {expected}\n"
                        f"Model output: {output}\n\n"
                        "Is the model output correct?"
                    ),
                },
            ],
            response_format=CorrectnessJudgement,
            temperature=0,
            max_tokens=300,
        )
        judgement = response.choices[0].message.parsed
        if judgement is None:
            return {"passed": False, "confidence": 0.0, "reasoning": "Parse error"}
        return {
            "passed": judgement.is_correct,
            "confidence": round(judgement.confidence, 4),
            "reasoning": judgement.reasoning,
        }


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------


async def run_eval() -> dict[str, Any]:
    """Initialize weave and run the evaluation.

    Returns:
        The evaluation summary dict.
    """
    weave.init("eval-api-test")

    evaluation = weave.Evaluation(
        dataset=DATASET,
        scorers=[
            exact_match,
            token_distance,
            starts_with_same_letter,
            contains_expected_text,
            answer_relevance,
            text_statistics,
            string_similarity,
            CorrectnessJudge(),
        ],
        trials=3,
        evaluation_name="eval-api-test-run-realistic",
        criteria=[
            weave.EvaluationCriterion(
                scorer="exact_match",
                metric="true_fraction",
                op=">=",
                threshold=0.5,
            ),
            weave.EvaluationCriterion(
                scorer="token_distance",
                metric="passed.true_fraction",
                op=">=",
                threshold=0.3,
            ),
            weave.EvaluationCriterion(
                scorer="contains_expected_text",
                metric="passed.true_fraction",
                op=">=",
                threshold=0.8,
            ),
            weave.EvaluationCriterion(
                scorer="CorrectnessJudge",
                metric="passed.true_fraction",
                op=">=",
                threshold=0.7,
            ),
        ],
    )

    model = QAModel()
    return await evaluation.evaluate(model)


def main() -> None:
    """Execute the evaluation and print results."""
    result = asyncio.run(run_eval())
    print("=" * 60)
    print("Evaluation completed for project: eval-api-test")
    print("=" * 60)
    print()
    print(json.dumps(result, indent=2, default=str))

    if criteria := result.get("_criteria"):
        print()
        print("-" * 60)
        status = "PASSED" if criteria["passed"] else "FAILED"
        print(f"Overall criteria: {status}")
        print("-" * 60)
        for r in criteria["results"]:
            mark = "PASS" if r["passed"] else "FAIL"
            actual_str = f"{r['actual']:.4f}" if r["actual"] is not None else "N/A"
            print(
                f"  [{mark}] {r['scorer']}.{r['metric']} "
                f"{r['op']} {r['threshold']}  (actual: {actual_str})"
            )


if __name__ == "__main__":
    main()
