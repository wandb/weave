#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "requests",
# ]
# ///
"""Synthetic agent trace load generator.

Generates realistic agent conversations at scale and ingests them via the
native structured ingest endpoint. Produces data in the shapes of OpenAI
Agents, Google ADK, Claude Code / SWE-agent, and simple chat-bot
conversations, with lorem ipsum content.

Usage:
    devall uv run examples/otel_genai/load_generator.py --conversations 10000
    devall uv run examples/otel_genai/load_generator.py --conversations 1000000 --concurrency 50
"""

import argparse
import json
import os
import random
import string
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests

LOREM_WORDS = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua ut enim ad minim "
    "veniam quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat duis aute irure dolor in reprehenderit in voluptate "
    "velit esse cillum dolore eu fugiat nulla pariatur excepteur sint occaecat "
    "cupidatat non proident sunt in culpa qui officia deserunt mollit anim id "
    "est laborum the agent processed the request and returned results after "
    "analyzing multiple data sources including the knowledge base and external "
    "apis the model generated a comprehensive response based on the context "
    "provided by the user and the retrieved information from various tools "
    "error occurred during processing retry attempt was successful after "
    "fallback to alternative model configuration the system identified "
    "relevant patterns in the data and synthesized an actionable summary "
    "weather forecast indicates clear skies with temperatures ranging between "
    "seventy and eighty degrees fahrenheit the database query returned fifteen "
    "results matching the search criteria including recent transactions and "
    "historical records the file contains approximately three hundred lines "
    "of python code implementing the authentication middleware component "
    "terminal output shows all tests passing with coverage at ninety two "
    "percent the deployment pipeline completed successfully across staging "
    "and production environments the api response included pagination tokens "
    "for the next batch of results the code review identified three potential "
    "issues related to error handling and input validation the function was "
    "refactored to improve performance by reducing unnecessary allocations"
).split()

# ---------------------------------------------------------------------------
# Agent templates
# ---------------------------------------------------------------------------

TEMPLATES = {
    "openai_agents": {
        "provider": "openai",
        "agents": [
            {"name": "TriageAgent", "model": "o4-mini",
             "system": "You are a helpful concierge that routes requests to specialists."},
            {"name": "WeatherBot", "model": "gpt-4o-mini",
             "system": "You report weather using the get_weather tool."},
            {"name": "TravelAdvisor", "model": "gpt-4o-mini",
             "system": "You plan trips using search_flights and search_hotels."},
            {"name": "Translator", "model": "gpt-4o-mini",
             "system": "You translate text between languages."},
            {"name": "ResearchAgent", "model": "gpt-4o",
             "system": "You conduct research using web_search and database tools."},
        ],
        "tools": [
            "get_weather", "search_flights", "search_hotels", "translate_text",
            "web_search", "database_query", "calculate", "send_email",
            "transfer_to_WeatherBot", "transfer_to_TravelAdvisor",
            "transfer_to_Translator", "transfer_to_ResearchAgent",
        ],
        "turns_range": (3, 7),
        "tools_per_turn": (0, 3),
    },
    "google_adk": {
        "provider": "google",
        "agents": [
            {"name": "Coordinator", "model": "gemini-2.0-flash",
             "system": "You coordinate between specialist agents for complex tasks."},
            {"name": "WeatherAgent", "model": "gemini-2.0-flash",
             "system": "You provide weather forecasts and climate data."},
            {"name": "MathAgent", "model": "gemini-2.5-pro",
             "system": "You solve mathematical problems and do calculations."},
            {"name": "ImageAgent", "model": "gemini-2.0-flash",
             "system": "You generate and analyze images."},
        ],
        "tools": [
            "get_weather", "calculate", "generate_image", "analyze_data",
            "fetch_news", "convert_units", "plot_chart",
        ],
        "turns_range": (2, 5),
        "tools_per_turn": (1, 3),
    },
    "swe_agent": {
        "provider": "anthropic",
        "agents": [
            {"name": "swe-agent", "model": "claude-sonnet-4-20250514",
             "system": "You are an expert software engineer. Fix bugs by reading code and running tests."},
            {"name": "code-reviewer", "model": "claude-sonnet-4-20250514",
             "system": "You review code changes for correctness, style, and performance."},
            {"name": "cursor-agent", "model": "claude-opus-4-20250514",
             "system": "You assist with coding tasks in the IDE."},
        ],
        "tools": [
            "read_file", "edit_file", "run_command", "bash", "grep",
            "write_file", "list_directory", "search_codebase",
            "run_tests", "git_diff", "git_commit",
        ],
        "turns_range": (2, 10),
        "tools_per_turn": (2, 5),
    },
    "chat_bot": {
        "provider": "openai",
        "agents": [
            {"name": "chat-assistant", "model": "gpt-4o-mini",
             "system": "You are a helpful assistant."},
            {"name": "support-bot", "model": "gpt-4o-mini",
             "system": "You help customers with product questions and issues."},
            {"name": "tutor-bot", "model": "gemini-2.0-flash",
             "system": "You explain concepts clearly and help students learn."},
        ],
        "tools": [],
        "turns_range": (1, 5),
        "tools_per_turn": (0, 0),
    },
}

