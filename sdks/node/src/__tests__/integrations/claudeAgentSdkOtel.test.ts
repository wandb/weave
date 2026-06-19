import {SpanKind, SpanStatusCode} from '@opentelemetry/api';

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
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_TOTAL_TOKENS,
} from '../../genai/semconv';
import {ClaudeAgentOtelTracer} from '../../integrations/claude-agent-sdk/otelTracer';
import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from '../genai/common';

const INVOKE = 'invoke_agent claude_agent_sdk';

describe('Claude Agent SDK — OTel tracer', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  test('emits invoke_agent + chat + execute_tool GenAI spans for one query', () => {
    const tracer = new ClaudeAgentOtelTracer({
      prompt: 'What is the weather in Tokyo?',
    });
    tracer.processMessage({
      type: 'system',
      subtype: 'init',
      session_id: 'sess-1',
      model: 'claude-x',
    } as any);
    tracer.processMessage({
      type: 'assistant',
      session_id: 'sess-1',
      message: {
        model: 'claude-x',
        stop_reason: 'tool_use',
        content: [
          {type: 'thinking', thinking: 'I should check the weather.'},
          {type: 'text', text: 'Let me check.'},
          {type: 'tool_use', id: 't1', name: 'Bash', input: {command: 'ls'}},
        ],
      },
    } as any);
    tracer.processMessage({
      type: 'user',
      session_id: 'sess-1',
      message: {
        content: [
          {
            type: 'tool_result',
            tool_use_id: 't1',
            content: 'Sunny',
            is_error: false,
          },
        ],
      },
    } as any);
    tracer.finalize({
      type: 'result',
      subtype: 'success',
      is_error: false,
      result: 'It is sunny.',
      total_cost_usd: 0.01,
      num_turns: 1,
      modelUsage: {
        'claude-x': {inputTokens: 10, outputTokens: 5, cacheReadInputTokens: 3},
      },
    } as any);

    const spans = getExporter().getFinishedSpans();

    const invoke = findSpan(spans, INVOKE);
    expect(invoke.kind).toBe(SpanKind.INTERNAL);
    expect(invoke.attributes[ATTR_GEN_AI_OPERATION_NAME]).toBe('invoke_agent');
    expect(invoke.attributes[ATTR_GEN_AI_AGENT_NAME]).toBe('claude_agent_sdk');
    expect(invoke.attributes[ATTR_GEN_AI_PROVIDER_NAME]).toBe('anthropic');
    expect(invoke.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('sess-1');
    expect(invoke.parentSpanId).toBeUndefined();
    expect(invoke.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS]).toBe(10);
    expect(invoke.attributes[ATTR_GEN_AI_USAGE_OUTPUT_TOKENS]).toBe(5);
    expect(invoke.attributes[ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS]).toBe(
      3
    );
    expect(invoke.attributes[ATTR_GEN_AI_USAGE_TOTAL_TOKENS]).toBe(15);
    expect(invoke.attributes['claude_agent_sdk.usage.cost_usd']).toBe(0.01);
    expect(invoke.attributes['claude_agent_sdk.num_turns']).toBe(1);
    expect(
      JSON.parse(invoke.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string)
    ).toEqual([{role: 'user', content: 'What is the weather in Tokyo?'}]);
    expect(
      JSON.parse(invoke.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string)
    ).toEqual([{role: 'assistant', content: 'It is sunny.'}]);

    const chat = findSpan(spans, 'chat claude-x');
    expect(chat.kind).toBe(SpanKind.CLIENT);
    expect(chat.attributes[ATTR_GEN_AI_OPERATION_NAME]).toBe('chat');
    expect(chat.attributes[ATTR_GEN_AI_REQUEST_MODEL]).toBe('claude-x');
    expect(chat.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('sess-1');
    expect(chat.attributes[ATTR_GEN_AI_RESPONSE_FINISH_REASONS]).toEqual([
      'tool_use',
    ]);
    expect(chat.parentSpanId).toBe(invoke.spanContext().spanId);
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

    const tool = findSpan(spans, 'execute_tool Bash');
    expect(tool.kind).toBe(SpanKind.INTERNAL);
    expect(tool.attributes[ATTR_GEN_AI_TOOL_NAME]).toBe('Bash');
    expect(tool.attributes[ATTR_GEN_AI_TOOL_CALL_ID]).toBe('t1');
    expect(tool.attributes[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS]).toBe(
      '{"command":"ls"}'
    );
    expect(tool.attributes[ATTR_GEN_AI_TOOL_CALL_RESULT]).toBe('Sunny');
    expect(tool.parentSpanId).toBe(invoke.spanContext().spanId);

    // The whole tree shares one trace.
    const traceId = invoke.spanContext().traceId;
    expect(chat.spanContext().traceId).toBe(traceId);
    expect(tool.spanContext().traceId).toBe(traceId);
  });

  test('a tool_result flagged is_error marks the execute_tool span as error', () => {
    const tracer = new ClaudeAgentOtelTracer({prompt: 'p'});
    tracer.processMessage({
      type: 'assistant',
      session_id: 's',
      message: {
        model: 'm',
        content: [
          {type: 'tool_use', id: 't9', name: 'Bash', input: {command: 'boom'}},
        ],
      },
    } as any);
    tracer.processMessage({
      type: 'user',
      session_id: 's',
      message: {
        content: [
          {
            type: 'tool_result',
            tool_use_id: 't9',
            content: 'command not found',
            is_error: true,
          },
        ],
      },
    } as any);
    tracer.finalize({
      type: 'result',
      subtype: 'success',
      is_error: false,
    } as any);

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
    tracer.processMessage({
      type: 'assistant',
      session_id: 's',
      message: {
        model: 'm',
        content: [{type: 'tool_use', id: 'tX', name: 'Bash', input: {}}],
      },
    } as any);
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
    tracer.processMessage({
      type: 'assistant',
      session_id: 's',
      message: {model: 'm', content: [{type: 'text', text: 'trying'}]},
    } as any);
    tracer.finalize({
      type: 'result',
      subtype: 'error_max_turns',
      is_error: true,
      errors: ['boom'],
    } as any);

    const invoke = findSpan(getExporter().getFinishedSpans(), INVOKE);
    expect(invoke.status.code).toBe(SpanStatusCode.ERROR);
    expect(invoke.status.message).toContain('boom');
  });
});
