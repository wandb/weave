"""Bootstrap a Weave project with sample data for testing and onboarding.

Generates (each step can be run individually):
  - datasets:        Publish sample datasets
  - calls:           Traced ops: nested, streaming, async, threaded, errors,
                     log_call, postprocess, sample_rate, views, Markdown/Content
  - evaluations:     Function + class scorers, custom summarize, preprocess
  - imperative-eval: EvaluationLogger with log_prediction/log_score
  - objects:         Objects, prompts (String/Messages/Easy), tags, aliases,
                     ref/get, Dataset.from_pandas

No LLM API keys are required — all models are simulated locally.

Usage:
    python scripts/bootstrap_project.py my-team/demo-project
    python scripts/bootstrap_project.py my-team/demo --steps calls datasets
    python scripts/bootstrap_project.py my-team/demo --base-url http://localhost:9994
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
from weave import ThreadPoolExecutor

# ==========================================================================
# Constants
# ==========================================================================

ALL_STEPS = ["datasets", "calls", "evaluations", "imperative-eval", "objects"]

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
    {"question": "What is 7 × 8?", "expected": "56", "category": "math"},
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

QA_KNOWLEDGE = {
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

POSITIVE_WORDS = {
    "love",
    "fantastic",
    "great",
    "excellent",
    "amazing",
    "delightful",
    "recommended",
    "perfect",
    "exceeded",
    "best",
}

NEGATIVE_WORDS = {
    "terrible",
    "worst",
    "broke",
    "hate",
    "awful",
    "horrible",
    "bad",
    "never",
    "disappointed",
    "useless",
}

ERROR_INPUTS = ["", "{bad json", "   "]


# ==========================================================================
# Simulation helpers
# ==========================================================================


def simulate_qa_answer(question: str, temperature: float) -> str:
    q_lower = question.lower()
    for key, answer in QA_KNOWLEDGE.items():
        if key in q_lower:
            if random.random() < (1.0 - temperature * 0.3):
                return answer
            return answer + " (approximately)"
    return "I'm not sure about that."


def simulate_sentiment(text: str) -> tuple[str, float]:
    words = set(text.lower().split())
    pos_count = len(words & POSITIVE_WORDS)
    neg_count = len(words & NEGATIVE_WORDS)

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


def simulate_summarization(document: str, max_length: int) -> str:
    sentences = document.replace(". ", ".\n").split("\n")
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 1:
        return document[:max_length]
    picked = [sentences[0]]
    if len(sentences) > 2:
        picked.append(random.choice(sentences[1:]))
    summary = " ".join(picked)
    if len(summary) > max_length:
        summary = summary[:max_length].rsplit(" ", 1)[0] + "..."
    return summary


# ==========================================================================
# Models
# ==========================================================================


class QAModel(weave.Model):
    """A simple Q&A model that uses keyword matching to simulate answers."""

    temperature: float = 0.7
    system_prompt: str = "You are a helpful assistant that answers questions concisely."

    @weave.op
    def predict(self, question: str) -> dict:
        answer = simulate_qa_answer(question, self.temperature)
        return {"answer": answer, "confidence": random.uniform(0.5, 1.0)}


class SentimentModel(weave.Model):
    """A simulated sentiment classifier."""

    threshold: float = 0.5

    @weave.op
    def predict(self, text: str) -> dict:
        label, score = simulate_sentiment(text)
        return {"label": label, "score": score}


class SummarizationModel(weave.Model):
    """A simulated summarization model."""

    max_length: int = 100

    @weave.op
    def predict(self, document: str) -> dict:
        summary = simulate_summarization(document, self.max_length)
        return {"summary": summary}


# ==========================================================================
# Custom objects
# ==========================================================================


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


# ==========================================================================
# Scorers
# ==========================================================================


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
        q_words = set(question.lower().split()) - {
            "what",
            "is",
            "the",
            "of",
            "a",
            "who",
            "in",
        }
        a_words = set(answer.lower().split())
        overlap = len(q_words & a_words) / max(len(q_words), 1)
        return {"relevant": overlap >= self.min_overlap, "overlap": round(overlap, 3)}


class FailureReportScorer(weave.Scorer):
    """Scorer with a custom summarize() that reports failure details."""

    @weave.op
    def score(self, *, output: Any, expected: str, **kwargs: Any) -> dict:
        answer = output.get("answer", "")
        match = answer.strip().lower() == expected.strip().lower()
        return {"match": match, "answer": answer, "expected": expected}

    @weave.op
    def summarize(self, score_rows: list) -> dict | None:
        total = len(score_rows)
        failures = [r for r in score_rows if not r.get("match", True)]
        return {
            "total": total,
            "pass_rate": (total - len(failures)) / max(total, 1),
            "failure_count": len(failures),
            "failure_examples": [
                f"got '{f['answer']}' expected '{f['expected']}'" for f in failures[:3]
            ],
        }


# ==========================================================================
# Ops — nested pipeline
# ==========================================================================


@weave.op
def retrieve_context(question: str, top_k: int = 3) -> list[str]:
    """Simulate a RAG retrieval step."""
    time.sleep(random.uniform(0.01, 0.05))
    return [f"Relevant passage {i + 1} for: {question[:40]}..." for i in range(top_k)]


@weave.op
def format_prompt(question: str, context: list[str]) -> str:
    """Format a prompt with retrieved context."""
    context_block = "\n".join(f"- {c}" for c in context)
    return f"Context:\n{context_block}\n\nQuestion: {question}\nAnswer:"


@weave.op
def generate_answer(prompt: str, temperature: float = 0.7) -> str:
    """Simulate LLM generation."""
    time.sleep(random.uniform(0.02, 0.08))
    if "Question:" in prompt:
        question = (
            prompt.rsplit("Question:", maxsplit=1)[-1]
            .split("\n", maxsplit=1)[0]
            .strip()
        )
        return simulate_qa_answer(question, temperature)
    return "I don't have enough information to answer that."


@weave.op
def rag_pipeline(question: str) -> dict:
    """A full RAG pipeline: retrieve -> format -> generate."""
    context = retrieve_context(question)
    prompt = format_prompt(question, context)
    answer = generate_answer(prompt)
    return {"answer": answer, "context": context, "prompt_length": len(prompt)}


@weave.op
def classify_text(text: str) -> dict:
    """Classify text sentiment."""
    label, score = simulate_sentiment(text)
    return {"label": label, "score": score}


@weave.op
def extract_entities(text: str) -> list[dict]:
    """Simulate named entity extraction."""
    time.sleep(random.uniform(0.01, 0.03))
    entities = []
    for word in text.split():
        cleaned = word.strip(".,!?")
        if cleaned and cleaned[0].isupper() and len(cleaned) > 1:
            entities.append(
                {
                    "text": cleaned,
                    "type": random.choice(["PERSON", "ORG", "LOC", "MISC"]),
                }
            )
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


# ==========================================================================
# Ops — streaming, async, errors, display names, views, threading
# ==========================================================================


@weave.op(call_display_name=lambda call: f"stream [{call.inputs['prompt'][:30]}...]")
def stream_tokens(prompt: str) -> Iterator[str]:
    """Simulate token-by-token LLM generation (streaming op)."""
    answer = simulate_qa_answer(prompt, temperature=0.5)
    for token in answer.split():
        time.sleep(random.uniform(0.01, 0.03))
        yield token + " "


@weave.op(call_display_name=lambda call: f"async-fetch [{call.inputs['url'][:25]}]")
async def async_fetch_data(url: str) -> dict:
    """Simulate an async data fetch."""
    await asyncio.sleep(random.uniform(0.02, 0.08))
    return {"url": url, "status": 200, "tokens": random.randint(50, 500)}


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
        raise ValueError(
            f"Malformed JSON payload: unexpected token at position 0 in: {raw_input[:50]}"
        )
    return {"parsed": raw_input.strip(), "length": len(raw_input)}


@weave.op
def analyze_with_view(text: str) -> dict:
    """An op that attaches a markdown view to its call via set_view."""
    words = text.split()
    word_count = len(words)
    char_count = len(text)
    unique_words = len({w.lower().strip(".,!?") for w in words})

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


@weave.op
def chat_turn(user_message: str) -> str:
    """A single chat turn — used inside weave.thread() to group a conversation."""
    answer = simulate_qa_answer(user_message, temperature=0.5)
    call = weave.get_current_call()
    if call and call.summary is not None:
        call.summary["message_length"] = len(answer)
    return answer


def _redact_keys(inputs: dict) -> dict:
    """Strip keys named 'api_key' — used as postprocess_inputs demo."""
    return {k: ("***" if "key" in k.lower() else v) for k, v in inputs.items()}


@weave.op(
    name="secure_lookup",
    postprocess_inputs=_redact_keys,
    postprocess_output=lambda out: {**out, "_postprocessed": True},
)
def lookup_with_key(query: str, api_key: str = "sk-demo-key-12345") -> dict:
    """Op with postprocess_inputs (redacts api_key) and postprocess_output."""
    return {"result": f"Result for: {query}", "source": "demo-api"}


@weave.op(tracing_sample_rate=0.5)
def high_volume_op(item_id: int) -> dict:
    """Op with tracing_sample_rate=0.5 — only ~half the calls are traced."""
    return {"item_id": item_id, "processed": True}


@weave.op
def generate_markdown_report(data: list[dict]) -> weave.Markdown:
    """Op that returns a weave.Markdown object for rich rendering in the UI."""
    lines = ["# Bootstrap Data Summary\n"]
    lines.append(f"Total records: **{len(data)}**\n")
    lines.append("| # | Question | Expected |")
    lines.append("|---|----------|----------|")
    for i, row in enumerate(data[:5]):
        lines.append(
            f"| {i + 1} | {row.get('question', 'N/A')} | {row.get('expected', 'N/A')} |"
        )
    if len(data) > 5:
        lines.append(f"\n*...and {len(data) - 5} more rows*")
    return weave.Markdown("\n".join(lines))


@weave.op
def generate_content_artifact(text: str) -> weave.Content:
    """Op that returns a weave.Content object (e.g. a CSV snippet)."""
    csv_body = "question,expected,category\n"
    for row in QA_EXAMPLES[:5]:
        csv_body += f"{row['question']},{row['expected']},{row['category']}\n"
    return weave.Content.from_text(csv_body, extension="csv", mimetype="text/csv")


@weave.op
def threaded_worker(task_id: int, text: str) -> dict:
    """A worker op invoked via ThreadPoolExecutor — context propagates correctly."""
    time.sleep(random.uniform(0.01, 0.03))
    label, score = simulate_sentiment(text)
    return {"task_id": task_id, "label": label, "score": score}


# ==========================================================================
# Steps
# ==========================================================================


def step_datasets() -> dict[str, weave.Dataset]:
    """Publish sample datasets."""
    print("  [datasets] Publishing datasets...")

    qa_dataset = weave.Dataset(name="qa-examples", rows=QA_EXAMPLES)
    weave.publish(qa_dataset)
    print(f"    ✓ qa-examples ({len(QA_EXAMPLES)} rows)")

    sentiment_dataset = weave.Dataset(
        name="sentiment-examples", rows=SENTIMENT_EXAMPLES
    )
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
        with weave.attributes(
            {"category": example["category"], "batch": "rag", "index": i}
        ):
            rag_pipeline(example["question"])
    print(f"    ✓ {len(QA_EXAMPLES)} RAG pipeline calls (with nested ops + attributes)")

    # Sentiment classification calls
    for i, example in enumerate(SENTIMENT_EXAMPLES):
        with weave.attributes(
            {"expected_label": example["label"], "batch": "sentiment", "index": i}
        ):
            classify_text(example["text"])
    print(
        f"    ✓ {len(SENTIMENT_EXAMPLES)} sentiment classification calls (with attributes)"
    )

    # Document processing calls (nested: classify + extract_entities)
    docs = [ex["document"] for ex in SUMMARIZATION_EXAMPLES]
    for i, doc in enumerate(docs):
        with weave.attributes({"batch": "doc-processing", "index": i}):
            process_document(doc)
    print(f"    ✓ {len(docs)} document processing calls (with nested ops)")

    # Streaming ops (custom call_display_name + yield)
    for example in QA_EXAMPLES[:3]:
        list(stream_tokens(example["question"]))
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
    for raw in ERROR_INPUTS:
        try:
            failing_parse(raw)
        except ValueError:
            pass
    failing_parse("valid input text")
    print(f"    ✓ {len(ERROR_INPUTS)} errored calls + 1 success (error states in UI)")

    # Threaded conversation (weave.thread groups calls by thread_id)
    with weave.thread() as t:
        chat_turn("Hello, what is the capital of France?")
        chat_turn("And what about Germany?")
        chat_turn("Thanks! What is 7 × 8?")
    tid = t.thread_id or "unknown"
    print(f"    ✓ 1 threaded conversation (3 turns, thread_id={tid[:12]}...)")

    # log_call: manual call logging for undecorated functions
    weave.log_call(
        op="legacy_data_transform",
        inputs={"raw_records": 150, "filter": "active"},
        output={"transformed": 142, "dropped": 8},
    )
    weave.log_call(
        op="legacy_data_transform",
        inputs={"raw_records": 0, "filter": "active"},
        output=None,
        exception=ValueError("No records to transform"),
    )
    print("    ✓ 2 manually logged calls via weave.log_call (1 success, 1 error)")

    # postprocess_inputs (redacts api_key) and postprocess_output
    lookup_with_key("weather forecast", api_key="sk-secret-key-abc123")
    lookup_with_key("stock prices")
    print("    ✓ 2 calls with postprocess_inputs/output (api_key redacted)")

    # tracing_sample_rate — only ~half will be traced
    for i in range(20):
        high_volume_op(i)
    print("    ✓ 20 high-volume calls with tracing_sample_rate=0.5 (~10 traced)")

    # Markdown output
    generate_markdown_report(QA_EXAMPLES)
    print("    ✓ 1 call returning weave.Markdown (rich rendering)")

    # Content output
    generate_content_artifact("qa data")
    print("    ✓ 1 call returning weave.Content (CSV artifact)")

    # ThreadPoolExecutor with context propagation
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(threaded_worker, i, ex["text"])
            for i, ex in enumerate(SENTIMENT_EXAMPLES[:6])
        ]
        [f.result() for f in futures]
    print("    ✓ 6 calls via ThreadPoolExecutor (context-aware threading)")


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


async def step_evaluations(datasets: dict[str, weave.Dataset] | None = None) -> None:
    """Run evaluations with different models and scorers."""
    print("  [evaluations] Running evaluations...")

    if datasets is None:
        datasets = {
            "qa": weave.Dataset(name="qa-examples", rows=QA_EXAMPLES),
            "sentiment": weave.Dataset(
                name="sentiment-examples", rows=SENTIMENT_EXAMPLES
            ),
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
        scorers=[
            exact_match,
            contains_expected,
            confidence_above_threshold,
            relevance_scorer,
        ],
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

    # Evaluation with custom Scorer.summarize and preprocess_model_input
    failure_scorer = FailureReportScorer()

    @weave.op
    def strip_category(example: dict) -> dict:
        """preprocess_model_input: remove 'category' before passing to model."""
        return {k: v for k, v in example.items() if k != "category"}

    qa_eval_v3 = weave.Evaluation(
        name="qa-with-failure-report",
        dataset=datasets["qa"],
        scorers=[failure_scorer],
        preprocess_model_input=strip_category,
    )
    qa_results_v3 = await qa_eval_v3.evaluate(qa_model)
    print(
        f"    ✓ QA eval (custom summarize + preprocess): {_format_results(qa_results_v3)}"
    )


def step_imperative_eval() -> None:
    """Log an evaluation imperatively with log_prediction / log_score / log_summary."""
    print("  [imperative-eval] Running imperative evaluation...")

    ev = weave.EvaluationLogger(name="manual-review-eval")

    for example in QA_EXAMPLES[:5]:
        answer = simulate_qa_answer(example["question"], temperature=0.5)
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

    config = PipelineConfig(
        name="default-rag-config",
        retriever_top_k=3,
        model_temperature=0.7,
        max_tokens=256,
        system_prompt="You are a helpful assistant. Answer concisely.",
    )
    weave.publish(config)
    print("    ✓ PipelineConfig: default-rag-config")

    config_v2 = PipelineConfig(
        name="creative-rag-config",
        retriever_top_k=5,
        model_temperature=0.9,
        max_tokens=512,
        system_prompt="You are a creative assistant. Provide detailed, imaginative answers.",
    )
    weave.publish(config_v2)
    print("    ✓ PipelineConfig: creative-rag-config")

    experiment = ExperimentMetadata(
        name="baseline-qa-experiment",
        hypothesis="Lowering temperature improves exact-match accuracy on factual QA",
        owner="bootstrap-script",
        tags=["baseline", "qa", "temperature-sweep"],
        notes="Comparing temperature=0.3 vs temperature=0.9 on the QA dataset.",
    )
    weave.publish(experiment)
    print("    ✓ ExperimentMetadata: baseline-qa-experiment")

    qa_prompt = weave.StringPrompt(
        "You are a helpful assistant. Answer the following question concisely "
        "and accurately. If you are unsure, say so."
    )
    qa_prompt.name = "qa-system-prompt"
    weave.publish(qa_prompt)
    print("    ✓ StringPrompt: qa-system-prompt")

    chat_prompt = weave.MessagesPrompt(
        [
            {
                "role": "system",
                "content": (
                    "You are a retrieval-augmented assistant. Use the provided "
                    "context to answer questions. Cite your sources."
                ),
            },
            {"role": "user", "content": "Context: {context}\n\nQuestion: {question}"},
        ]
    )
    chat_prompt.name = "rag-chat-prompt"
    weave.publish(chat_prompt)
    print("    ✓ MessagesPrompt: rag-chat-prompt")

    easy = weave.EasyPrompt("You are a multilingual assistant.", role="system")
    easy.append({"role": "user", "content": "Translate '{text}' to {language}."})
    easy.name = "translation-prompt"
    weave.publish(easy)
    print("    ✓ EasyPrompt: translation-prompt")

    # Tags and aliases
    config_ref = weave.publish(
        PipelineConfig(
            name="tagged-config",
            retriever_top_k=3,
            model_temperature=0.5,
            max_tokens=256,
            system_prompt="You are a precise assistant.",
        )
    )
    from weave.trace.context.weave_client_context import require_weave_client

    require_weave_client().flush()
    weave.add_tags(config_ref, ["stable", "reviewed", "v1"])
    print("    ✓ Tagged object: tagged-config (stable, reviewed, v1)")

    weave.set_aliases(config_ref, ["production", "latest-stable"])
    print("    ✓ Aliased object: tagged-config -> production, latest-stable")

    retrieved = weave.ref("tagged-config").get()
    print(
        f"    ✓ weave.ref('tagged-config').get() -> top_k={retrieved.retriever_top_k}"
    )

    try:
        import pandas as pd

        df = pd.DataFrame(
            {
                "input": ["2+2", "capital of Italy", "who wrote Hamlet"],
                "expected": ["4", "Rome", "Shakespeare"],
                "difficulty": ["easy", "medium", "medium"],
            }
        )
        pandas_ds = weave.Dataset.from_pandas(df)
        pandas_ds.name = "pandas-dataset"
        weave.publish(pandas_ds)
        print(f"    ✓ Dataset.from_pandas: pandas-dataset ({len(df)} rows)")
    except ImportError:
        print("    - Skipped Dataset.from_pandas (pandas not installed)")


# ==========================================================================
# CLI
# ==========================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap a Weave project with sample data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "available steps:\n"
            "  datasets         Publish sample datasets\n"
            "  calls            All op variants: nested, streaming, async, threaded,\n"
            "                   errors, log_call, postprocess, sample_rate, views,\n"
            "                   Markdown/Content output, ThreadPoolExecutor\n"
            "  evaluations      Function + class scorers, custom summarize,\n"
            "                   preprocess_model_input\n"
            "  imperative-eval  EvaluationLogger with log_prediction/log_score\n"
            "  objects          Objects, prompts (String/Messages/Easy), tags,\n"
            "                   aliases, ref/get, Dataset.from_pandas\n"
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

    summary_lines: list[str] = []

    datasets: dict[str, weave.Dataset] | None = None
    if "datasets" in steps:
        datasets = step_datasets()
        total = len(QA_EXAMPLES) + len(SENTIMENT_EXAMPLES) + len(SUMMARIZATION_EXAMPLES)
        summary_lines.append(f"3 published datasets ({total} total rows)")
        print()

    if "calls" in steps:
        step_calls()
        summary_lines.append(
            "Traced op calls: nested, streaming, async, threaded, errors, "
            "log_call, postprocess, sample_rate, views, Markdown/Content"
        )
        print()

    if "evaluations" in steps:
        asyncio.run(step_evaluations(datasets))
        summary_lines.append(
            "5 evaluations: function + class scorers, custom summarize, preprocess"
        )
        print()

    if "imperative-eval" in steps:
        step_imperative_eval()
        summary_lines.append("1 imperative evaluation via EvaluationLogger")
        print()

    if "objects" in steps:
        step_objects()
        summary_lines.append(
            "Objects: configs, prompts (String/Messages/Easy), tags, aliases, "
            "ref/get, Dataset.from_pandas"
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
