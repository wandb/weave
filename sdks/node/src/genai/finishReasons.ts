import type {Message} from './types';

/** Values from the Agent Lens GenAI conventions (upstream OTel `FinishReason`). */
export const FINISH_REASON_STOP = 'stop';
export const FINISH_REASON_LENGTH = 'length';
export const FINISH_REASON_CONTENT_FILTER = 'content_filter';
export const FINISH_REASON_TOOL_CALL = 'tool_call';
export const FINISH_REASON_ERROR = 'error';

/** Provider-specific finish reasons (OpenAI, Anthropic, Gemini, pi), lower-cased. */
const FINISH_REASON_ALIASES: Record<string, string> = {
  stop: FINISH_REASON_STOP,
  end_turn: FINISH_REASON_STOP,
  stop_sequence: FINISH_REASON_STOP,
  length: FINISH_REASON_LENGTH,
  max_tokens: FINISH_REASON_LENGTH,
  max_output_tokens: FINISH_REASON_LENGTH,
  model_context_window_exceeded: FINISH_REASON_LENGTH,
  content_filter: FINISH_REASON_CONTENT_FILTER,
  refusal: FINISH_REASON_CONTENT_FILTER,
  safety: FINISH_REASON_CONTENT_FILTER,
  recitation: FINISH_REASON_CONTENT_FILTER,
  blocklist: FINISH_REASON_CONTENT_FILTER,
  prohibited_content: FINISH_REASON_CONTENT_FILTER,
  spii: FINISH_REASON_CONTENT_FILTER,
  image_safety: FINISH_REASON_CONTENT_FILTER,
  tool_call: FINISH_REASON_TOOL_CALL,
  tool_calls: FINISH_REASON_TOOL_CALL,
  function_call: FINISH_REASON_TOOL_CALL,
  tool_use: FINISH_REASON_TOOL_CALL,
  tooluse: FINISH_REASON_TOOL_CALL,
  error: FINISH_REASON_ERROR,
  failed: FINISH_REASON_ERROR,
  malformed_function_call: FINISH_REASON_ERROR,
  unexpected_tool_call: FINISH_REASON_ERROR,
};

/** Map a provider finish reason to the convention's value, or return it lower-cased. */
export function normalizeFinishReason(reason: string): string {
  const lowered = reason.trim().toLowerCase();
  return FINISH_REASON_ALIASES[lowered] ?? lowered;
}

/** Whether an output message requests at least one tool call. */
export function messageHasToolCall(message: Message): boolean {
  return (message.parts ?? []).some(part => part.type === 'tool_call');
}

/**
 * One finish reason per output message of a Responses API call.
 *
 * Each message ends with `tool_call` when it requests tools and `stop`
 * otherwise. An `incomplete` or `failed` response replaces the last message's
 * reason with `incomplete_details.reason` or `error`.
 */
export function finishReasonsFromResponses(
  status: string | null | undefined,
  incompleteReason: string | null | undefined,
  outputMessages: Message[]
): string[] {
  const reasons: string[] = outputMessages.map(message =>
    messageHasToolCall(message) ? FINISH_REASON_TOOL_CALL : FINISH_REASON_STOP
  );
  if (reasons.length === 0) {
    return reasons;
  }
  if (status === 'incomplete' && incompleteReason) {
    reasons[reasons.length - 1] = normalizeFinishReason(incompleteReason);
  } else if (status === 'failed') {
    reasons[reasons.length - 1] = FINISH_REASON_ERROR;
  }
  return reasons;
}
