#!/usr/bin/env python3
"""Turn-by-turn conversation logging with weave.agents.conversation.

Demonstrates the imperative SDK for logging agent conversations one turn
at a time. Each flush() sends a single turn to the server — no OTel SDK
required, just HTTP.

Usage:
    devall uv run examples/otel_genai/turn_by_turn_example.py
"""

import os

from weave.agents.conversation import conversation


def main():
    project = os.environ.get("WANDB_ENTITY", "ben-urmomsclothes") + "/genai-otel-test"
    server = os.environ.get("WF_TRACE_SERVER_URL", "http://localhost:6345")

    print(f"Server: {server}")
    print(f"Project: {project}")
    print()

    # -- Example 1: Simple multi-turn conversation --
    print("=" * 50)
    print("Example 1: Weather agent — 2 turns")
    print("=" * 50)

    conv = conversation(
        agent_name="weather-agent",
        model="gpt-4o",
        project=project,
        server_url=server,
        conversation_name="Tokyo & Osaka Weather",
    )
    print(f"Conversation ID: {conv.conversation_id}")

    # Turn 1
    conv.system("You are a helpful weather assistant.")
    conv.user("What's the weather in Tokyo?")
    conv.assistant("Let me check that for you.")
    conv.tool_call(
        "get_weather",
        arguments={"city": "Tokyo", "units": "fahrenheit"},
        result="Clear skies, 75°F, humidity 45%",
    )
    conv.assistant("It's currently clear and 75°F in Tokyo with 45% humidity.")
    conv.metrics(input_tokens=150, output_tokens=42)
    result = conv.flush()
    print(f"  Turn 1: {result}")

    # Turn 2
    conv.user("What about Osaka?")
    conv.tool_call(
        "get_weather",
        arguments={"city": "Osaka", "units": "fahrenheit"},
        result="Partly cloudy, 72°F, humidity 55%",
    )
    conv.assistant("Osaka is partly cloudy at 72°F with 55% humidity.")
    conv.metrics(input_tokens=180, output_tokens=38)
    result = conv.flush()
    print(f"  Turn 2: {result}")

    print(f"  Total turns flushed: {conv.turns_flushed}")
    print()

    # -- Example 2: Coding agent with tool calls --
    print("=" * 50)
    print("Example 2: Coding agent — debug session")
    print("=" * 50)

    conv2 = conversation(
        agent_name="swe-agent",
        model="claude-sonnet-4-20250514",
        project=project,
        server_url=server,
        conversation_name="Fix failing test",
    )
    print(f"Conversation ID: {conv2.conversation_id}")

    # Turn 1: investigate
    conv2.system(
        "You are an expert software engineer. Fix bugs by reading code and running tests."
    )
    conv2.user("The test_login test is failing. Can you fix it?")
    conv2.assistant("I'll look at the test first to understand what's expected.")
    conv2.tool_call(
        "read_file",
        arguments={"path": "tests/test_login.py"},
        result='def test_login():\n    resp = client.post("/login", json={"user": "admin", "pass": "secret"})\n    assert resp.status_code == 200',
    )
    conv2.assistant(
        "The test expects a 200 from /login. Let me check the route handler."
    )
    conv2.tool_call(
        "read_file",
        arguments={"path": "app/routes/auth.py"},
        result='@app.post("/login")\ndef login(data):\n    if data.user == "admin":\n        return {"token": "..."}, 200\n    return {"error": "unauthorized"}, 401',
    )
    conv2.assistant(
        "I see — the route reads `data.user` but the test sends `user` in the JSON body. The Pydantic model likely expects `username`. Let me check."
    )
    conv2.metrics(input_tokens=420, output_tokens=95)
    result = conv2.flush()
    print(f"  Turn 1 (investigate): {result}")

    # Turn 2: fix
    conv2.user("Yes, please fix it.")
    conv2.tool_call(
        "edit_file",
        arguments={
            "path": "app/routes/auth.py",
            "old": "data.user",
            "new": "data.username",
        },
        result="File edited successfully",
    )
    conv2.tool_call(
        "run_command",
        arguments={"command": "pytest tests/test_login.py -v"},
        result="tests/test_login.py::test_login PASSED\n\n1 passed in 0.3s",
    )
    conv2.assistant(
        "Fixed! The issue was that the route was reading `data.user` but the model field is `data.username`. Test passes now."
    )
    conv2.metrics(input_tokens=380, output_tokens=52)
    result = conv2.flush()
    print(f"  Turn 2 (fix): {result}")

    print(f"  Total turns flushed: {conv2.turns_flushed}")
    print()

    # -- Example 3: Auto-flush on turn boundary --
    print("=" * 50)
    print("Example 3: Auto-flush (no explicit flush between turns)")
    print("=" * 50)

    conv3 = conversation(
        agent_name="chat-bot",
        model="gpt-4o-mini",
        project=project,
        server_url=server,
        conversation_name="Auto-flush demo",
    )
    print(f"Conversation ID: {conv3.conversation_id}")

    # These auto-flush: user() after assistant content triggers flush
    conv3.user("Hello!")
    conv3.assistant("Hi! How can I help you?")
    conv3.metrics(input_tokens=10, output_tokens=8)

    conv3.user("What is 2+2?")  # auto-flushes the previous turn
    print(f"  After second user(): turns_flushed={conv3.turns_flushed}")

    conv3.assistant("2 + 2 = 4")
    conv3.metrics(input_tokens=15, output_tokens=5)

    conv3.user("Thanks!")  # auto-flushes again
    print(f"  After third user(): turns_flushed={conv3.turns_flushed}")

    conv3.assistant("You're welcome!")
    conv3.flush()  # explicit flush for the last turn
    print(f"  After final flush(): turns_flushed={conv3.turns_flushed}")
    print()

    # -- Example 4: ATIF export --
    print("=" * 50)
    print("Example 4: Export conversation as ATIF")
    print("=" * 50)
    print(f"  Exporting conversation {conv.conversation_id[:16]}...")
    atif = conv.export_atif()
    if atif and "trajectory" in atif:
        traj = atif["trajectory"]
        print(f"  ATIF schema: {traj.get('schema_version', '?')}")
        print(f"  Agent: {traj.get('agent', {}).get('name', '?')}")
        print(f"  Steps: {len(traj.get('steps', []))}")
    elif atif:
        print(f"  Response: {list(atif.keys())}")
    else:
        print("  Export not available (server may not support it yet)")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
