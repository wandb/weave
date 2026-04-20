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
  // ── Session span ──────────────────────────────────────────────────────────

  describe('session span', () => {
    it('starts with correct attributes', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startSession(emit);
      emit('session_shutdown');

      const span = exporter
        .getFinishedSpans()
        .find(s => s.name === 'pi.coding_agent.session');
      expect(span).toBeDefined();
      expect(span!.kind).toBe(SpanKind.INTERNAL);
      expect(span!.attributes['gen_ai.agent.name']).toBe('pi-coding-agent');
      expect(span!.attributes['gen_ai.conversation.id']).toBe(
        'test-session-id'
      );
      expect(span!.attributes['pi.session.cwd']).toBe('/home/user/project');
    });

    it('is ended by session_shutdown', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startSession(emit);
      expect(exporter.getFinishedSpans()).toHaveLength(0);
      emit('session_shutdown');
      expect(
        exporter
          .getFinishedSpans()
          .find(s => s.name === 'pi.coding_agent.session')
      ).toBeDefined();
    });
  });

  // ── invoke_agent span ─────────────────────────────────────────────────────

  describe('invoke_agent span', () => {
    it('has correct attributes and is a child of the session span', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startInvoke(emit);
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const spans = exporter.getFinishedSpans();
      const session = spans.find(s => s.name === 'pi.coding_agent.session')!;
      const invoke = spans.find(
        s => s.name === 'invoke_agent pi-coding-agent'
      )!;
      expect(invoke.parentSpanId).toBe(session.spanContext().spanId);
      expect(invoke.attributes['gen_ai.provider.name']).toBe('anthropic');
      expect(invoke.attributes['gen_ai.conversation.id']).toBe(
        'test-session-id'
      );
    });

    it('adds gen_ai.user.message event when captureContent is true', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startInvoke(emit, 'what time is it?');
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent pi-coding-agent')!;
      expect(invoke.events).toHaveLength(2);
      expect(invoke.events[0].name).toBe('gen_ai.system.message');

      expect(invoke.events[1].name).toBe('gen_ai.user.message');
      const userContent = JSON.parse(
        invoke.events[1].attributes!['gen_ai.event.content'] as string
      );
      expect(userContent.content).toBe('what time is it?');
    });

    it('omits event content when captureContent is false', () => {
      const {exporter, emit} = makeExporterAndAdapter({captureContent: false});
      startInvoke(emit, 'what time is it?');
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent pi-coding-agent')!;
      expect(invoke.events).toHaveLength(0);
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
      expect(chat.parentSpanId).toBe(invoke.spanContext().spanId);
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

    it('adds gen_ai.system.message event from context', () => {
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
      const sysEvent = chat.events.find(
        e => e.name === 'gen_ai.system.message'
      );
      expect(sysEvent).toBeDefined();
      const content = JSON.parse(
        sysEvent!.attributes!['gen_ai.event.content'] as string
      );
      expect(content[0].role).toBe('system');
    });

    it('skips gen_ai.system.message when no system messages in context', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startTurn(emit);
      emit('context', {messages: [{role: 'user', content: 'hello'}]});
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const chat = exporter
        .getFinishedSpans()
        .find(s => s.name.startsWith('chat '))!;
      expect(
        chat.events.find(e => e.name === 'gen_ai.system.message')
      ).toBeUndefined();
    });

    it('adds gen_ai.assistant.message event on message_end', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startTurn(emit);
      emit('message_end', {message: MOCK_ASSISTANT_MSG});
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const chat = exporter
        .getFinishedSpans()
        .find(s => s.name.startsWith('chat '))!;
      const assistantEvent = chat.events.find(
        e => e.name === 'gen_ai.assistant.message'
      );
      expect(assistantEvent).toBeDefined();
      const content = JSON.parse(
        assistantEvent!.attributes!['gen_ai.event.content'] as string
      );
      expect(content.role).toBe('assistant');
    });

    it('omits event content when captureContent is false', () => {
      const {exporter, emit} = makeExporterAndAdapter({captureContent: false});
      startTurn(emit);
      emit('context', {messages: [{role: 'system', content: 'sys'}]});
      emit('message_end', {message: MOCK_ASSISTANT_MSG});
      emit('turn_end', {turnIndex: 0, message: MOCK_ASSISTANT_MSG});
      emit('agent_end', {messages: []});
      emit('session_shutdown');

      const chat = exporter
        .getFinishedSpans()
        .find(s => s.name.startsWith('chat '))!;
      for (const event of chat.events) {
        expect(event.attributes?.['gen_ai.event.content']).toBeUndefined();
      }
    });
  });

  // ── tool spans ────────────────────────────────────────────────────────────

  describe('tool spans', () => {
    it('has correct attributes, is a sibling of chat, and adds tool message event', () => {
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
      expect(tool.parentSpanId).toBe(invoke.spanContext().spanId);
      expect(tool.attributes['gen_ai.tool.name']).toBe('bash');
      expect(tool.attributes['gen_ai.tool.call.id']).toBe('call-1');
      expect(tool.attributes['gen_ai.conversation.id']).toBe('test-session-id');
      const toolEvent = tool.events.find(e => e.name === 'gen_ai.tool.message');
      expect(toolEvent).toBeDefined();
      const content = JSON.parse(
        toolEvent!.attributes!['gen_ai.event.content'] as string
      );
      expect(content.content).toBe('file.ts');
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
    it('emits pi.coding_agent.compaction as child of session', () => {
      const {exporter, emit} = makeExporterAndAdapter();
      startSession(emit);
      emit('session_compact', {
        reason: 'context_limit',
        aborted: false,
        willRetry: false,
      });
      emit('session_shutdown');

      const spans = exporter.getFinishedSpans();
      const session = spans.find(s => s.name === 'pi.coding_agent.session')!;
      const compact = spans.find(s => s.name === 'pi.coding_agent.compaction')!;
      expect(compact).toBeDefined();
      expect(compact.parentSpanId).toBe(session.spanContext().spanId);
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
