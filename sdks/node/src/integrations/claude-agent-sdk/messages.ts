/**
 * camelCase→snake_case usage mapping for the Claude Agent SDK integration.
 *
 * The SDK reports per-model usage (`result.modelUsage`) in camelCase
 * ({@link ModelUsage}) and the aggregate (`result.usage`) in snake_case
 * ({@link NonNullableUsage}); Weave's usage/cost rollup keys on snake_case. This
 * normalizes either shape to the snake_case keys Weave emits.
 */
import type {
  ModelUsage,
  NonNullableUsage,
} from '@anthropic-ai/claude-agent-sdk';

/** Weave's snake_case usage shape — the only keys {@link toWeaveUsage} emits. */
type WeaveUsage = {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  cache_creation_input_tokens: number;
};

/**
 * Translate a Claude Agent SDK usage object — the per-model camelCase
 * {@link ModelUsage} or the snake_case aggregate {@link NonNullableUsage} — into
 * Weave's snake_case usage shape.
 */
export function toWeaveUsage(usage: ModelUsage | NonNullableUsage): WeaveUsage {
  if ('inputTokens' in usage) {
    return {
      input_tokens: usage.inputTokens,
      output_tokens: usage.outputTokens,
      cache_read_input_tokens: usage.cacheReadInputTokens,
      cache_creation_input_tokens: usage.cacheCreationInputTokens,
    };
  }
  return {
    input_tokens: usage.input_tokens,
    output_tokens: usage.output_tokens,
    cache_read_input_tokens: usage.cache_read_input_tokens,
    cache_creation_input_tokens: usage.cache_creation_input_tokens,
  };
}