TEMPLATE_WEIGHTS = {
    "openai_agents": 0.30,
    "google_adk": 0.20,
    "swe_agent": 0.30,
    "chat_bot": 0.20,
}

CONVERSATION_NAMES = [
    "Debug failing test", "Plan Tokyo trip", "Weather check",
    "Code review PR #4521", "Translate docs to Japanese", "Research quantum computing",
    "Fix auth middleware", "Hotel recommendations", "Data analysis pipeline",
    "Refactor database layer", "Deploy staging", "Customer support ticket",
    "Write unit tests", "API design review", "Performance optimization",
    "Security audit", "Migration planning", "Bug triage",
    "Feature specification", "Architecture review", "Cost analysis",
    "Model comparison", "Prompt engineering", "Dataset preparation",
    "Evaluation pipeline", "Agent benchmarking", "Tool integration",
    "Error handling improvement", "Documentation update", "CI/CD setup",
]

# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------

def lorem(n_words: int) -> str:
    """Generate n_words of lorem ipsum text."""
    return " ".join(random.choices(LOREM_WORDS, k=n_words))


def lorem_json(n_keys: int = 3) -> str:
    """Generate a JSON dict with random keys and values."""
    d = {}
    keys = random.sample(
        ["path", "city", "query", "command", "file", "pattern", "model",
         "temperature", "limit", "offset", "format", "language", "units",
         "date", "origin", "destination", "checkin", "checkout", "prompt"],
        k=min(n_keys, 15),
    )
    for k in keys:
        if random.random() < 0.3:
            d[k] = random.randint(1, 1000)
        elif random.random() < 0.5:
            d[k] = round(random.uniform(0, 1), 2)
        else:
            d[k] = lorem(random.randint(1, 5))
    return json.dumps(d)


def make_tool_result(tool_name: str) -> str:
    """Generate a realistic-ish tool result based on tool type."""
    if tool_name in ("read_file", "search_codebase", "grep", "list_directory"):
        lines = random.randint(10, 50)
        return "\n".join(
            f"{'  ' * random.randint(0, 3)}{lorem(random.randint(3, 12))}"
            for _ in range(lines)
        )
    if tool_name in ("bash", "run_command", "run_tests"):
        lines = random.randint(5, 30)
        return "\n".join(
            f"$ {lorem(random.randint(2, 8))}" if i == 0 else lorem(random.randint(3, 15))
            for i in range(lines)
        )
    if tool_name in ("get_weather",):
        city = random.choice(["Tokyo", "Paris", "London", "NYC", "Barcelona", "Sydney"])
        temp = random.randint(40, 95)
        return f"Weather in {city}: {random.choice(['Clear', 'Cloudy', 'Rainy', 'Sunny'])}, {temp}°F, humidity {random.randint(20, 90)}%"
    if tool_name in ("search_flights", "search_hotels"):
        return "\n".join(
            f"  {i}) {lorem(random.randint(8, 15))} — ${random.randint(100, 800)}"
            for i in range(1, random.randint(3, 6))
        )
    return lorem(random.randint(50, 500))


