import {randomUUID} from 'crypto';

import {SpanKind, SpanStatusCode} from '@opentelemetry/api';
import type {
  ModelUsage,
  SDKAssistantMessage,
  SDKResultMessage,
  SDKUserMessage,
} from '@anthropic-ai/claude-agent-sdk';

import {
  ATTR_ERROR_TYPE,
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_PROVIDER_NAME,
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_RESPONSE_FINISH_REASONS,
  ATTR_GEN_AI_RESPONSE_MODEL,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_TOTAL_TOKENS,
} from '../../../genai/semconv';
import {ClaudeAgentOtelTracer} from '../../../integrations/claude-agent-sdk/otelTracer';
import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from '../../genai/common';

const INVOKE = 'invoke_agent claude_agent_sdk';

// ---------------------------------------------------------------------------
// Typed SDK-message fixtures.
//
// The tracer consumes `SDKMessage`/`SDKResultMessage`, so the fixtures are built
// as those real types (every shape derived from `@anthropic-ai/claude-agent-sdk`)
// rather than `as any` blobs — the compiler now catches a fixture that drifts
// from the SDK contract. The tracer only reads a handful of fields, so the
// builders fill the rest from defaults and expose the meaningful bits as args.
// ---------------------------------------------------------------------------

type AssistantContent = SDKAssistantMessage['message']['content'][number];

const thinkingBlock = (
  thinking: string
): Extract<AssistantContent, {type: 'thinking'}> => ({
  type: 'thinking',
  thinking,
  signature: '',
});

const textBlock = (
  text: string
): Extract<AssistantContent, {type: 'text'}> => ({
  type: 'text',
  text,
  citations: null,
});

const toolUseBlock = (
  id: string,
  name: string,
  input: unknown
): Extract<AssistantContent, {type: 'tool_use'}> => ({
  type: 'tool_use',
  id,
  name,
  input,
});

// The tracer reads `model`, `stop_reason`, and `content` off an assistant
// message; the rest of the BetaMessage envelope is filled with neutral defaults.
const DEFAULT_BETA_USAGE: SDKAssistantMessage['message']['usage'] = {
  input_tokens: 0,
  output_tokens: 0,
  cache_creation_input_tokens: null,
  cache_read_input_tokens: null,
  cache_creation: null,
  output_tokens_details: null,
  server_tool_use: null,
  inference_geo: null,
  iterations: null,
  service_tier: null,
  speed: null,
};

function assistantMessage(opts: {
  sessionId: string;
  model: string;
  content: AssistantContent[];
  stopReason?: SDKAssistantMessage['message']['stop_reason'];
}): SDKAssistantMessage {
  return {
    type: 'assistant',
    session_id: opts.sessionId,
    parent_tool_use_id: null,
    uuid: randomUUID(),
    message: {
      id: 'msg-1',
      type: 'message',
      role: 'assistant',
      model: opts.model,
      content: opts.content,
      stop_reason: opts.stopReason ?? null,
      stop_sequence: null,
      stop_details: null,
      container: null,
      context_management: null,
      diagnostics: null,
      usage: DEFAULT_BETA_USAGE,
    },
  };
}

type ToolResultBlock = Extract<
  Exclude<SDKUserMessage['message']['content'], string>[number],
  {type: 'tool_result'}
>;

function userToolResult(opts: {
  sessionId: string;
  toolUseId: string;
  content: string;
  isError?: boolean;
}): SDKUserMessage {
  const block: ToolResultBlock = {
    type: 'tool_result',
    tool_use_id: opts.toolUseId,
    content: opts.content,
    is_error: opts.isError ?? false,
  };
  return {
    type: 'user',
    session_id: opts.sessionId,
    parent_tool_use_id: null,
    message: {role: 'user', content: [block]},
  };
}

// Build one model's usage; the tracer only reads the four token fields, so the
// rest (cost, context window, …) default to 0.
const modelUsage = (u: Partial<ModelUsage>): ModelUsage => ({
  inputTokens: 0,
  outputTokens: 0,
  cacheReadInputTokens: 0,
  cacheCreationInputTokens: 0,
  webSearchRequests: 0,
  costUSD: 0,
  contextWindow: 0,
  maxOutputTokens: 0,
  ...u,
});

// The tracer sources tokens from `modelUsage`, never `result.usage`, but the
// SDK result type still requires a (non-null) aggregate usage object.
const DEFAULT_RESULT_USAGE: SDKResultMessage['usage'] = {
  input_tokens: 0,
  output_tokens: 0,
  cache_creation_input_tokens: 0,
  cache_read_input_tokens: 0,
  cache_creation: {ephemeral_1h_input_tokens: 0, ephemeral_5m_input_tokens: 0},
  output_tokens_details: {thinking_tokens: 0},
  server_tool_use: {web_fetch_requests: 0, web_search_requests: 0},
  inference_geo: '',
  iterations: [],
  service_tier: 'standard',
  speed: 'standard',
};

