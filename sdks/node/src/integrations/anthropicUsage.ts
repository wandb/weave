/**
 * Prompt-token accounting shared by the Anthropic-shaped integrations.
 *
 * Mirrors the Python `weave/integrations/claude_agent_sdk/usage.py`. Anthropic
 * reports fresh input tokens separately from cache-read and cache-creation
 * tokens, while Weave records those cache counts as subsets of the full prompt,
 * so its input token count must include all three values.
 */

/** The prompt-side subset of an Anthropic usage object. */
type PromptUsage = {
  input_tokens?: number | null;
  cache_read_input_tokens?: number | null;
  cache_creation_input_tokens?: number | null;
};

/** Weave's gross prompt count for an Anthropic usage payload. */
export function totalInputTokens(usage?: PromptUsage | null): number {
  const raw = usage ?? {};
  return (
    (raw.input_tokens ?? 0) +
    (raw.cache_read_input_tokens ?? 0) +
    (raw.cache_creation_input_tokens ?? 0)
  );
}
