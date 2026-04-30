/**
 * Shared constants for OpenTelemetry integrations that emit spans conforming
 * to the GenAI semantic conventions:
 * https://opentelemetry.io/docs/specs/semconv/gen-ai/
 */

// ---------------------------------------------------------------------------
// Attribute key constants
// ---------------------------------------------------------------------------

/** GenAI semantic convention attribute keys. */
export const GEN_AI_ATTR = {
  GEN_AI_PROVIDER_NAME: 'gen_ai.provider.name',
  GEN_AI_OPERATION_NAME: 'gen_ai.operation.name',
  GEN_AI_AGENT_NAME: 'gen_ai.agent.name',
  GEN_AI_REQUEST_MODEL: 'gen_ai.request.model',
  GEN_AI_RESPONSE_MODEL: 'gen_ai.response.model',
  GEN_AI_RESPONSE_FINISH_REASONS: 'gen_ai.response.finish_reasons',
  GEN_AI_CONVERSATION_ID: 'gen_ai.conversation.id',
  // Token usage
  GEN_AI_USAGE_INPUT_TOKENS: 'gen_ai.usage.input_tokens',
  GEN_AI_USAGE_OUTPUT_TOKENS: 'gen_ai.usage.output_tokens',
  GEN_AI_USAGE_TOTAL_TOKENS: 'gen_ai.usage.total_tokens',
  GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS: 'gen_ai.usage.cache_read.input_tokens',
  GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS:
    'gen_ai.usage.cache_creation.input_tokens',
  // Tool
  GEN_AI_TOOL_NAME: 'gen_ai.tool.name',
  GEN_AI_TOOL_CALL_ID: 'gen_ai.tool.call.id',
  GEN_AI_OUTPUT_TYPE: 'gen_ai.output.type',
} as const;

// ---------------------------------------------------------------------------
// Event name constants
// ---------------------------------------------------------------------------

/** GenAI semantic convention span event names. */
export const GEN_AI_EVENT = {
  SYSTEM_MESSAGE: 'gen_ai.system.message',
  USER_MESSAGE: 'gen_ai.user.message',
  ASSISTANT_MESSAGE: 'gen_ai.assistant.message',
  TOOL_MESSAGE: 'gen_ai.tool.message',
  CONTENT_ATTR: 'gen_ai.event.content',
} as const;

// ---------------------------------------------------------------------------
// General OTEL attribute keys
// ---------------------------------------------------------------------------

/** General OpenTelemetry attribute keys used alongside GenAI spans. */
export const OTEL_ATTR = {
  ERROR_TYPE: 'error.type',
} as const;
