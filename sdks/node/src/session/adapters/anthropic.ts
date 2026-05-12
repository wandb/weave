/**
 * Adapters from Anthropic's wire format to the Weave Session SDK types.
 *
 * Use these when manually instrumenting calls to `client.messages.create`
 * (autopatched Anthropic integrations handle conversion automatically).
 *
 * Port of `weave/session/adapters/anthropic.py`.
 */

import {Usage} from '../types';

/**
 * Extract usage from an Anthropic Messages API `Message`.
 *
 * Anthropic types the cache fields as nullable; `null`/`undefined` is
 * treated as zero.
 */
export function usageFromAnthropic(message: Record<string, unknown>): Usage {
  const usage = (message.usage as Record<string, unknown> | undefined) ?? {};
  return new Usage({
    inputTokens: (usage.input_tokens as number | undefined) ?? 0,
    outputTokens: (usage.output_tokens as number | undefined) ?? 0,
    cacheCreationInputTokens:
      (usage.cache_creation_input_tokens as number | undefined) ?? 0,
    cacheReadInputTokens:
      (usage.cache_read_input_tokens as number | undefined) ?? 0,
  });
}
