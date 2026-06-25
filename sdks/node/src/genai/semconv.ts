/**
 * Constants for OpenTelemetry emitters in the Weave SDK that produce spans
 * conforming to the GenAI semantic conventions:
 * https://opentelemetry.io/docs/specs/semconv/gen-ai/
 *
 * Per the OpenTelemetry JS guidance for unstable (incubating) semconv, we copy
 * the relevant definitions here verbatim — same identifier names, same string
 * values — instead of importing from `@opentelemetry/semantic-conventions/
 * incubating`. The incubating entry point can break across minor versions, so
 * keeping a local copy lets us control when we absorb upstream changes.
 *
 * Refresh procedure: diff this file against the corresponding lines of
 * `@opentelemetry/semantic-conventions` `experimental_attributes.ts` /
 * `experimental_events.ts` (and `stable_attributes.ts` for `ATTR_ERROR_TYPE`).
 * Tracked upstream version: 1.41.1.
 *
 * See https://github.com/open-telemetry/opentelemetry-js/tree/main/semantic-conventions#unstable-semconv
 */

// ---------------------------------------------------------------------------
// Upstream attribute keys (verbatim copies)
// ---------------------------------------------------------------------------

export const ATTR_GEN_AI_AGENT_DESCRIPTION = 'gen_ai.agent.description';
export const ATTR_GEN_AI_AGENT_ID = 'gen_ai.agent.id';
export const ATTR_GEN_AI_AGENT_NAME = 'gen_ai.agent.name';
export const ATTR_GEN_AI_CONVERSATION_ID = 'gen_ai.conversation.id';
export const ATTR_GEN_AI_INPUT_MESSAGES = 'gen_ai.input.messages';
export const ATTR_GEN_AI_OPERATION_NAME = 'gen_ai.operation.name';
export const ATTR_GEN_AI_OUTPUT_MESSAGES = 'gen_ai.output.messages';
export const ATTR_GEN_AI_OUTPUT_TYPE = 'gen_ai.output.type';
export const ATTR_GEN_AI_PROVIDER_NAME = 'gen_ai.provider.name';
export const ATTR_GEN_AI_REQUEST_CHOICE_COUNT = 'gen_ai.request.choice.count';
export const ATTR_GEN_AI_REQUEST_FREQUENCY_PENALTY =
  'gen_ai.request.frequency_penalty';
export const ATTR_GEN_AI_REQUEST_MAX_TOKENS = 'gen_ai.request.max_tokens';
export const ATTR_GEN_AI_REQUEST_MODEL = 'gen_ai.request.model';
export const ATTR_GEN_AI_REQUEST_PRESENCE_PENALTY =
  'gen_ai.request.presence_penalty';
export const ATTR_GEN_AI_REQUEST_SEED = 'gen_ai.request.seed';
export const ATTR_GEN_AI_REQUEST_STOP_SEQUENCES =
  'gen_ai.request.stop_sequences';
export const ATTR_GEN_AI_REQUEST_TEMPERATURE = 'gen_ai.request.temperature';
export const ATTR_GEN_AI_REQUEST_TOP_P = 'gen_ai.request.top_p';
export const ATTR_GEN_AI_RESPONSE_FINISH_REASONS =
  'gen_ai.response.finish_reasons';
export const ATTR_GEN_AI_RESPONSE_ID = 'gen_ai.response.id';
export const ATTR_GEN_AI_RESPONSE_MODEL = 'gen_ai.response.model';
export const ATTR_GEN_AI_SYSTEM_INSTRUCTIONS = 'gen_ai.system_instructions';
export const ATTR_GEN_AI_TOOL_CALL_ARGUMENTS = 'gen_ai.tool.call.arguments';
export const ATTR_GEN_AI_TOOL_CALL_ID = 'gen_ai.tool.call.id';
export const ATTR_GEN_AI_TOOL_CALL_RESULT = 'gen_ai.tool.call.result';
export const ATTR_GEN_AI_TOOL_NAME = 'gen_ai.tool.name';
export const ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS =
  'gen_ai.usage.cache_creation.input_tokens';
export const ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS =
  'gen_ai.usage.cache_read.input_tokens';
export const ATTR_GEN_AI_USAGE_INPUT_TOKENS = 'gen_ai.usage.input_tokens';
export const ATTR_GEN_AI_USAGE_OUTPUT_TOKENS = 'gen_ai.usage.output_tokens';
export const ATTR_GEN_AI_USAGE_REASONING_OUTPUT_TOKENS =
  'gen_ai.usage.reasoning.output_tokens';

// ---------------------------------------------------------------------------
// Upstream event names (verbatim copies)
// ---------------------------------------------------------------------------

export const EVENT_GEN_AI_ASSISTANT_MESSAGE = 'gen_ai.assistant.message';
export const EVENT_GEN_AI_SYSTEM_MESSAGE = 'gen_ai.system.message';
export const EVENT_GEN_AI_TOOL_MESSAGE = 'gen_ai.tool.message';
export const EVENT_GEN_AI_USER_MESSAGE = 'gen_ai.user.message';

// ---------------------------------------------------------------------------
// Upstream stable attribute keys
// ---------------------------------------------------------------------------

export const ATTR_ERROR_TYPE = 'error.type';

// ---------------------------------------------------------------------------
// Weave extensions — NOT in upstream semconv
// ---------------------------------------------------------------------------
// These attribute keys are Weave-specific and have no counterpart in
// `@opentelemetry/semantic-conventions`. Keep them here so the rest of the
// file stays a clean copy of upstream and the diff against upstream is short.

/** Total tokens for an LLM call. Upstream tracks only input / output /
 *  reasoning separately. */
export const ATTR_GEN_AI_USAGE_TOTAL_TOKENS = 'gen_ai.usage.total_tokens';

/** Attribute key carrying serialized content inside a gen_ai.* span event
 *  (e.g. on `gen_ai.system.message`). */
export const ATTR_GEN_AI_EVENT_CONTENT = 'gen_ai.event.content';

// ---------------------------------------------------------------------------
// Emitter identity (Weave-specific, not a semconv constant)
// ---------------------------------------------------------------------------

/** Instrumentation-library name passed to `getWeaveTracer` by every emitter
 *  in the GenAI session SDK. */
export const WEAVE_GENAI_TRACER_NAME = 'weave-genai';
