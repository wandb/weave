"""A tiny script that answers questions with the OpenAI chat API. No framework, no agent loop."""

from __future__ import annotations

from openai import OpenAI

MODEL = "gpt-4o-mini"

client = OpenAI()

QUESTIONS = [
    "In one sentence, what is the capital of France?",
    "In one sentence, what causes ocean tides?",
    "In one sentence, who wrote Pride and Prejudice?",
]


def answer(question: str) -> str:
    """Ask the model a single question and return its answer."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Answer concisely."},
            {"role": "user", "content": question},
        ],
    )
    return response.choices[0].message.content or ""


def main() -> None:
    for question in QUESTIONS:
        print(f"Q: {question}")
        print(f"A: {answer(question)}\n")


if __name__ == "__main__":
    main()
