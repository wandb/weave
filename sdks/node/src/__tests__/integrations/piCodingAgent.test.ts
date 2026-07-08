import {SpanKind, SpanStatusCode} from '@opentelemetry/api';
import {
  BasicTracerProvider,
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {PiCodingAgentOtelAdapter} from '../../integrations/piCodingAgent';
import type {
  PiExtensionApi,
  PiExtensionContext,
} from '../../integrations/piCodingAgent.types';

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function makeExporterAndAdapter(opts: {captureContent?: boolean} = {}): {
  exporter: InMemorySpanExporter;
  emit: EmitFn;
} {
  const exporter = new InMemorySpanExporter();
  const provider = new BasicTracerProvider({
    spanProcessors: [new SimpleSpanProcessor(exporter)],
  });
  const adapter = new PiCodingAgentOtelAdapter({
    tracer: provider.getTracer('test'),
    ...opts,
  });

  const handlers = new Map<string, (event: any, ctx: any) => any>();
  const pi: PiExtensionApi = {
    on(type, handler) {
      handlers.set(type, handler as any);
    },
  };
  adapter.asExtension().setup(pi);

  const emit: EmitFn = (type, event = {}, ctx = DEFAULT_CTX) =>
    handlers.get(type)?.({type, ...event}, ctx);

  return {exporter, emit};
}

type EmitFn = (
  type: string,
  event?: Record<string, unknown>,
  ctx?: PiExtensionContext
) => void;

const DEFAULT_CTX: PiExtensionContext = {
  cwd: '/home/user/project',
  model: {id: 'claude-3-5-sonnet-20241022', provider: 'anthropic'},
  sessionManager: {getSessionId: () => 'test-session-id'},
};

const MOCK_USAGE = {
  input: 100,
  output: 50,
  cacheRead: 10,
  cacheWrite: 5,
  totalTokens: 150,
  cost: {total: 0.0015},
};

const MOCK_ASSISTANT_MSG = {
  role: 'assistant',
  model: 'claude-3-5-sonnet-20241022',
  provider: 'anthropic',
  usage: MOCK_USAGE,
  stopReason: 'stop',
  content: [{type: 'text', text: 'Hello!'}],
};

// Fire the standard session → invoke_agent preamble
function startSession(emit: EmitFn, ctx = DEFAULT_CTX) {
  emit('session_start', {reason: 'initial'}, ctx);
}

function startInvoke(emit: EmitFn, prompt = 'hello', ctx = DEFAULT_CTX) {
  startSession(emit, ctx);
  emit('before_agent_start', {prompt, systemPrompt: 'be helpful'}, ctx);
}

function startTurn(emit: EmitFn, ctx = DEFAULT_CTX) {
  startInvoke(emit, 'hello', ctx);
  emit('turn_start', {turnIndex: 0, timestamp: Date.now()}, ctx);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PiCodingAgentOtelAdapter', () => {
  describe('invoke_agent span', () => {
    it('emits with correct attributes', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startSession(emit);

      // Prompt
      emit('before_agent_start', {
        prompt: 'tell me a joke',
        systemPrompt: 'sys',
      });
      emit('agent_end', {messages: []});

      emit('session_shutdown');

      const span = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent pi-coding-agent');
      expect(span!.attributes['gen_ai.agent.name']).toBe('pi-coding-agent');
      expect(span!.attributes['gen_ai.provider.name']).toBe('anthropic');
      expect(span!.attributes['gen_ai.conversation.id']).toBe(
        'test-session-id'
      );
      expect(span!.attributes['pi.session.cwd']).toBe('/home/user/project');
      // Integration-tracking metadata is stamped on every span this
      // integration emits. OTel attributes are scalars, so the nested
      // `integration` shape is flattened to dotted keys.
      const stamped = exporter
        .getFinishedSpans()
        .filter(s => s.attributes['integration.name'] !== undefined);
      expect(stamped.length).toBeGreaterThan(0);
      expect(
        stamped.every(
          s => s.attributes['integration.name'] === 'pi_coding_agent'
        )
      ).toBe(true);
      expect(
        stamped.every(
          s =>
            s.attributes['integration.meta.package_name'] ===
            '@pi-dev/coding-agent'
        )
      ).toBe(true);
    });

    it('emits one trace per prompt, linked by conversation id', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startSession(emit);
      // Prompt 1
      emit('before_agent_start', {prompt: 'first', systemPrompt: 'sys'});
      emit('agent_end', {messages: []});
      // Prompt 2
      emit('before_agent_start', {prompt: 'second', systemPrompt: 'sys'});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const invokes = exporter
        .getFinishedSpans()
        .filter(s => s.name === 'invoke_agent pi-coding-agent');
      expect(invokes).toHaveLength(2);
      expect(invokes[0].spanContext().traceId).not.toBe(
        invokes[1].spanContext().traceId
      );
      expect(invokes[0].attributes['gen_ai.conversation.id']).toBe(
        'test-session-id'
      );
      expect(invokes[1].attributes['gen_ai.conversation.id']).toBe(
        'test-session-id'
      );
    });

    it('sets gen_ai.input.messages and gen_ai.system_instructions when captureContent is true', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startInvoke(emit, 'what time is it?');
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent pi-coding-agent')!;
      const inputMessages = JSON.parse(
        invoke.attributes['gen_ai.input.messages'] as string
      );
      expect(inputMessages).toEqual([
        {role: 'user', content: 'what time is it?'},
      ]);
      const systemInstructions = JSON.parse(
        invoke.attributes['gen_ai.system_instructions'] as string
      );
      expect(systemInstructions).toEqual(['be helpful']);
    });

    it('sets gen_ai.output.messages from assistant messages in agent_end', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startInvoke(emit, 'what time is it?');
      emit('agent_end', {messages: [MOCK_ASSISTANT_MSG]});
      emit('session_shutdown');

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent pi-coding-agent')!;
      const outputMessages = JSON.parse(
        invoke.attributes['gen_ai.output.messages'] as string
      );
      expect(outputMessages).toHaveLength(1);
      expect(outputMessages[0].role).toBe('assistant');
      expect(outputMessages[0].parts[0]).toEqual({
        type: 'text',
        content: 'Hello!',
      });
      expect(outputMessages[0].finish_reason).toBe('stop');
    });

    it('omits message attributes when captureContent is false', () => {
      const {exporter, emit} = makeExporterAndAdapter({captureContent: false});
      startInvoke(emit, 'what time is it?');
      emit('agent_end', {messages: [MOCK_ASSISTANT_MSG]});
      emit('session_shutdown');

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent pi-coding-agent')!;
      expect(invoke.attributes['gen_ai.input.messages']).toBeUndefined();
      expect(invoke.attributes['gen_ai.output.messages']).toBeUndefined();
      expect(invoke.attributes['gen_ai.system_instructions']).toBeUndefined();
    });

    it('aggregates usage across multiple turns', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startInvoke(emit);

      // Turn 1
      emit('turn_start', {turnIndex: 0, timestamp: Date.now()});
      emit('turn_end', {
        turnIndex: 0,
        message: {
          ...MOCK_ASSISTANT_MSG,
          usage: {
            input: 100,
            output: 50,
            cacheRead: 0,
            cacheWrite: 0,
            totalTokens: 150,
            cost: {total: 0.001},
          },
        },
      });

      // Turn 2
      emit('turn_start', {turnIndex: 1, timestamp: Date.now()});
      emit('turn_end', {
        turnIndex: 1,
        message: {
          ...MOCK_ASSISTANT_MSG,
          usage: {
            input: 200,
            output: 80,
            cacheRead: 0,
            cacheWrite: 0,
            totalTokens: 280,
            cost: {total: 0.002},
          },
        },
      });

      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent pi-coding-agent')!;
      expect(invoke.attributes['gen_ai.usage.input_tokens']).toBe(300);
      expect(invoke.attributes['gen_ai.usage.output_tokens']).toBe(130);
      expect(invoke.attributes['gen_ai.usage.total_tokens']).toBe(430);
      expect(invoke.attributes['pi.usage.cost_usd']).toBeCloseTo(0.003);
    });
  });

  // ── chat span ─────────────────────────────────────────────────────────────

  describe('chat span', () => {
    it('has correct attributes, is a child of invoke_agent, and sets response attributes on turn_end', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startTurn(emit);
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const spans = exporter.getFinishedSpans();
      const invoke = spans.find(
        s => s.name === 'invoke_agent pi-coding-agent'
      )!;
      const chat = spans.find(s => s.name.startsWith('chat '))!;
      expect(chat.kind).toBe(SpanKind.CLIENT);
      expect(chat.parentSpanContext?.spanId).toBe(invoke.spanContext().spanId);
      expect(chat.attributes['gen_ai.operation.name']).toBe('chat');
      expect(chat.attributes['gen_ai.provider.name']).toBe('anthropic');
      expect(chat.attributes['gen_ai.request.model']).toBe(
        'claude-3-5-sonnet-20241022'
      );
      expect(chat.attributes['gen_ai.conversation.id']).toBe('test-session-id');
      expect(chat.attributes['gen_ai.response.model']).toBe(
        'claude-3-5-sonnet-20241022'
      );
      expect(chat.attributes['gen_ai.response.finish_reasons']).toEqual([
        'stop',
      ]);
      expect(chat.attributes['gen_ai.usage.input_tokens']).toBe(100);
      expect(chat.attributes['gen_ai.usage.output_tokens']).toBe(50);
      expect(chat.attributes['gen_ai.usage.total_tokens']).toBe(150);
      expect(chat.attributes['gen_ai.usage.cache_read.input_tokens']).toBe(10);
      expect(chat.attributes['gen_ai.usage.cache_creation.input_tokens']).toBe(
        5
      );
    });

    it('sets gen_ai.system_instructions and gen_ai.input.messages from context', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startTurn(emit);
      emit('context', {
        messages: [
          {role: 'system', content: 'You are a helpful assistant.'},
          {role: 'user', content: 'hello'},
        ],
      });
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const chat = exporter
        .getFinishedSpans()
        .find(s => s.name.startsWith('chat '))!;
      const systemInstructions = JSON.parse(
        chat.attributes['gen_ai.system_instructions'] as string
      );
      expect(systemInstructions).toEqual(['You are a helpful assistant.']);
      const inputMessages = JSON.parse(
        chat.attributes['gen_ai.input.messages'] as string
      );
      expect(inputMessages).toEqual([{role: 'user', content: 'hello'}]);
    });

    it('skips gen_ai.system_instructions when no system messages in context', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startTurn(emit);
      emit('context', {messages: [{role: 'user', content: 'hello'}]});
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const chat = exporter
        .getFinishedSpans()
        .find(s => s.name.startsWith('chat '))!;
      expect(chat.attributes['gen_ai.system_instructions']).toBeUndefined();
    });

    it('sets gen_ai.output.messages on turn_end with assistant content', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startTurn(emit);
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const chat = exporter
        .getFinishedSpans()
        .find(s => s.name.startsWith('chat '))!;
      const outputMessages = JSON.parse(
        chat.attributes['gen_ai.output.messages'] as string
      );
      expect(outputMessages).toHaveLength(1);
      expect(outputMessages[0].role).toBe('assistant');
      expect(outputMessages[0].parts[0]).toEqual({
        type: 'text',
        content: 'Hello!',
      });
      expect(outputMessages[0].finish_reason).toBe('stop');
    });

    it('omits message attributes when captureContent is false', () => {
      const {exporter, emit} = makeExporterAndAdapter({captureContent: false});
      startTurn(emit);
      emit('context', {messages: [{role: 'system', content: 'sys'}]});
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const chat = exporter
        .getFinishedSpans()
        .find(s => s.name.startsWith('chat '))!;
      expect(chat.attributes['gen_ai.input.messages']).toBeUndefined();
      expect(chat.attributes['gen_ai.output.messages']).toBeUndefined();
      expect(chat.attributes['gen_ai.system_instructions']).toBeUndefined();
    });
  });

  // ── tool spans ────────────────────────────────────────────────────────────

  describe('tool spans', () => {
    it('has correct attributes, is a sibling of chat, and sets tool call arguments and result', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startTurn(emit);
      emit('tool_call', {
        toolCallId: 'call-1',
        toolName: 'bash',
        input: {cmd: 'ls'},
      });
      emit('tool_result', {
        toolCallId: 'call-1',
        toolName: 'bash',
        content: 'file.ts',
        isError: false,
      });
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const spans = exporter.getFinishedSpans();
      const invoke = spans.find(
        s => s.name === 'invoke_agent pi-coding-agent'
      )!;
      const tool = spans.find(s => s.name === 'execute_tool bash')!;
      expect(tool.kind).toBe(SpanKind.INTERNAL);
      expect(tool.parentSpanContext?.spanId).toBe(invoke.spanContext().spanId);
      expect(tool.attributes['gen_ai.tool.name']).toBe('bash');
      expect(tool.attributes['gen_ai.tool.call.id']).toBe('call-1');
      expect(tool.attributes['gen_ai.conversation.id']).toBe('test-session-id');
      expect(tool.attributes['gen_ai.tool.call.arguments']).toBe(
        JSON.stringify({cmd: 'ls'})
      );
      expect(tool.attributes['gen_ai.tool.call.result']).toBe('file.ts');
    });

    it('omits tool arguments and result when captureContent is false', () => {
      const {exporter, emit} = makeExporterAndAdapter({captureContent: false});
      startTurn(emit);
      emit('tool_call', {
        toolCallId: 'call-1',
        toolName: 'bash',
        input: {cmd: 'ls'},
      });
      emit('tool_result', {
        toolCallId: 'call-1',
        toolName: 'bash',
        content: 'file.ts',
        isError: false,
      });
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const tool = exporter
        .getFinishedSpans()
        .find(s => s.name === 'execute_tool bash')!;
      expect(tool.attributes['gen_ai.tool.call.arguments']).toBeUndefined();
      expect(tool.attributes['gen_ai.tool.call.result']).toBeUndefined();
    });

    it('sets error attributes on tool_result with isError', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startTurn(emit);
      emit('tool_call', {toolCallId: 'call-1', toolName: 'bash', input: {}});
      emit('tool_result', {
        toolCallId: 'call-1',
        toolName: 'bash',
        content: 'Permission denied',
        isError: true,
      });
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const tool = exporter
        .getFinishedSpans()
        .find(s => s.name === 'execute_tool bash')!;
      expect(tool.attributes['error.type']).toBe('tool_error');
      expect(tool.status.code).toBe(SpanStatusCode.ERROR);
      expect(tool.status.message).toBe('Permission denied');
    });

    it('aborts open tool spans when agent_end fires', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startTurn(emit);
      emit('tool_call', {toolCallId: 'call-1', toolName: 'bash', input: {}});
      // tool_result never fires — agent ends with open tool
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const tool = exporter
        .getFinishedSpans()
        .find(s => s.name === 'execute_tool bash')!;
      expect(tool.attributes['error.type']).toBe('aborted');
      expect(tool.status.code).toBe(SpanStatusCode.ERROR);
    });
  });

  // ── compaction span ───────────────────────────────────────────────────────

  describe('compaction span', () => {
    it('emits pi.coding_agent.compaction as a root span', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startSession(emit);
      emit('session_compact', {
        reason: 'context_limit',
        aborted: false,
        willRetry: false,
      });
      emit('session_shutdown');

      const compact = exporter
        .getFinishedSpans()
        .find(s => s.name === 'pi.coding_agent.compaction')!;
      expect(compact).toBeDefined();
      expect(compact.parentSpanContext?.spanId).toBeUndefined();
      expect(compact.attributes['pi.compaction.reason']).toBe('context_limit');
      expect(compact.attributes['pi.compaction.aborted']).toBe(false);
      expect(compact.attributes['pi.compaction.will_retry']).toBe(false);
      expect(compact.attributes['gen_ai.conversation.id']).toBe(
        'test-session-id'
      );
    });
  });

  // ── auto-retry events ─────────────────────────────────────────────────────

  describe('auto-retry events', () => {
    it('adds auto_retry_start and auto_retry_end events to invoke_agent span', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startInvoke(emit);
      emit('auto_retry_start', {
        attempt: 1,
        maxAttempts: 3,
        errorMessage: 'rate limit',
      });
      emit('auto_retry_end', {success: true, attempt: 1});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent pi-coding-agent')!;
      const retryStart = invoke.events.find(e => e.name === 'auto_retry_start');
      const retryEnd = invoke.events.find(e => e.name === 'auto_retry_end');
      expect(retryStart).toBeDefined();
      expect(retryStart!.attributes!['auto_retry.attempt']).toBe(1);
      expect(retryStart!.attributes!['auto_retry.error_message']).toBe(
        'rate limit'
      );
      expect(retryEnd).toBeDefined();
      expect(retryEnd!.attributes!['auto_retry.success']).toBe(true);
    });
  });
});
