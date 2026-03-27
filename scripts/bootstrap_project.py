"""Bootstrap a Weave project with sample data for testing and onboarding.

Generates (each step can be run individually):
  - datasets:        Publish sample datasets
  - calls:           Traced op calls (nested, streaming, async, errors, display names, views)
  - evaluations:     Evaluations with function and class-based scorers
  - imperative-eval: Imperative evaluation logging via EvaluationLogger
  - objects:         Custom objects, prompt templates, tags, and aliases

No LLM API keys are required — all models are simulated locally.

Usage:
    # Run all steps (default):
    python scripts/bootstrap_project.py my-team/demo-project

    # Run only specific steps:
    python scripts/bootstrap_project.py my-team/demo --steps calls datasets
    python scripts/bootstrap_project.py my-team/demo --steps evaluations

    # Point at a local trace server:
    python scripts/bootstrap_project.py my-team/demo --base-url http://localhost:9994

Requires:
    pip install weave  (or run from the repo with `uv run`)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import time
from collections.abc import Iterator
from typing import Any

from pydantic import Field

import weave

ALL_STEPS = ["datasets", "calls", "evaluations", "imperative-eval", "objects"]


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

QA_EXAMPLES = [
    {
        "question": "What is the capital of France?",
        "expected": "Paris",
        "category": "geography",
    },
    {
        "question": "Who wrote '1984'?",
        "expected": "George Orwell",
        "category": "literature",
    },
    {
        "question": "What is the square root of 144?",
        "expected": "12",
        "category": "math",
    },
    {
        "question": "What planet is closest to the Sun?",
        "expected": "Mercury",
        "category": "science",
    },
    {
        "question": "In what year did World War II end?",
        "expected": "1945",
        "category": "history",
    },
    {
        "question": "What is the chemical symbol for gold?",
        "expected": "Au",
        "category": "science",
    },
    {
        "question": "Who painted the Mona Lisa?",
        "expected": "Leonardo da Vinci",
        "category": "art",
    },
    {
        "question": "What is 7 × 8?",
        "expected": "56",
        "category": "math",
    },
    {
        "question": "What is the largest ocean on Earth?",
        "expected": "Pacific Ocean",
        "category": "geography",
    },
    {
        "question": "Who developed the theory of relativity?",
        "expected": "Albert Einstein",
        "category": "science",
    },
]

SENTIMENT_EXAMPLES = [
    {"text": "I love this product, it works perfectly!", "label": "positive"},
    {"text": "Terrible experience, would not recommend.", "label": "negative"},
    {"text": "It's okay, nothing special.", "label": "neutral"},
    {"text": "Absolutely fantastic service!", "label": "positive"},
    {"text": "The worst purchase I've ever made.", "label": "negative"},
    {"text": "Average quality, fair price.", "label": "neutral"},
    {"text": "Exceeded my expectations in every way.", "label": "positive"},
    {"text": "Broke after one day of use.", "label": "negative"},
    {"text": "Does what it says, no more no less.", "label": "neutral"},
    {"text": "A delightful surprise, highly recommended!", "label": "positive"},
]

SUMMARIZATION_EXAMPLES = [
    {
        "document": (
            "The Amazon rainforest, often referred to as the 'lungs of the Earth,' "
            "produces about 20% of the world's oxygen. It spans across nine countries "
            "and is home to approximately 10% of all species on the planet. Deforestation "
            "threatens this vital ecosystem, with an estimated 17% of the forest lost "
            "in the last 50 years."
        ),
        "expected_summary": (
            "The Amazon rainforest produces 20% of Earth's oxygen and hosts 10% of all "
            "species, but has lost 17% of its area to deforestation."
        ),
    },
    {
        "document": (
            "Quantum computing leverages quantum mechanical phenomena like superposition "
            "and entanglement to process information. Unlike classical bits that are either "
            "0 or 1, quantum bits (qubits) can exist in multiple states simultaneously. "
            "This allows quantum computers to solve certain problems exponentially faster "
            "than classical computers."
        ),
        "expected_summary": (
            "Quantum computers use qubits that exist in multiple states at once, enabling "
            "exponentially faster solutions for certain problems compared to classical computers."
        ),
    },
    {
        "document": (
            "The Mediterranean diet emphasizes fruits, vegetables, whole grains, legumes, "
            "nuts, and olive oil. Studies show it reduces the risk of heart disease by up "
            "to 30%. It also includes moderate consumption of fish and poultry while limiting "
            "red meat and processed foods."
        ),
        "expected_summary": (
            "The Mediterranean diet focuses on plant-based foods and olive oil, reducing "
            "heart disease risk by up to 30%."
        ),
    },
]


# ---------------------------------------------------------------------------
# Simulated models (no API keys required)
# ---------------------------------------------------------------------------


class QAModel(weave.Model):
    """A simple Q&A model that uses keyword matching to simulate answers."""

    temperature: float = 0.7
    system_prompt: str = "You are a helpful assistant that answers questions concisely."

    @weave.op
    def predict(self, question: str) -> dict:
        answer = _simulate_qa_answer(question, self.temperature)
        return {"answer": answer, "confidence": random.uniform(0.5, 1.0)}


class SentimentModel(weave.Model):
    """A simulated sentiment classifier."""

    threshold: float = 0.5

    @weave.op
    def predict(self, text: str) -> dict:
        label, score = _simulate_sentiment(text)
        return {"label": label, "score": score}


class SummarizationModel(weave.Model):
    """A simulated summarization model."""

    max_length: int = 100

    @weave.op
    def predict(self, document: str) -> dict:
        summary = _simulate_summarization(document, self.max_length)
        return {"summary": summary}


# ---------------------------------------------------------------------------
# Custom objects
# ---------------------------------------------------------------------------


class PipelineConfig(weave.Object):
    """A published configuration object for a RAG pipeline."""

    retriever_top_k: int = 3
    model_temperature: float = 0.7
    max_tokens: int = 256
    system_prompt: str = "You are a helpful assistant."


class ExperimentMetadata(weave.Object):
    """Metadata about an experiment run."""

    hypothesis: str = ""
    owner: str = ""
    tags: list[str] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Ops (traced functions)
# ---------------------------------------------------------------------------


@weave.op
def retrieve_context(question: str, top_k: int = 3) -> list[str]:
    """Simulate a RAG retrieval step."""
    time.sleep(random.uniform(0.01, 0.05))
    snippets = [
        f"Relevant passage {i + 1} for: {question[:40]}..."
        for i in range(top_k)
    ]
    return snippets


@weave.op
def format_prompt(question: str, context: list[str]) -> str:
    """Format a prompt with retrieved context."""
    context_block = "\n".join(f"- {c}" for c in context)
    return f"Context:\n{context_block}\n\nQuestion: {question}\nAnswer:"


@weave.op
def generate_answer(prompt: str, temperature: float = 0.7) -> str:
    """Simulate LLM generation."""
    time.sleep(random.uniform(0.02, 0.08))
    # Extract the question from the prompt
    if "Question:" in prompt:
        question = prompt.rsplit("Question:", maxsplit=1)[-1].split("\n", maxsplit=1)[0].strip()
        return _simulate_qa_answer(question, temperature)
    return "I don't have enough information to answer that."


@weave.op
def rag_pipeline(question: str) -> dict:
    """A full RAG pipeline: retrieve -> format -> generate."""
    context = retrieve_context(question)
    prompt = format_prompt(question, context)
    answer = generate_answer(prompt)
    return {
        "answer": answer,
        "context": context,
        "prompt_length": len(prompt),
    }


@weave.op
def classify_text(text: str) -> dict:
    """Classify text sentiment."""
    label, score = _simulate_sentiment(text)
    return {"label": label, "score": score}


@weave.op
def extract_entities(text: str) -> list[dict]:
    """Simulate named entity extraction."""
    time.sleep(random.uniform(0.01, 0.03))
    words = text.split()
    entities = []
    for word in words:
        cleaned = word.strip(".,!?")
        if cleaned and cleaned[0].isupper() and len(cleaned) > 1:
            entity_type = random.choice(["PERSON", "ORG", "LOC", "MISC"])
            entities.append({"text": cleaned, "type": entity_type})
    return entities


@weave.op
def process_document(document: str) -> dict:
    """Process a document: classify sentiment and extract entities."""
    sentiment = classify_text(document)
    entities = extract_entities(document)
    return {
        "sentiment": sentiment,
        "entities": entities,
        "word_count": len(document.split()),
    }


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------


@weave.op
def exact_match(expected: str, output: dict) -> dict:
    """Check if the model output exactly matches the expected answer."""
    model_answer = output.get("answer", output.get("summary", ""))
    match = model_answer.strip().lower() == expected.strip().lower()
    return {"match": match}


@weave.op
def contains_expected(expected: str, output: dict) -> dict:
    """Check if the expected answer appears anywhere in the model output."""
    model_answer = output.get("answer", output.get("summary", ""))
    contains = expected.strip().lower() in model_answer.strip().lower()
    return {"contains": contains}


@weave.op
def confidence_above_threshold(output: dict, threshold: float = 0.7) -> dict:
    """Check if model confidence exceeds the threshold."""
    confidence = output.get("confidence", output.get("score", 0.0))
    return {"above_threshold": confidence >= threshold}


@weave.op
def label_match(label: str, output: dict) -> dict:
    """Check if predicted label matches the true label."""
    predicted = output.get("label", "")
    return {"match": predicted == label}


@weave.op
def summary_length_ok(output: dict) -> dict:
    """Check that summary is shorter than the original and non-empty."""
    summary = output.get("summary", "")
    is_ok = 10 < len(summary) < 500
    return {"length_ok": is_ok, "length": len(summary)}


class AnswerRelevanceScorer(weave.Scorer):
    """A class-based scorer that checks answer relevance via keyword overlap."""

    min_overlap: float = 0.3

    @weave.op
    def score(self, *, output: Any, question: str, **kwargs: Any) -> dict:
        answer = output.get("answer", "")
        q_words = set(question.lower().split()) - {"what", "is", "the", "of", "a", "who", "in"}
        a_words = set(answer.lower().split())
        overlap = len(q_words & a_words) / max(len(q_words), 1)
        return {"relevant": overlap >= self.min_overlap, "overlap": round(overlap, 3)}


# ---------------------------------------------------------------------------
# Streaming, async, error, and display-name ops
# ---------------------------------------------------------------------------


@weave.op(call_display_name=lambda call: f"stream [{call.inputs['prompt'][:30]}...]")
def stream_tokens(prompt: str) -> Iterator[str]:
    """Simulate token-by-token LLM generation (streaming op)."""
    answer = _simulate_qa_answer(prompt, temperature=0.5)
    for token in answer.split():
        time.sleep(random.uniform(0.01, 0.03))
        yield token + " "


@weave.op(call_display_name=lambda call: f"async-fetch [{call.inputs['url'][:25]}]")
async def async_fetch_data(url: str) -> dict:
    """Simulate an async data fetch."""
    await asyncio.sleep(random.uniform(0.02, 0.08))
    return {
        "url": url,
        "status": 200,
        "tokens": random.randint(50, 500),
    }


@weave.op
async def async_parallel_pipeline(questions: list[str]) -> list[dict]:
    """Fetch data for multiple questions concurrently (async op)."""
    tasks = [async_fetch_data(f"https://api.example.com/q/{q[:20]}") for q in questions]
    return await asyncio.gather(*tasks)


@weave.op
def failing_parse(raw_input: str) -> dict:
    """An op that sometimes fails — demonstrates error states in the UI."""
    if not raw_input or not raw_input.strip():
        raise ValueError("Input must not be empty")
    if raw_input.startswith("{"):
        # Simulate a JSON parse that fails on malformed input
        raise ValueError(f"Malformed JSON payload: unexpected token at position 0 in: {raw_input[:50]}")
    return {"parsed": raw_input.strip(), "length": len(raw_input)}


@weave.op
def analyze_with_view(text: str) -> dict:
    """An op that attaches a markdown view to its call via set_view."""
    words = text.split()
    word_count = len(words)
    char_count = len(text)
    unique_words = len({w.lower().strip(".,!?") for w in words})

    # Attach a rich markdown report as a view on this call
    report = (
        f"# Text Analysis Report\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Words | {word_count} |\n"
        f"| Characters | {char_count} |\n"
        f"| Unique words | {unique_words} |\n"
        f"| Avg word length | {char_count / max(word_count, 1):.1f} |\n"
    )
    weave.set_view("analysis-report", report, extension="md")

    return {
        "word_count": word_count,
        "char_count": char_count,
        "unique_words": unique_words,
    }


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

_QA_KNOWLEDGE = {
    "capital": "Paris",
    "france": "Paris",
    "1984": "George Orwell",
    "wrote": "George Orwell",
    "square root": "12",
    "144": "12",
    "closest": "Mercury",
    "sun": "Mercury",
    "world war": "1945",
    "chemical symbol": "Au",
    "gold": "Au",
    "mona lisa": "Leonardo da Vinci",
    "painted": "Leonardo da Vinci",
    "7 × 8": "56",
    "7 * 8": "56",
    "largest ocean": "Pacific Ocean",
    "relativity": "Albert Einstein",
    "developed": "Albert Einstein",
}

_POSITIVE_WORDS = {
    "love", "fantastic", "great", "excellent", "amazing",
    "delightful", "recommended", "perfect", "exceeded", "best",
}
_NEGATIVE_WORDS = {
    "terrible", "worst", "broke", "hate", "awful",
    "horrible", "bad", "never", "disappointed", "useless",
}


def _simulate_qa_answer(question: str, temperature: float) -> str:
    q_lower = question.lower()
    for key, answer in _QA_KNOWLEDGE.items():
        if key in q_lower:
            # Simulate temperature-based noise
            if random.random() < (1.0 - temperature * 0.3):
                return answer
            return answer + " (approximately)"
    return "I'm not sure about that."


def _simulate_sentiment(text: str) -> tuple[str, float]:
    words = set(text.lower().split())
    pos_count = len(words & _POSITIVE_WORDS)
    neg_count = len(words & _NEGATIVE_WORDS)

    if pos_count > neg_count:
        label = "positive"
        score = min(0.95, 0.6 + pos_count * 0.1 + random.uniform(0, 0.15))
    elif neg_count > pos_count:
        label = "negative"
        score = min(0.95, 0.6 + neg_count * 0.1 + random.uniform(0, 0.15))
    else:
        label = "neutral"
        score = 0.4 + random.uniform(0, 0.2)
    return label, round(score, 3)


def _simulate_summarization(document: str, max_length: int) -> str:
    sentences = document.replace(". ", ".\n").split("\n")
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 1:
        return document[:max_length]
    # Pick first and a random other sentence
    picked = [sentences[0]]
    if len(sentences) > 2:
        picked.append(random.choice(sentences[1:]))
    summary = " ".join(picked)
    if len(summary) > max_length:
        summary = summary[:max_length].rsplit(" ", 1)[0] + "..."
    return summary


# ---------------------------------------------------------------------------
# Bootstrap steps
# ---------------------------------------------------------------------------


def step_datasets() -> dict[str, weave.Dataset]:
    """Publish sample datasets."""
    print("  [datasets] Publishing datasets...")

    qa_dataset = weave.Dataset(name="qa-examples", rows=QA_EXAMPLES)
    weave.publish(qa_dataset)
    print(f"    ✓ qa-examples ({len(QA_EXAMPLES)} rows)")

    sentiment_dataset = weave.Dataset(name="sentiment-examples", rows=SENTIMENT_EXAMPLES)
    weave.publish(sentiment_dataset)
    print(f"    ✓ sentiment-examples ({len(SENTIMENT_EXAMPLES)} rows)")

    summarization_dataset = weave.Dataset(
        name="summarization-examples", rows=SUMMARIZATION_EXAMPLES
    )
    weave.publish(summarization_dataset)
    print(f"    ✓ summarization-examples ({len(SUMMARIZATION_EXAMPLES)} rows)")

    return {
        "qa": qa_dataset,
        "sentiment": sentiment_dataset,
        "summarization": summarization_dataset,
    }


def step_calls() -> None:
    """Generate a variety of traced calls including nested call trees."""
    print("  [calls] Generating traced calls...")

    # RAG pipeline calls with attributes (nested: retrieve -> format -> generate)
    for i, example in enumerate(QA_EXAMPLES):
        with weave.attributes({"category": example["category"], "batch": "rag", "index": i}):
            rag_pipeline(example["question"])
    print(f"    ✓ {len(QA_EXAMPLES)} RAG pipeline calls (with nested ops + attributes)")

    # Sentiment classification calls
    for i, example in enumerate(SENTIMENT_EXAMPLES):
        with weave.attributes({"expected_label": example["label"], "batch": "sentiment", "index": i}):
            classify_text(example["text"])
    print(f"    ✓ {len(SENTIMENT_EXAMPLES)} sentiment classification calls (with attributes)")

    # Document processing calls (nested: classify + extract_entities)
    docs = [ex["document"] for ex in SUMMARIZATION_EXAMPLES]
    for i, doc in enumerate(docs):
        with weave.attributes({"batch": "doc-processing", "index": i}):
            process_document(doc)
    print(f"    ✓ {len(docs)} document processing calls (with nested ops)")

    # Streaming ops (custom call_display_name + yield)
    for example in QA_EXAMPLES[:3]:
        tokens = list(stream_tokens(example["question"]))
    print("    ✓ 3 streaming op calls (with custom display names)")

    # Async ops (concurrent fetch)
    questions = [ex["question"] for ex in QA_EXAMPLES[:4]]
    asyncio.run(async_parallel_pipeline(questions))
    print("    ✓ 1 async parallel pipeline call (4 concurrent fetches)")

    # Calls with set_view (rich markdown view attached)
    for example in SUMMARIZATION_EXAMPLES:
        analyze_with_view(example["document"])
    print(f"    ✓ {len(SUMMARIZATION_EXAMPLES)} calls with set_view (markdown report)")

    # Error state calls
    error_inputs = ["", "{bad json", "   "]
    for raw in error_inputs:
        try:
            failing_parse(raw)
        except ValueError:
            pass  # Expected — the error is recorded in the call
    # Also one successful call for contrast
    failing_parse("valid input text")
    print(f"    ✓ {len(error_inputs)} errored calls + 1 success (error states in UI)")


async def step_evaluations(datasets: dict[str, weave.Dataset] | None = None) -> None:
    """Run evaluations with different models and scorers."""
    print("  [evaluations] Running evaluations...")

    # If datasets weren't published in an earlier step, create them inline
    if datasets is None:
        datasets = {
            "qa": weave.Dataset(name="qa-examples", rows=QA_EXAMPLES),
            "sentiment": weave.Dataset(name="sentiment-examples", rows=SENTIMENT_EXAMPLES),
            "summarization": weave.Dataset(
                name="summarization-examples", rows=SUMMARIZATION_EXAMPLES
            ),
        }

    # QA evaluation (mix of function scorers + class-based scorer)
    relevance_scorer = AnswerRelevanceScorer(min_overlap=0.2)
    qa_model = QAModel(temperature=0.3, system_prompt="Answer concisely.")
    qa_eval = weave.Evaluation(
        name="qa-evaluation",
        dataset=datasets["qa"],
        scorers=[exact_match, contains_expected, confidence_above_threshold, relevance_scorer],
    )
    qa_results = await qa_eval.evaluate(qa_model)
    print(f"    ✓ QA evaluation: {_format_results(qa_results)}")

    # Run a second QA eval with different temperature to show comparison
    qa_model_v2 = QAModel(temperature=0.9, system_prompt="Be creative.")
    qa_results_v2 = await qa_eval.evaluate(qa_model_v2)
    print(f"    ✓ QA evaluation (high temp): {_format_results(qa_results_v2)}")

    # Sentiment evaluation
    sentiment_model = SentimentModel(threshold=0.5)
    sentiment_eval = weave.Evaluation(
        name="sentiment-evaluation",
        dataset=datasets["sentiment"],
        scorers=[label_match, confidence_above_threshold],
    )
    sentiment_results = await sentiment_eval.evaluate(sentiment_model)
    print(f"    ✓ Sentiment evaluation: {_format_results(sentiment_results)}")

    # Summarization evaluation
    summarization_model = SummarizationModel(max_length=150)
    summarization_eval = weave.Evaluation(
        name="summarization-evaluation",
        dataset=datasets["summarization"],
        scorers=[summary_length_ok],
    )
    summarization_results = await summarization_eval.evaluate(summarization_model)
    print(f"    ✓ Summarization evaluation: {_format_results(summarization_results)}")


def step_imperative_eval() -> None:
    """Demonstrate imperative evaluation logging via EvaluationLogger."""
    print("  [imperative-eval] Running imperative evaluation...")

    ev = weave.EvaluationLogger(name="manual-review-eval")

    for example in QA_EXAMPLES[:5]:
        answer = _simulate_qa_answer(example["question"], temperature=0.5)
        confidence = random.uniform(0.5, 1.0)

        pred = ev.log_prediction(
            inputs={"question": example["question"]},
            output={"answer": answer, "confidence": confidence},
        )
        pred.log_score(
            "exact_match",
            answer.strip().lower() == example["expected"].strip().lower(),
        )
        pred.log_score(
            "confidence",
            {"value": round(confidence, 3), "above_threshold": confidence >= 0.7},
        )
        pred.finish()

    ev.log_summary()
    print("    ✓ Imperative evaluation with 5 examples")


def step_objects() -> None:
    """Publish custom objects and prompt templates."""
    print("  [objects] Publishing custom objects and prompts...")

    # Publish a pipeline config object
    config = PipelineConfig(
        name="default-rag-config",
        retriever_top_k=3,
        model_temperature=0.7,
        max_tokens=256,
        system_prompt="You are a helpful assistant. Answer concisely.",
    )
    weave.publish(config)
    print("    ✓ PipelineConfig: default-rag-config")

    # Publish a second config variant for comparison
    config_v2 = PipelineConfig(
        name="creative-rag-config",
        retriever_top_k=5,
        model_temperature=0.9,
        max_tokens=512,
        system_prompt="You are a creative assistant. Provide detailed, imaginative answers.",
    )
    weave.publish(config_v2)
    print("    ✓ PipelineConfig: creative-rag-config")

    # Publish experiment metadata
    experiment = ExperimentMetadata(
        name="baseline-qa-experiment",
        hypothesis="Lowering temperature improves exact-match accuracy on factual QA",
        owner="bootstrap-script",
        tags=["baseline", "qa", "temperature-sweep"],
        notes="Comparing temperature=0.3 vs temperature=0.9 on the QA dataset.",
    )
    weave.publish(experiment)
    print("    ✓ ExperimentMetadata: baseline-qa-experiment")

    # Publish prompt templates
    qa_prompt = weave.StringPrompt(
        "You are a helpful assistant. Answer the following question concisely "
        "and accurately. If you are unsure, say so."
    )
    qa_prompt.name = "qa-system-prompt"
    weave.publish(qa_prompt)
    print("    ✓ StringPrompt: qa-system-prompt")

    chat_prompt = weave.MessagesPrompt([
        {
            "role": "system",
            "content": (
                "You are a retrieval-augmented assistant. Use the provided "
                "context to answer questions. Cite your sources."
            ),
        },
        {"role": "user", "content": "Context: {context}\n\nQuestion: {question}"},
    ])
    chat_prompt.name = "rag-chat-prompt"
    weave.publish(chat_prompt)
    print("    ✓ MessagesPrompt: rag-chat-prompt")

    # --- Tags and aliases on published objects ---
    config_ref = weave.publish(PipelineConfig(
        name="tagged-config",
        retriever_top_k=3,
        model_temperature=0.5,
        max_tokens=256,
        system_prompt="You are a precise assistant.",
    ))
    weave.add_tags(config_ref, ["stable", "reviewed", "v1"])
    print("    ✓ Tagged object: tagged-config (stable, reviewed, v1)")

    weave.set_aliases(config_ref, ["production", "latest-stable"])
    print("    ✓ Aliased object: tagged-config -> production, latest-stable")


def _format_results(results: dict) -> str:
    """Format evaluation results for display."""
    parts = []
    for key, value in results.items():
        if isinstance(value, dict):
            for metric, metric_val in value.items():
                if isinstance(metric_val, dict) and "true_fraction" in metric_val:
                    parts.append(f"{key}.{metric}={metric_val['true_fraction']:.0%}")
                elif isinstance(metric_val, dict) and "mean" in metric_val:
                    parts.append(f"{key}.{metric}={metric_val['mean']:.2f}")
    return ", ".join(parts) if parts else str(results)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap a Weave project with sample data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "available steps:\n"
            "  datasets         Publish sample datasets (QA, sentiment, summarization)\n"
            "  calls            Traced ops: nested, streaming, async, errors, views\n"
            "  evaluations      Evaluations with function + class-based scorers\n"
            "  imperative-eval  Log an evaluation imperatively via EvaluationLogger\n"
            "  objects          Objects, prompts, tags, and aliases\n"
            "\n"
            "examples:\n"
            "  %(prog)s my-team/demo\n"
            "  %(prog)s my-team/demo --steps calls datasets\n"
            "  %(prog)s my-team/demo --steps evaluations --seed 123\n"
        ),
    )
    parser.add_argument(
        "project",
        nargs="?",
        default="bootstrap/demo-project",
        help="Weave project name (default: bootstrap/demo-project)",
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=ALL_STEPS,
        default=None,
        metavar="STEP",
        help=f"Steps to run (default: all). Choices: {', '.join(ALL_STEPS)}",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Weave trace server URL (e.g. http://localhost:9994)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()

    steps = set(args.steps) if args.steps else set(ALL_STEPS)

    random.seed(args.seed)

    print(f"\n{'=' * 60}")
    print(f"  Bootstrapping Weave project: {args.project}")
    print(f"  Steps: {', '.join(sorted(steps))}")
    print(f"{'=' * 60}\n")

    if args.base_url:
        os.environ["WF_TRACE_SERVER_URL"] = args.base_url

    weave.init(project_name=args.project)

    # Track what was created for the summary
    summary_lines: list[str] = []

    # --- datasets ---
    datasets: dict[str, weave.Dataset] | None = None
    if "datasets" in steps:
        datasets = step_datasets()
        summary_lines.append(
            f"3 published datasets ({len(QA_EXAMPLES) + len(SENTIMENT_EXAMPLES) + len(SUMMARIZATION_EXAMPLES)} total rows)"
        )
        print()

    # --- calls ---
    if "calls" in steps:
        step_calls()
        summary_lines.append(
            "Traced op calls: nested pipelines, streaming, async, errors, "
            "custom display names, and set_view"
        )
        print()

    # --- evaluations ---
    if "evaluations" in steps:
        asyncio.run(step_evaluations(datasets))
        summary_lines.append("4 evaluations with function + class-based scorers")
        print()

    # --- imperative-eval ---
    if "imperative-eval" in steps:
        step_imperative_eval()
        summary_lines.append("1 imperative evaluation via EvaluationLogger")
        print()

    # --- objects ---
    if "objects" in steps:
        step_objects()
        summary_lines.append(
            "Published objects with tags and aliases (configs, prompts, experiment)"
        )
        print()

    weave.finish()

    print(f"{'=' * 60}")
    print(f"  Done! Your project '{args.project}' is ready.")
    print(f"{'=' * 60}")
    print()
    print("  What was created:")
    for line in summary_lines:
        print(f"    - {line}")
    print()


if __name__ == "__main__":
    main()
