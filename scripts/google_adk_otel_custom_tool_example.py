"""Example: log a custom ADK tool to the Weave GenAI OTLv2 endpoint.

This is the "real objects" companion to ``google_adk_otel_example.py``. The
other example uses lightweight dataclasses so it runs anywhere; this one
defines a custom Python tool (``get_weather``), wraps it with ADK's real
``FunctionTool``, actually executes the user code through ``tool.run_async``,
and threads the resulting ``google.genai.types`` event back into ADK's
tracing layer. ``weave.integrations.patch_google_adk()`` enriches each
emitted span so the dedicated Weave OTLv2 columns get populated.

Flow:

  1. ``weave.init("megatruong/adk-test")`` installs the global OTel
     ``TracerProvider`` with a ``BatchSpanProcessor`` pointing at
     ``/agents/otel/v1/traces``.
  2. We define ``get_weather(city, units)`` and ``convert_currency(...)``,
     wrap them with ``google.adk.tools.FunctionTool``, and bind them to a
     real ``LlmAgent``.
  3. For each tool we open an OTel ``execute_tool`` span, ``await
     tool.run_async``, then call ``trace_tool_call`` with the resulting
     ``google.genai.types`` ``Event``. The patched ``trace_tool_call``
     adds ``gen_ai.tool.call.{arguments,result}`` plus
     ``gen_ai.provider.name``.
  4. An ``invoke_agent`` span wraps the whole turn and is enriched by
     ``trace_agent_invocation`` (agent name/description/id, conversation
     id, provider, model).
  5. A ``call_llm`` span is enriched by ``trace_call_llm`` with the full
     OTLv2 request/response/usage column set, including the parts-model
     ``gen_ai.input.messages``/``gen_ai.output.messages`` and the
     ``gen_ai.tool.definitions`` derived from the agent's declared tools.

Run:

    uv venv --python 3.12 --clear
    source .venv/bin/activate
    uv pip install -e . 'google-adk>=1.17.0'
    export WANDB_API_KEY=...          # or run ``wandb login`` once
    python scripts/google_adk_otel_custom_tool_example.py

Override the project with ``WEAVE_ADK_EXAMPLE_PROJECT``; defaults to
``megatruong/adk-test``.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.llm_agent import LlmAgent
from google.adk.events.event import Event
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

import weave
from weave.integrations.google_adk.google_adk_sdk import (
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_AGENT_ID,
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OPERATION_NAME,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_OUTPUT_TYPE,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_REQUEST_TOP_P,
    GEN_AI_RESPONSE_FINISH_REASONS,
    GEN_AI_RESPONSE_ID,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM_INSTRUCTIONS,
    GEN_AI_TOOL_CALL_ARGUMENTS,
    GEN_AI_TOOL_CALL_ID,
    GEN_AI_TOOL_CALL_RESULT,
    GEN_AI_TOOL_DEFINITIONS,
    GEN_AI_TOOL_DESCRIPTION,
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_TYPE,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    get_google_adk_patcher,
)
from weave.trace.urls import otel_traces_endpoint, project_weave_root_url

EXPECTED_EXECUTE_TOOL_KEYS = {
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_TYPE,
    GEN_AI_TOOL_CALL_ID,
    GEN_AI_TOOL_DESCRIPTION,
    GEN_AI_TOOL_CALL_ARGUMENTS,
    GEN_AI_TOOL_CALL_RESULT,
}

EXPECTED_INVOKE_AGENT_KEYS = {
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_AGENT_NAME,
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_AGENT_ID,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_REQUEST_MODEL,
}

EXPECTED_CALL_LLM_KEYS = {
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_RESPONSE_ID,
    GEN_AI_REQUEST_TEMPERATURE,
    GEN_AI_REQUEST_TOP_P,
    GEN_AI_REQUEST_MAX_TOKENS,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_SYSTEM_INSTRUCTIONS,
    GEN_AI_TOOL_DEFINITIONS,
    GEN_AI_RESPONSE_FINISH_REASONS,
    GEN_AI_OUTPUT_TYPE,
}


# --------------------------------------------------------------------------
# Custom tool — a real Python function the agent can call. This is the
# "user code" you want logged. Docstring + type hints are surfaced as
# the tool's description and parameter schema by ADK.
# --------------------------------------------------------------------------


def get_weather(city: str, units: str = "metric") -> dict[str, Any]:
    """Look up the current weather for a city.

    Args:
        city: The city to look up, e.g. "Paris".
        units: ``"metric"`` for Celsius (default) or ``"imperial"`` for
            Fahrenheit.

    Returns:
        A dict with ``city``, ``temperature``, ``unit`` and a textual
        ``conditions`` summary.
    """
    fake_db = {
        "Paris": {"c": 18, "conditions": "cloudy"},
        "Tokyo": {"c": 22, "conditions": "sunny"},
        "New York": {"c": 9, "conditions": "rainy"},
    }
    entry = fake_db.get(city, {"c": 15, "conditions": "unknown"})
    if units == "imperial":
        return {
            "city": city,
            "temperature": round(entry["c"] * 9 / 5 + 32, 1),
            "unit": "F",
            "conditions": entry["conditions"],
        }
    return {
        "city": city,
        "temperature": entry["c"],
        "unit": "C",
        "conditions": entry["conditions"],
    }


def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict[str, Any]:
    """Convert an amount between two ISO-4217 currency codes.

    Args:
        amount: Source amount.
        from_currency: ISO code to convert from (e.g. ``"USD"``).
        to_currency: ISO code to convert to (e.g. ``"JPY"``).

    Returns:
        A dict with the converted ``amount`` and a frozen ``rate`` used.
    """
    fake_rates = {("USD", "JPY"): 150.2, ("USD", "EUR"): 0.92, ("USD", "GBP"): 0.79}
    rate = fake_rates.get((from_currency, to_currency))
    if rate is None:
        raise ValueError(f"No rate for {from_currency} -> {to_currency}")
    return {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "rate": rate,
        "amount": round(amount * rate, 2),
    }


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def _function_response_event(
    *, call_id: str, tool_name: str, response: Any, event_id: str
) -> Event:
    """Build a real ADK ``Event`` carrying a tool function response.

    Mirrors what ADK constructs in its runner after a tool returns, so
    ``trace_tool_call`` reads ``call_id`` / ``response`` through the same
    code path it uses in production.
    """
    fr = types.FunctionResponse(id=call_id, name=tool_name, response=response)
    part = types.Part(function_response=fr)
    content = types.Content(role="user", parts=[part])
    return Event(
        id=event_id,
        author="trip_planner",
        content=content,
        invocation_id="inv-custom-tool-001",
    )


def _build_llm_request(agent: LlmAgent, user_question: str) -> LlmRequest:
    """Build a real ``LlmRequest`` for the agent's first turn.

    ``trace_call_llm`` walks ``llm_request.contents`` and
    ``llm_request.config`` exactly as it would in production; this lets
    the example exercise the full parts-model serializer in
    ``weave/integrations/google_adk/google_adk_sdk.py``.
    """
    tools = [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={"city": types.Schema(type=types.Type.STRING)},
                    ),
                )
                for tool in agent.tools
                if isinstance(tool, FunctionTool)
            ]
        )
    ]
    config = types.GenerateContentConfig(
        temperature=0.3,
        top_p=0.95,
        max_output_tokens=1024,
        system_instruction=(
            "You are a precise travel planner. Use the get_weather and "
            "convert_currency tools when relevant."
        ),
        tools=tools,
    )
    contents = [
        types.Content(role="user", parts=[types.Part(text=user_question)]),
    ]
    return LlmRequest(model=agent.model, contents=contents, config=config)


def _build_llm_response(answer: str) -> LlmResponse:
    """Build a realistic ``LlmResponse`` covering the OTLv2 usage columns."""
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=answer)]),
        finish_reason=types.FinishReason.STOP,
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=210,
            candidates_token_count=88,
            thoughts_token_count=12,
            cached_content_token_count=20,
        ),
        model_version="gemini-2.0-flash-2025-01",
        # ADK calls this field ``interaction_id``; the Weave integration maps
        # it to ``gen_ai.response.id`` on the emitted span.
        interaction_id="resp-custom-tool-9988",
    )


def _attr_lines(span: Any, *, limit: int = 80) -> list[str]:
    lines = []
    for key in sorted((span.attributes or {}).keys()):
        value = span.attributes[key]
        rendered = (
            value[:limit] + "..."
            if isinstance(value, str) and len(value) > limit
            else value
        )
        lines.append(f"    {key} = {rendered!r}")
    return lines


def _print_section(title: str, span: Any, required: set[str]) -> list[str]:
    print(f"\n## {title}")
    present = set((span.attributes or {}).keys())
    for line in _attr_lines(span):
        print(line)
    missing = sorted(required - present)
    if missing:
        print(f"  MISSING required keys: {missing}")
        return missing
    return []


async def _run() -> None:
    project = os.environ.get("WEAVE_ADK_EXAMPLE_PROJECT", "megatruong/adk-test")

    # 1. weave.init() installs the global OTel TracerProvider pointed at the
    # GenAI OTLP endpoint. Tee an in-memory exporter onto the same provider
    # so we can verify wire contents without round-tripping.
    client = weave.init(project)
    entity_name = client.entity
    project_name = client.project

    provider = otel_trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        raise TypeError(
            "weave.init() did not install an OTel TracerProvider. Set "
            "WF_TRACE_SERVER_URL and WANDB_API_KEY, then re-run."
        )
    in_memory = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(in_memory))

    patcher = get_google_adk_patcher()
    if not patcher.attempt_patch():
        raise RuntimeError(
            "Failed to patch google.adk.telemetry.tracing — is google-adk installed?"
        )

    try:
        from google.adk.telemetry.tracing import (
            trace_agent_invocation,
            trace_call_llm,
            trace_tool_call,
        )

        # 2. Construct real ADK objects with the custom tools.
        weather_tool = FunctionTool(get_weather)
        currency_tool = FunctionTool(convert_currency)
        agent = LlmAgent(
            name="trip_planner",
            description="Plans multi-city itineraries with live weather + currency lookup.",
            model="gemini-2.0-flash",
            tools=[weather_tool, currency_tool],
        )

        session_service = InMemorySessionService()
        session = await session_service.create_session(
            app_name="adk-otel-demo",
            user_id="megatruong",
            session_id="conv-custom-tool-001",
        )
        ctx = InvocationContext(
            invocation_id="inv-custom-tool-001",
            agent=agent,
            session=session,
            session_service=session_service,
        )

        tracer = otel_trace.get_tracer("weave-adk-custom-tool-example")
        captured_spans: dict[str, Any] = {}

        # Run each custom tool's Python implementation up front so we can build
        # the response events that ADK's runner would normally hand to
        # ``trace_tool_call``.
        weather_args = {"city": "Paris", "units": "metric"}
        weather_result = await weather_tool.run_async(
            args=weather_args, tool_context=None
        )
        currency_args = {"amount": 1000, "from_currency": "USD", "to_currency": "JPY"}
        currency_result = await currency_tool.run_async(
            args=currency_args, tool_context=None
        )

        llm_request_one = _build_llm_request(
            agent,
            "What's the weather in Paris, and how much is 1000 USD in JPY?",
        )
        llm_response_one = _build_llm_response(
            "Paris is 18C and cloudy; 1000 USD is about 150,200 JPY."
        )

        # 3. One trace per turn. ``invoke_agent`` is the root, and the
        # ``execute_tool`` / ``call_llm`` spans are nested children — that
        # matches what ADK's runner produces and lets Weave's chat view group
        # everything into a single agent turn.
        with tracer.start_as_current_span("invoke_agent trip_planner") as invoke_span:
            trace_agent_invocation(invoke_span, agent, ctx)
            trace_id_hex = f"{invoke_span.context.trace_id:032x}"

            # Initial LLM call that "decides" to use the tools.
            with tracer.start_as_current_span(
                "call_llm gemini-2.0-flash"
            ) as llm_span:
                trace_call_llm(
                    ctx,
                    "event-llm-001",
                    llm_request_one,
                    llm_response_one,
                    span=llm_span,
                )

            # Tool execution spans — nested under invoke_agent so they share
            # the trace and parent_span_id properly resolves on the server.
            with tracer.start_as_current_span(
                "execute_tool get_weather"
            ) as tool_span:
                trace_tool_call(
                    weather_tool,
                    weather_args,
                    _function_response_event(
                        call_id="call-weather-001",
                        tool_name=weather_tool.name,
                        response=weather_result,
                        event_id="event-tool-001",
                    ),
                    error=None,
                    span=tool_span,
                )

            with tracer.start_as_current_span(
                "execute_tool convert_currency"
            ) as currency_span:
                trace_tool_call(
                    currency_tool,
                    currency_args,
                    _function_response_event(
                        call_id="call-currency-001",
                        tool_name=currency_tool.name,
                        response=currency_result,
                        event_id="event-tool-002",
                    ),
                    error=None,
                    span=currency_span,
                )

            # Follow-up LLM call that "uses" the tool results to answer.
            llm_request_two = _build_llm_request(
                agent,
                "Summarise the weather in Paris and the USD→JPY conversion.",
            )
            llm_response_two = _build_llm_response(
                "Paris is 18C and cloudy. 1000 USD converts to 150,200 JPY."
            )
            with tracer.start_as_current_span(
                "call_llm gemini-2.0-flash"
            ) as llm_span_two:
                trace_call_llm(
                    ctx,
                    "event-llm-002",
                    llm_request_two,
                    llm_response_two,
                    span=llm_span_two,
                )

        # Force flush so both the in-memory exporter and the BatchSpanProcessor
        # have handed every span downstream before we print the summary.
        provider.force_flush()

        for span in in_memory.get_finished_spans():
            captured_spans[span.name] = span

        # 6. Report what landed on each span + what reached the ingest endpoint.
        all_missing: list[str] = []
        for title, span_name, required in (
            ("invoke_agent (trip_planner)", "invoke_agent trip_planner", EXPECTED_INVOKE_AGENT_KEYS),
            ("execute_tool get_weather (custom tool)", "execute_tool get_weather", EXPECTED_EXECUTE_TOOL_KEYS),
            ("execute_tool convert_currency (custom tool)", "execute_tool convert_currency", EXPECTED_EXECUTE_TOOL_KEYS),
            ("call_llm gemini-2.0-flash", "call_llm gemini-2.0-flash", EXPECTED_CALL_LLM_KEYS),
        ):
            span = captured_spans.get(span_name)
            if span is None:
                print(f"\n## {title}\n  ERROR: span not exported")
                all_missing.append(title)
                continue
            missing = _print_section(title, span, required)
            if missing:
                all_missing.append(f"{title} missing {missing}")

        if all_missing:
            print("\nFAIL: incomplete OTLv2 coverage:")
            for entry in all_missing:
                print(f"  - {entry}")
            raise SystemExit(1)

        print(
            "\nOK: custom-tool execute_tool spans and surrounding agent/LLM spans"
            " carry every expected OTLv2 attribute."
        )

        print("\n" + "=" * 72)
        print("Spans exported to Weave GenAI OTL v2 endpoint")
        print("=" * 72)
        print(f"  Endpoint:    {otel_traces_endpoint()}")
        print(f"  Project:     {entity_name}/{project_name}")
        print(f"  Project URL: {project_weave_root_url(entity_name, project_name)}")
        print(f"  Agents URL:  {project_weave_root_url(entity_name, project_name)}/agents")
        print("  Custom tools logged:")
        print(f"    - get_weather       result={weather_result}")
        print(f"    - convert_currency  result={currency_result}")
        # All five spans (invoke_agent, 2 × call_llm, 2 × execute_tool)
        # share a single trace_id so Weave's chat view renders them as one
        # turn under the trip_planner agent.
        print(f"  Single trace_id (covers all 5 spans): {trace_id_hex}")
        print(
            "  Conversation URL: "
            f"{project_weave_root_url(entity_name, project_name)}/agents?conversation_id=conv-custom-tool-001"
        )
    finally:
        patcher.undo_patch()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
