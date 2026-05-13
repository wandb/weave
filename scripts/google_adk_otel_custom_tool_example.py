"""Example: log a custom ADK tool to the Weave GenAI OTLv2 endpoint.

This is the ADK-native companion to ``google_adk_otel_example.py``. The
other example pokes ADK's tracing helpers (``trace_tool_call`` etc.)
directly, which is useful for testing the integration's attribute set but
isn't how ADK actually runs. This script defines a custom Python tool,
wraps it with ADK's ``FunctionTool``, hands the agent to ADK's
``InMemoryRunner``, and lets the runner drive the entire agent loop. ADK
opens every OTel span itself; ``weave.integrations.patch_google_adk()``
enriches them on the way out so the Weave OTLv2 columns get populated.

A ``StubLlm`` (subclass of ``BaseLlm``) returns scripted responses so the
example needs no Gemini / Vertex credentials. In production you'd swap
that for a real model — the rest of the flow stays identical, because
the spans we care about are emitted by ADK regardless of which LLM
implementation the agent uses.

Flow:

  1. ``weave.init("megatruong/adk-test")`` installs the global OTel
     ``TracerProvider`` with a ``BatchSpanProcessor`` pointing at
     ``/agents/otel/v1/traces``.
  2. Define ``get_weather`` and ``convert_currency`` Python functions,
     wrap each with ``FunctionTool``, and bind them to an ``LlmAgent``.
  3. ``StubLlm`` walks through the scripted multi-turn response sequence
     (call ``get_weather`` → call ``convert_currency`` → final answer)
     so ADK's runner actually invokes the tools.
  4. ``InMemoryRunner.run_async`` drives the loop. ADK emits the
     ``invoke_agent``, ``call_llm`` and ``execute_tool`` spans natively;
     the Weave patch fills in the full OTLv2 attribute set.

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
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
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
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_FINISH_REASONS,
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

APP_NAME = "adk-otel-demo"
USER_ID = "megatruong"
SESSION_ID = f"conv-custom-tool-{uuid.uuid4().hex[:8]}"

# These are the OTLv2 attributes we expect on each span ADK emits. They
# combine ADK's own ``gen_ai.*`` keys with the ones added by
# ``weave.integrations.patch_google_adk``.
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

# ADK sets ``request.model`` only on the ``generate_content`` span; the
# ``invoke_agent`` span carries the agent-level metadata, not the model.
EXPECTED_INVOKE_AGENT_KEYS = {
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_AGENT_NAME,
    GEN_AI_AGENT_DESCRIPTION,
    GEN_AI_AGENT_ID,
    GEN_AI_CONVERSATION_ID,
}

# ADK's modern runner emits ``generate_content`` LLM spans (via
# ``use_inference_span``), not the legacy ``chat`` operation. The patch
# enriches both code paths; the script asserts the modern shape.
EXPECTED_CALL_LLM_KEYS = {
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_AGENT_NAME,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_INPUT_MESSAGES,
    GEN_AI_OUTPUT_MESSAGES,
    GEN_AI_SYSTEM_INSTRUCTIONS,
    GEN_AI_TOOL_DEFINITIONS,
    GEN_AI_RESPONSE_FINISH_REASONS,
    GEN_AI_OUTPUT_TYPE,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
}


# --------------------------------------------------------------------------
# Custom tools — real Python functions the agent can call. ADK reads the
# docstring and type hints to build the function declaration it shows the
# model.
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


def convert_currency(
    amount: float, from_currency: str, to_currency: str
) -> dict[str, Any]:
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
# Stub LLM — scripts the multi-turn flow so we don't need real model
# credentials. ``InMemoryRunner`` invokes it exactly the same way it would
# invoke a Gemini model, so the OTel spans ADK emits are identical to a
# real run.
# --------------------------------------------------------------------------


class StubLlm(BaseLlm):
    """Walk through a scripted function-call / function-response sequence."""

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["stub-llm"]

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        # Decide which scripted turn we're on by inspecting the latest
        # function-response part in the request. ADK appends a turn after
        # each tool call, so the request shape changes deterministically.
        tool_names_seen = [
            part.function_response.name
            for content in llm_request.contents
            for part in (content.parts or [])
            if getattr(part, "function_response", None) is not None
        ]

        if not tool_names_seen:
            # Turn 1: ask the runner to call ``get_weather``.
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                id="call-weather-1",
                                name="get_weather",
                                args={"city": "Paris", "units": "metric"},
                            )
                        )
                    ],
                ),
                finish_reason=types.FinishReason.STOP,
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=120,
                    candidates_token_count=18,
                ),
                model_version="stub-llm-v1",
                interaction_id="resp-stub-001",
            )
            return

        if tool_names_seen == ["get_weather"]:
            # Turn 2: now that we have weather, request ``convert_currency``.
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            function_call=types.FunctionCall(
                                id="call-currency-1",
                                name="convert_currency",
                                args={
                                    "amount": 1000,
                                    "from_currency": "USD",
                                    "to_currency": "JPY",
                                },
                            )
                        )
                    ],
                ),
                finish_reason=types.FinishReason.STOP,
                usage_metadata=types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=160,
                    candidates_token_count=22,
                ),
                model_version="stub-llm-v1",
                interaction_id="resp-stub-002",
            )
            return

        # Turn 3: both tools returned; synthesize the final answer.
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=(
                            "Paris is 18C and cloudy. 1000 USD converts to "
                            "150,200 JPY at today's rate."
                        )
                    )
                ],
            ),
            finish_reason=types.FinishReason.STOP,
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=210,
                candidates_token_count=42,
            ),
            model_version="stub-llm-v1",
            interaction_id="resp-stub-003",
        )


# --------------------------------------------------------------------------
# Reporting helpers
# --------------------------------------------------------------------------


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
    print(f"\n## {title}  (span_id={span.context.span_id:016x})")
    for line in _attr_lines(span):
        print(line)
    missing = sorted(required - set((span.attributes or {}).keys()))
    if missing:
        print(f"  MISSING required keys: {missing}")
    return missing


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


async def _run() -> None:
    project = os.environ.get("WEAVE_ADK_EXAMPLE_PROJECT", "megatruong/adk-test")

    # 1. ``weave.init`` installs the global OTel TracerProvider pointing at
    # the GenAI OTLP endpoint. Tee an in-memory exporter so we can verify
    # wire contents locally too.
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
        # 2. Construct a real ADK agent with the custom tools.
        agent = LlmAgent(
            name="trip_planner",
            description=(
                "Plans multi-city itineraries with live weather + currency lookup."
            ),
            model=StubLlm(model="stub-llm"),
            tools=[FunctionTool(get_weather), FunctionTool(convert_currency)],
        )

        # 3. Hand the agent to ADK's runner. From here on, ADK opens every
        # OTel span itself — invoke_agent at the top, then call_llm /
        # execute_tool children as the model issues function calls.
        runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
        await runner.session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
        )

        new_message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        "What's the weather in Paris, and how much is 1000 USD "
                        "in JPY?"
                    )
                )
            ],
        )

        final_text = ""
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=new_message,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text = part.text

        provider.force_flush()

        # 4. Inspect the spans ADK emitted. Each span name maps to the OTel
        # operation: ``invoke_agent``, ``call_llm`` (Gemini-style "execute_tool
        # ${tool_name}" naming for tool spans varies by ADK version, so we
        # match by operation_name instead).
        captured = list(in_memory.get_finished_spans())
        by_op: dict[str, list[Any]] = {}
        for span in captured:
            op = (span.attributes or {}).get(GEN_AI_OPERATION_NAME, "")
            by_op.setdefault(str(op), []).append(span)

        # ADK emits one invoke_agent span per turn and one execute_tool span
        # per tool call. The number of call_llm spans depends on the ADK
        # version's generate-content wrapper.
        execute_tool_spans = by_op.get("execute_tool", [])
        invoke_agent_spans = by_op.get("invoke_agent", [])
        call_llm_spans = by_op.get("chat", []) + by_op.get("generate_content", [])

        all_missing: list[str] = []

        if not invoke_agent_spans:
            print("\n## invoke_agent — NO SPAN EMITTED")
            all_missing.append("invoke_agent")
        else:
            for span in invoke_agent_spans:
                miss = _print_section(
                    "invoke_agent (trip_planner)", span, EXPECTED_INVOKE_AGENT_KEYS
                )
                if miss:
                    all_missing.append(f"invoke_agent missing {miss}")

        if not execute_tool_spans:
            print("\n## execute_tool — NO SPAN EMITTED")
            all_missing.append("execute_tool")
        else:
            for span in execute_tool_spans:
                tool_name = (span.attributes or {}).get(GEN_AI_TOOL_NAME, "")
                miss = _print_section(
                    f"execute_tool {tool_name} (custom tool)",
                    span,
                    EXPECTED_EXECUTE_TOOL_KEYS,
                )
                if miss:
                    all_missing.append(f"execute_tool[{tool_name}] missing {miss}")

        if not call_llm_spans:
            print("\n## call_llm — NO SPAN EMITTED")
            all_missing.append("call_llm")
        else:
            for span in call_llm_spans:
                miss = _print_section(
                    f"call_llm ({span.name})", span, EXPECTED_CALL_LLM_KEYS
                )
                if miss:
                    all_missing.append(f"call_llm[{span.name}] missing {miss}")

        if all_missing:
            print("\nFAIL: incomplete OTLv2 coverage:")
            for entry in all_missing:
                print(f"  - {entry}")
            raise SystemExit(1)

        print("\nOK: ADK emitted every expected span and the Weave patch enriched it.")

        # 5. Print where the trace landed on Weave.
        trace_ids = sorted({f"{s.context.trace_id:032x}" for s in captured})
        print("\n" + "=" * 72)
        print("Spans exported to Weave GenAI OTL v2 endpoint")
        print("=" * 72)
        print(f"  Endpoint:    {otel_traces_endpoint()}")
        print(f"  Project:     {entity_name}/{project_name}")
        print(f"  Project URL: {project_weave_root_url(entity_name, project_name)}")
        print(f"  Agents URL:  {project_weave_root_url(entity_name, project_name)}/agents")
        print(f"  Conversation: {SESSION_ID}")
        print(f"  Final answer: {final_text!r}")
        print(f"  Trace IDs (hex): {trace_ids}")
    finally:
        patcher.undo_patch()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