function resultSuccess(opts: {
  result?: string;
  totalCostUsd?: number;
  numTurns?: number;
  modelUsage?: Record<string, ModelUsage>;
  sessionId?: string;
}): SDKResultMessage {
  return {
    type: 'result',
    subtype: 'success',
    is_error: false,
    duration_ms: 0,
    duration_api_ms: 0,
    num_turns: opts.numTurns ?? 0,
    result: opts.result ?? '',
    stop_reason: null,
    total_cost_usd: opts.totalCostUsd ?? 0,
    usage: DEFAULT_RESULT_USAGE,
    modelUsage: opts.modelUsage ?? {},
    permission_denials: [],
    uuid: randomUUID(),
    session_id: opts.sessionId ?? 'sess',
  };
}

function resultError(opts: {
  subtype?: Exclude<SDKResultMessage['subtype'], 'success'>;
  errors?: string[];
  sessionId?: string;
}): SDKResultMessage {
  return {
    type: 'result',
    subtype: opts.subtype ?? 'error_max_turns',
    is_error: true,
    duration_ms: 0,
    duration_api_ms: 0,
    num_turns: 0,
    stop_reason: null,
    total_cost_usd: 0,
    usage: DEFAULT_RESULT_USAGE,
    modelUsage: {},
    permission_denials: [],
    errors: opts.errors ?? [],
    uuid: randomUUID(),
    session_id: opts.sessionId ?? 'sess',
  };
}

