"""Entry point: ask the agent a couple of questions."""

from __future__ import annotations

from agent import run_agent

QUESTIONS = [
    "What's the weather in Tokyo, and tell me one fact about the city?",
    "What's the weather in Paris?",
]


def main() -> None:
    for question in QUESTIONS:
        print(f"USER:  {question}")
        answer = run_agent(question)
        print(f"AGENT: {answer}\n")


if __name__ == "__main__":
    main()
