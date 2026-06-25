import type {
  Response,
  ResponseOutputItem,
} from 'openai/resources/responses/responses';

/**
 * Build an OpenAI Responses-API `Response` from the bits of data a mock
 * actually cares about. Fills in the long tail of required-but-irrelevant
 * fields (tool_choice, parallel_tool_calls, etc.) with safe defaults so
 * the mocks stay readable.
 */
export function openAIResponse(opts: {
  id: string;
  text?: string;
  reasoning?: string;
  toolCalls?: Array<{callId: string; name: string; args: object; id?: string}>;
  usage: {input: number; output: number; reasoning?: number; cached?: number};
  createdAt: Date;
}): Response {
  const output: ResponseOutputItem[] = [];

  if (opts.reasoning !== undefined) {
    output.push({
      type: 'reasoning',
      id: `${opts.id}-reasoning`,
      summary: [{type: 'summary_text', text: opts.reasoning}],
    });
  }

  if (opts.text !== undefined) {
    output.push({
      type: 'message',
      id: `${opts.id}-msg`,
      role: 'assistant',
      status: 'completed',
      content: [{type: 'output_text', text: opts.text, annotations: []}],
    });
  }

  for (const tc of opts.toolCalls ?? []) {
    output.push({
      type: 'function_call',
      id: tc.id ?? `${opts.id}-${tc.callId}`,
      call_id: tc.callId,
      name: tc.name,
      arguments: JSON.stringify(tc.args),
      status: 'completed',
    });
  }

  return {
    id: opts.id,
    object: 'response',
    created_at: Math.floor(opts.createdAt.getTime() / 1000),
    model: 'gpt-4o-mini',
    output,
    output_text: opts.text ?? '',
    error: null,
    incomplete_details: null,
    instructions: null,
    metadata: null,
    parallel_tool_calls: true,
    temperature: null,
    tool_choice: 'auto',
    tools: [],
    top_p: null,
    status: 'completed',
    usage: {
      input_tokens: opts.usage.input,
      output_tokens: opts.usage.output,
      total_tokens: opts.usage.input + opts.usage.output,
      input_tokens_details: {cached_tokens: opts.usage.cached ?? 0},
      output_tokens_details: {reasoning_tokens: opts.usage.reasoning ?? 0},
    },
  };
}
