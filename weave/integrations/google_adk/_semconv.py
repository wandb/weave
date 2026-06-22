"""Vendored GenAI semantic-convention keys for the Google ADK integration.

These mirror ``opentelemetry.semconv._incubating.attributes.gen_ai_attributes``.
We vendor them as plain string literals instead of importing the package:

1. **Dependency compatibility.** The named constants below only ship in
   ``opentelemetry-semantic-conventions>=0.63b0`` (``opentelemetry-sdk>=1.42``).
   ``google-adk`` pins ``opentelemetry-sdk<=1.41.1``, so importing them from the
   package makes ``weave`` + ``google-adk`` an unsatisfiable install. Vendoring
   the strings removes that version coupling — the integration runs against
   whatever semconv ADK pulls in.
2. **Lock-step with the server.** The trace server already vendors these exact
   strings as its extraction keys (``weave/trace_server/agents/semconv.py``).
   The client emits the attribute; the server looks it up by literal, so the two
   must agree. ``tests/integrations/google_adk/test_google_adk.py`` asserts the
   match to catch drift.

The source module is private (``_incubating``) and the values are stable spec
attribute names, so hardcoding them is the same trade-off ``agents/semconv.py``
and ``weave/evaluation/otel_eval_linker.py`` already make.
"""

from __future__ import annotations

# --- Attribute keys (named to match the upstream constants) -----------------
GEN_AI_AGENT_ID = "gen_ai.agent.id"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_TOP_P = "gen_ai.request.top_p"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_REQUEST_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"
GEN_AI_REQUEST_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"
GEN_AI_REQUEST_SEED = "gen_ai.request.seed"
GEN_AI_REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"
GEN_AI_REQUEST_CHOICE_COUNT = "gen_ai.request.choice.count"
GEN_AI_RESPONSE_ID = "gen_ai.response.id"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES = "gen_ai.output.messages"
GEN_AI_OUTPUT_TYPE = "gen_ai.output.type"
GEN_AI_SYSTEM_INSTRUCTIONS = "gen_ai.system_instructions"
GEN_AI_TOOL_DEFINITIONS = "gen_ai.tool.definitions"
GEN_AI_TOOL_CALL_ARGUMENTS = "gen_ai.tool.call.arguments"
GEN_AI_TOOL_CALL_RESULT = "gen_ai.tool.call.result"
GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS = "gen_ai.usage.cache_read.input_tokens"
GEN_AI_USAGE_REASONING_OUTPUT_TOKENS = "gen_ai.usage.reasoning.output_tokens"

# --- Enum member values (were GenAi*Values.<MEMBER>.value) ------------------
# gen_ai.operation.name value for an agent-invocation span.
OPERATION_INVOKE_AGENT = "invoke_agent"
# gen_ai.provider.name values. ADK's _guess_gemini_system_name picks between
# these based on GOOGLE_GENAI_USE_VERTEXAI; the strings are the upstream
# GenAiSystemValues members.
PROVIDER_VERTEX_AI = "vertex_ai"
PROVIDER_GEMINI = "gemini"
# gen_ai.output.type value for a text response.
OUTPUT_TYPE_TEXT = "text"