describe('Claude Agent SDK — OTel tracer', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  test('emits invoke_agent + chat + execute_tool GenAI spans for one query', () => {
    const tracer = new ClaudeAgentOtelTracer({
      prompt: 'What is the weather in Tokyo?',
    });
    tracer.processMessage(
      assistantMessage({
        sessionId: 'sess-1',
        model: 'claude-x',
        stopReason: 'tool_use',
        content: [
          thinkingBlock('I should check the weather.'),
          textBlock('Let me check.'),
          toolUseBlock('t1', 'Bash', {command: 'ls'}),
        ],
      })
    );
    tracer.processMessage(
      userToolResult({
        sessionId: 'sess-1',
        toolUseId: 't1',
        content: 'Sunny',
        isError: false,
      })
    );
    tracer.finalize(
      resultSuccess({
        sessionId: 'sess-1',
        result: 'It is sunny.',
        totalCostUsd: 0.01,
        numTurns: 1,
        modelUsage: {
          'claude-x': modelUsage({
            inputTokens: 10,
            outputTokens: 5,
            cacheReadInputTokens: 3,
          }),
        },
      })
    );

    const spans = getExporter().getFinishedSpans();

    const invoke = findSpan(spans, INVOKE);
    expect(invoke.kind).toBe(SpanKind.INTERNAL);
    expect(invoke.attributes[ATTR_GEN_AI_OPERATION_NAME]).toBe('invoke_agent');
    expect(invoke.attributes[ATTR_GEN_AI_AGENT_NAME]).toBe('claude_agent_sdk');
    expect(invoke.attributes[ATTR_GEN_AI_PROVIDER_NAME]).toBe('anthropic');
    expect(invoke.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('sess-1');
    expect(invoke.parentSpanContext?.spanId).toBeUndefined();
    // The root carries no token usage of its own — per-model usage rides on
    // child `chat` spans (asserted below) so the trace server costs and rolls
    // it up per model. The SDK's authoritative total cost stays on the root.
    expect(invoke.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS]).toBeUndefined();
    expect(invoke.attributes['claude_agent_sdk.usage.cost_usd']).toBe(0.01);
    expect(invoke.attributes['claude_agent_sdk.num_turns']).toBe(1);
    expect(
      JSON.parse(invoke.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string)
    ).toEqual([{role: 'user', content: 'What is the weather in Tokyo?'}]);
    expect(
      JSON.parse(invoke.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string)
    ).toEqual([{role: 'assistant', content: 'It is sunny.'}]);

    // Two spans are named `chat claude-x`: the per-message content span and the
    // per-model usage span. Distinguish them by what each carries.
    const chatSpans = spans.filter(s => s.name === 'chat claude-x');
    const chat = chatSpans.find(
      s => s.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] != null
    )!;
    expect(chat.kind).toBe(SpanKind.CLIENT);
    expect(chat.attributes[ATTR_GEN_AI_OPERATION_NAME]).toBe('chat');
    expect(chat.attributes[ATTR_GEN_AI_REQUEST_MODEL]).toBe('claude-x');
    expect(chat.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('sess-1');
    // Child spans carry the agent name so per-agent usage rollups (which group
    // by gen_ai.agent.name) attribute their tokens to the agent.
    expect(chat.attributes[ATTR_GEN_AI_AGENT_NAME]).toBe('claude_agent_sdk');
    expect(chat.attributes[ATTR_GEN_AI_RESPONSE_FINISH_REASONS]).toEqual([
      'tool_use',
    ]);
    expect(chat.parentSpanContext?.spanId).toBe(invoke.spanContext().spanId);
    expect(
      JSON.parse(chat.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string)
    ).toEqual([
      {
        role: 'assistant',
        parts: [
          {type: 'reasoning', content: 'I should check the weather.'},
          {type: 'text', content: 'Let me check.'},
          {
            type: 'tool_call',
            toolCallId: 't1',
            toolName: 'Bash',
            arguments: '{"command":"ls"}',
          },
        ],
      },
    ]);

    // The per-model usage span carries `modelUsage['claude-x']`, keyed by model
    // (request + response) so the trace server costs and rolls it up per model.
    const usageChat = chatSpans.find(
      s => s.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS] != null
    )!;
    expect(usageChat.attributes[ATTR_GEN_AI_OPERATION_NAME]).toBe('chat');
    expect(usageChat.attributes[ATTR_GEN_AI_REQUEST_MODEL]).toBe('claude-x');
    expect(usageChat.attributes[ATTR_GEN_AI_RESPONSE_MODEL]).toBe('claude-x');
    // input_tokens is the FULL prompt: fresh (10) + cache_read (3) folded in.
    expect(usageChat.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS]).toBe(13);
    expect(usageChat.attributes[ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]).toBe(5);
    expect(
      usageChat.attributes[ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS]
    ).toBe(3);
    // total_tokens = inclusive input (13) + output (5).
    expect(usageChat.attributes[ATTR_GEN_AI_USAGE_TOTAL_TOKENS]).toBe(18);
    expect(usageChat.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('sess-1');
    expect(usageChat.attributes[ATTR_GEN_AI_AGENT_NAME]).toBe(
      'claude_agent_sdk'
    );
    expect(usageChat.parentSpanContext?.spanId).toBe(invoke.spanContext().spanId);

    const tool = findSpan(spans, 'execute_tool Bash');
    expect(tool.kind).toBe(SpanKind.INTERNAL);
    expect(tool.attributes[ATTR_GEN_AI_TOOL_NAME]).toBe('Bash');
    expect(tool.attributes[ATTR_GEN_AI_TOOL_CALL_ID]).toBe('t1');
    expect(tool.attributes[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS]).toBe(
      '{"command":"ls"}'
    );
    expect(tool.attributes[ATTR_GEN_AI_TOOL_CALL_RESULT]).toBe('Sunny');
    expect(tool.attributes[ATTR_GEN_AI_AGENT_NAME]).toBe('claude_agent_sdk');
    expect(tool.parentSpanContext?.spanId).toBe(invoke.spanContext().spanId);

    // The whole tree shares one trace.
    const traceId = invoke.spanContext().traceId;
    expect(chat.spanContext().traceId).toBe(traceId);
    expect(tool.spanContext().traceId).toBe(traceId);
  });

  test('emits one usage chat span per model, preserving the per-model split', () => {
    const tracer = new ClaudeAgentOtelTracer({prompt: 'p'});
    tracer.processMessage(
      assistantMessage({
        sessionId: 'sess-2',
        model: 'claude-opus',
        content: [textBlock('hi')],
      })
    );
    tracer.finalize(
      resultSuccess({
        totalCostUsd: 0.05,
        // Multi-model session: a fast model handled an internal step and never
        // surfaced an assistant message of its own.
        modelUsage: {
          'claude-opus': modelUsage({inputTokens: 100, outputTokens: 40}),
          'claude-haiku': modelUsage({
            inputTokens: 20,
            outputTokens: 8,
            cacheReadInputTokens: 5,
            cacheCreationInputTokens: 3,
          }),
        },
      })
    );

    const spans = getExporter().getFinishedSpans();
    const invoke = findSpan(spans, INVOKE);
    // The root never carries token usage; the server rolls it up from children.
    expect(invoke.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS]).toBeUndefined();
    expect(invoke.attributes[ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]).toBeUndefined();
    expect(invoke.attributes['claude_agent_sdk.usage.cost_usd']).toBe(0.05);

    // One usage span per model, each keyed by its own model — the split is
    // preserved (not summed), so the server prices each model at its own rate.
    const opus = spans.find(
      s =>
        s.attributes[ATTR_GEN_AI_RESPONSE_MODEL] === 'claude-opus' &&
        s.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS] != null
    )!;
    expect(opus.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS]).toBe(100);
    expect(opus.attributes[ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]).toBe(40);
    expect(opus.attributes[ATTR_GEN_AI_USAGE_TOTAL_TOKENS]).toBe(140);
    expect(opus.parentSpanContext?.spanId).toBe(invoke.spanContext().spanId);

    // The internal fast model has no content chat span, only a usage span —
    // sourcing from `modelUsage` is what makes its tokens visible at all.
    const haiku = spans.find(
      s => s.attributes[ATTR_GEN_AI_RESPONSE_MODEL] === 'claude-haiku'
    )!;
    // input_tokens is the FULL prompt: Anthropic's disjoint fresh (20) +
    // cache_read (5) + cache_creation (3) folded in, so it's comparable to
    // OpenAI's already-inclusive input_tokens and the server's cost formula
    // `(input - cache_read - cache_creation) * price` recovers the fresh 20.
    expect(haiku.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS]).toBe(28);
    expect(haiku.attributes[ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]).toBe(8);
    expect(haiku.attributes[ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS]).toBe(5);
    expect(
      haiku.attributes[ATTR_GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS]
    ).toBe(3);
    // total_tokens = inclusive input (28) + output (8).
    expect(haiku.attributes[ATTR_GEN_AI_USAGE_TOTAL_TOKENS]).toBe(36);
    expect(haiku.parentSpanContext?.spanId).toBe(invoke.spanContext().spanId);
  });

  test('a tool_result flagged is_error marks the execute_tool span as error', () => {
    const tracer = new ClaudeAgentOtelTracer({prompt: 'p'});
    tracer.processMessage(
      assistantMessage({
        sessionId: 's',
        model: 'm',
        content: [toolUseBlock('t9', 'Bash', {command: 'boom'})],
      })
    );
    tracer.processMessage(
      userToolResult({
        sessionId: 's',
        toolUseId: 't9',
        content: 'command not found',
        isError: true,
      })
    );
    tracer.finalize(resultSuccess({}));

    const tool = findSpan(
      getExporter().getFinishedSpans(),
      'execute_tool Bash'
    );
    expect(tool.status.code).toBe(SpanStatusCode.ERROR);
    expect(tool.attributes[ATTR_ERROR_TYPE]).toBe('tool_error');
    expect(tool.attributes[ATTR_GEN_AI_TOOL_CALL_RESULT]).toBe(
      'command not found'
    );
  });

  test('a stream error fails the root and sweeps open tool spans as aborted', () => {
    const tracer = new ClaudeAgentOtelTracer({prompt: 'p'});
    tracer.processMessage(
      assistantMessage({
        sessionId: 's',
        model: 'm',
        content: [toolUseBlock('tX', 'Bash', {})],
      })
    );
    tracer.finalize(undefined, new Error('subprocess crashed'));

    const spans = getExporter().getFinishedSpans();
    const invoke = findSpan(spans, INVOKE);
    expect(invoke.status.code).toBe(SpanStatusCode.ERROR);
    expect(invoke.status.message).toContain('subprocess crashed');
    expect(invoke.attributes[ATTR_ERROR_TYPE]).toBe('agent_error');

    const tool = findSpan(spans, 'execute_tool Bash');
    expect(tool.status.code).toBe(SpanStatusCode.ERROR);
    expect(tool.attributes[ATTR_ERROR_TYPE]).toBe('aborted');
  });

  test('a non-success result subtype fails the root span', () => {
    const tracer = new ClaudeAgentOtelTracer({prompt: 'p'});
    tracer.processMessage(
      assistantMessage({
        sessionId: 's',
        model: 'm',
        content: [textBlock('trying')],
      })
    );
    tracer.finalize(
      resultError({subtype: 'error_max_turns', errors: ['boom']})
    );

    const invoke = findSpan(getExporter().getFinishedSpans(), INVOKE);
    expect(invoke.status.code).toBe(SpanStatusCode.ERROR);
    expect(invoke.status.message).toContain('boom');
  });

  test('late-binds the conversation id from the result when no earlier message carried one', () => {
    // A result-only stream (no system/assistant turn) still groups into its
    // session: finalize reads session_id off the result.
    const tracer = new ClaudeAgentOtelTracer({prompt: 'p'});
    tracer.finalize(resultSuccess({sessionId: 'sess-late', result: 'ok'}));

    const invoke = findSpan(getExporter().getFinishedSpans(), INVOKE);
    expect(invoke.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('sess-late');
  });
});