# ---------------------------------------------------------------------------
# Conversation builder
# ---------------------------------------------------------------------------

def build_conversation(
    conv_index: int,
    rng: random.Random,
    time_start: datetime,
    time_end: datetime,
) -> dict:
    """Build a single conversation payload for /genai/conversations/ingest."""
    template_name = rng.choices(
        list(TEMPLATE_WEIGHTS.keys()),
        weights=list(TEMPLATE_WEIGHTS.values()),
    )[0]
    tmpl = TEMPLATES[template_name]

    agent = rng.choice(tmpl["agents"])
    conv_id = str(uuid.UUID(int=rng.getrandbits(128)))
    conv_name = rng.choice(CONVERSATION_NAMES)

    n_turns = rng.randint(*tmpl["turns_range"])

    conv_start = time_start + timedelta(
        seconds=rng.uniform(0, (time_end - time_start).total_seconds())
    )

    turns = []
    cursor = conv_start

    for t_idx in range(n_turns):
        turn_agent = agent if rng.random() < 0.6 else rng.choice(tmpl["agents"])
        turn_duration = timedelta(seconds=rng.uniform(0.5, 30))
        turn_start = cursor.isoformat()
        turn_end = (cursor + turn_duration).isoformat()

        messages = []
        user_text = lorem(rng.randint(10, 50))
        messages.append({"role": "user", "content": user_text})

        assistant_text = lorem(rng.randint(30, 300))
        messages.append({"role": "assistant", "content": assistant_text})

        tool_calls = []
        if tmpl["tools"]:
            n_tools = rng.randint(*tmpl["tools_per_turn"])
            for _ in range(n_tools):
                tool_name = rng.choice(tmpl["tools"])
                tool_calls.append({
                    "tool_name": tool_name,
                    "arguments": lorem_json(rng.randint(2, 5)),
                    "result": make_tool_result(tool_name),
                    "duration_ms": rng.randint(50, 5000),
                })
            if tool_calls:
                follow_up = lorem(rng.randint(20, 100))
                messages.append({"role": "assistant", "content": follow_up})

        reasoning = ""
        if rng.random() < 0.20:
            reasoning = lorem(rng.randint(100, 500))

        input_text = user_text
        output_text = assistant_text + " ".join(m["content"] for m in messages if m["role"] == "assistant")
        for tc in tool_calls:
            input_text += " " + tc["arguments"]
            output_text += " " + tc["result"]

        turn = {
            "messages": messages,
            "tool_calls": tool_calls,
            "agent_name": turn_agent["name"],
            "model": turn_agent["model"],
            "input_tokens": max(1, len(input_text) // 4),
            "output_tokens": max(1, len(output_text) // 4),
            "reasoning_content": reasoning,
            "system_instructions": [turn_agent["system"]] if t_idx == 0 else [],
            "started_at": turn_start,
            "ended_at": turn_end,
        }
        turns.append(turn)

        cursor += turn_duration + timedelta(seconds=rng.uniform(60, 3600))

    status = "ok"
    r = rng.random()
    if r < 0.03:
        status = "error"
    elif r < 0.05:
        status = "unset"

    return {
        "conversation_id": conv_id,
        "conversation_name": f"{conv_name} #{conv_index}",
        "agent_name": agent["name"],
        "provider_name": tmpl["provider"],
        "turns": turns,
    }


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def _url():
    """Get trace server URL."""
    return os.environ.get("WF_TRACE_SERVER_URL", "http://localhost:6345").rstrip("/")


def _auth():
    """Get auth tuple."""
    key = os.environ.get("WANDB_API_KEY", "")
    return ("api", key) if key else None


def ingest_conversation(payload: dict, project_id: str) -> dict:
    """POST one conversation to the ingest endpoint."""
    url = f"{_url()}/genai/conversations/ingest"
    params = {"project_id": project_id}
    try:
        r = requests.post(url, json=payload, params=params, auth=_auth(), timeout=60)
        if r.status_code == 200:
            return r.json()
        return {"error": r.status_code, "text": r.text[:200]}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic agent traces at scale"
    )
    parser.add_argument(
        "--conversations", type=int, default=10_000,
        help="Total conversations to generate (default: 10000)",
    )
    parser.add_argument(
        "--project", type=str, default=None,
        help="Project ID (default: {WANDB_ENTITY}/lorem-ipsum)",
    )
    parser.add_argument(
        "--server", type=str, default=None,
        help="Trace server URL (default: WF_TRACE_SERVER_URL or localhost:6345)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=20,
        help="Parallel HTTP requests (default: 20)",
    )
    parser.add_argument(
        "--time-span-days", type=int, default=30,
        help="Spread data across N days (default: 30)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    args = parser.parse_args()

    if args.server:
        os.environ["WF_TRACE_SERVER_URL"] = args.server

    entity = os.environ.get("WANDB_ENTITY", "ben-urmomsclothes")
    project_id = args.project or f"{entity}/lorem-ipsum"

    print("=" * 60)
    print("Synthetic Agent Trace Load Generator")
    print("=" * 60)
    print(f"  Server:        {_url()}")
    print(f"  Project:       {project_id}")
    print(f"  Conversations: {args.conversations:,}")
    print(f"  Concurrency:   {args.concurrency}")
    print(f"  Time span:     {args.time_span_days} days")
    print(f"  Seed:          {args.seed}")
    print("=" * 60)
    print()

    time_end = datetime.now(timezone.utc)
    time_start = time_end - timedelta(days=args.time_span_days)

    master_rng = random.Random(args.seed)
    seeds = [master_rng.randint(0, 2**63) for _ in range(args.conversations)]

    payloads = []
    gen_start = time.time()
    for i, seed in enumerate(seeds):
        rng = random.Random(seed)
        payload = build_conversation(i, rng, time_start, time_end)
        payloads.append(payload)
        if (i + 1) % 10_000 == 0:
            print(f"  Generated {i + 1:,} conversations...")

    gen_elapsed = time.time() - gen_start
    total_turns = sum(len(p["turns"]) for p in payloads)
    print(f"\nGenerated {len(payloads):,} conversations ({total_turns:,} turns) in {gen_elapsed:.1f}s")
    print(f"Starting ingestion with {args.concurrency} workers...\n")

    ingested = 0
    errors = 0
    total_spans = 0
    ingest_start = time.time()

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(ingest_conversation, p, project_id): i
            for i, p in enumerate(payloads)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                if "error" in result:
                    errors += 1
                else:
                    ingested += 1
                    total_spans += result.get("span_count", 0)
            except Exception:
                errors += 1

            done = ingested + errors
            if done % 1000 == 0 or done == len(payloads):
                elapsed = time.time() - ingest_start
                rate = done / max(elapsed, 0.001)
                eta = (len(payloads) - done) / max(rate, 0.001)
                print(
                    f"  [{done:,}/{len(payloads):,}] "
                    f"{ingested:,} ok, {errors:,} err | "
                    f"{rate:.0f} conv/s | "
                    f"~{total_spans:,} spans | "
                    f"ETA {eta:.0f}s"
                )

    ingest_elapsed = time.time() - ingest_start
    total_elapsed = time.time() - gen_start

    print()
    print("=" * 60)
    print("Done!")
    print(f"  Conversations: {ingested:,} ingested, {errors:,} errors")
    print(f"  Total spans:   ~{total_spans:,}")
    print(f"  Total turns:   {total_turns:,}")
    print(f"  Ingest time:   {ingest_elapsed:.1f}s ({ingested / max(ingest_elapsed, 0.001):.0f} conv/s)")
    print(f"  Total time:    {total_elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
