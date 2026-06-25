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
  input_tokens?: number;
  output_tokens?: number;
  cache_read_input_tokens?: number;
  cache_creation_input_tokens?: number;
};

/**
 * Either Claude Agent SDK usage shape, with every field optional: the per-model
 * `result.modelUsage` values ({@link ModelUsage}, camelCase) or the aggregate
 * `result.usage` ({@link NonNullableUsage}, snake_case). An object only carries
 * one casing's keys, and the wire value can be partial, so all keys are optional.
 */
type SdkUsage = Partial<ModelUsage> & Partial<NonNullableUsage>;

/**
 * Translate a Claude Agent SDK usage object into Weave's snake_case usage shape.
 *
 * Weave's usage/cost rollup keys on snake_case, so the camelCase `modelUsage`
 * names are renamed and the snake_case aggregate names pass through (whichever
 * is present wins). Absent fields stay absent.
 */
export function toWeaveUsage(usage: SdkUsage): WeaveUsage {
  return {
    input_tokens: usage.inputTokens ?? usage.input_tokens,
    output_tokens: usage.outputTokens ?? usage.output_tokens,
    cache_read_input_tokens:
      usage.cacheReadInputTokens ?? usage.cache_read_input_tokens,
    cache_creation_input_tokens:
      usage.cacheCreationInputTokens ?? usage.cache_creation_input_tokens,
  };
}
