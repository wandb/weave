import {SpanKind, SpanStatusCode} from '@opentelemetry/api';
import {
  BasicTracerProvider,
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {OpenCodeCodingAgentOtelAdapter} from '../../integrations/opencodeCodingAgent';

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function makeAdapter(
  opts: {captureContent?: boolean; agentName?: string} = {}
): {
  exporter: InMemorySpanExporter;
  adapter: OpenCodeCodingAgentOtelAdapter;
} {
  const exporter = new InMemorySpanExporter();
  const provider = new BasicTracerProvider({
    spanProcessors: [new SimpleSpanProcessor(exporter)],
  });
  const adapter = new OpenCodeCodingAgentOtelAdapter({
    tracer: provider.getTracer('test'),
    ...opts,
  });
  return {exporter, adapter};
}

const TEST_SESSION = {
  id: 'test-session-id',
  title: 'Test Session',
  modelID: 'claude-sonnet-4-20250514',
  providerID: 'anthropic',
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
};

// Fire a standard session_created → user message preamble
function startSession(adapter: OpenCodeCodingAgentOtelAdapter): void {
  adapter.onEvent({
    type: 'session.created',
    properties: TEST_SESSION as any,
  });
}

function startInvoke(
  adapter: OpenCodeCodingAgentOtelAdapter,
  prompt = 'hello'
): void {
  startSession(adapter);
  adapter.setSessionCwd('/home/user/project');

  // User message triggers invoke_agent
  adapter.onEvent({
    type: 'message.updated',
    properties: {
      id: `msg-user-${Date.now()}`,
      role: 'user',
      sessionID: TEST_SESSION.id,
      createdAt: new Date().toISOString(),
    },
  });

  if (prompt) {
    adapter.setInputMessages([{role: 'user', content: prompt}]);
  }
}

function startAssistant(
  adapter: OpenCodeCodingAgentOtelAdapter,
  messageId = `msg-assistant-${Date.now()}`
): void {
  adapter.onEvent({
    type: 'message.updated',
    properties: {
      id: messageId,
      role: 'assistant',
      sessionID: TEST_SESSION.id,
      createdAt: new Date().toISOString(),
    },
  });
}

function addTextPart(
  adapter: OpenCodeCodingAgentOtelAdapter,
  text: string
): void {
  adapter.onEvent({
    type: 'message.part.updated',
    properties: {
      sessionID: TEST_SESSION.id,
      messageID: 'msg-assistant',
      part: {type: 'text', text},
    },
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('OpenCodeCodingAgentOtelAdapter', () => {
  describe('invoke_agent span', () => {
    it('emits with correct attributes', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter, 'tell me a joke');
      adapter.endInvokeAgentSpan();

      const span = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent opencode');
      expect(span).toBeDefined();
      expect(span!.attributes['gen_ai.operation.name']).toBe('invoke_agent');
      expect(span!.attributes['gen_ai.agent.name']).toBe('opencode');
      expect(span!.attributes['gen_ai.provider.name']).toBe('anthropic');
      expect(span!.attributes['gen_ai.conversation.id']).toBe(
        'test-session-id'
      );
      expect(span!.attributes['opencode.session.cwd']).toBe(
        '/home/user/project'
      );
    });

    it('stamps integration provenance on every span', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);
      adapter.endInvokeAgentSpan();

      const stamped = exporter
        .getFinishedSpans()
        .filter(s => s.attributes['integration.name'] !== undefined);
      expect(stamped.length).toBeGreaterThan(0);
      expect(
        stamped.every(s => s.attributes['integration.name'] === 'opencode')
      ).toBe(true);
      expect(
        stamped.every(
          s => s.attributes['integration.meta.package_name'] === 'opencode-ai'
        )
      ).toBe(true);
    });

    it('emits one trace per prompt, linked by conversation id', () => {
      const {exporter, adapter} = makeAdapter();
      startSession(adapter);

      // Prompt 1
      adapter.onEvent({
        type: 'message.updated',
        properties: {
          id: 'msg-user-1',
          role: 'user',
          sessionID: TEST_SESSION.id,
          createdAt: new Date().toISOString(),
        },
      });
      adapter.endInvokeAgentSpan();

      // Prompt 2
      adapter.onEvent({
        type: 'message.updated',
        properties: {
          id: 'msg-user-2',
          role: 'user',
          sessionID: TEST_SESSION.id,
          createdAt: new Date().toISOString(),
        },
      });
      adapter.endInvokeAgentSpan();

      const invokes = exporter
        .getFinishedSpans()
        .filter(s => s.name === 'invoke_agent opencode');
      expect(invokes).toHaveLength(2);
      // Each prompt gets its own trace (different trace IDs)
      expect(invokes[0].spanContext().traceId).not.toBe(
        invokes[1].spanContext().traceId
      );
      // But they share the same conversation ID
      expect(invokes[0].attributes['gen_ai.conversation.id']).toBe(
        'test-session-id'
      );
      expect(invokes[1].attributes['gen_ai.conversation.id']).toBe(
        'test-session-id'
      );
    });

    it('sets gen_ai.input.messages when captureContent is true', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter, 'what time is it?');
      adapter.endInvokeAgentSpan();

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent opencode')!;
      const inputMessages = JSON.parse(
        invoke.attributes['gen_ai.input.messages'] as string
      );
      expect(inputMessages).toEqual([
        {role: 'user', content: 'what time is it?'},
      ]);
    });

    it('sets gen_ai.system_instructions when provided', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);
      adapter.setSystemInstructions(['You are a helpful coding assistant.']);
      adapter.endInvokeAgentSpan();

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent opencode')!;
      const systemInstructions = JSON.parse(
        invoke.attributes['gen_ai.system_instructions'] as string
      );
      expect(systemInstructions).toEqual([
        'You are a helpful coding assistant.',
      ]);
    });

    it('sets gen_ai.output.messages from accumulated assistant parts', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter, 'what time is it?');
      startAssistant(adapter, 'msg-assistant-1');
      addTextPart(adapter, 'It is 3 PM.');
      adapter.endInvokeAgentSpan();

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent opencode')!;
      const outputMessages = JSON.parse(
        invoke.attributes['gen_ai.output.messages'] as string
      );
      expect(outputMessages).toHaveLength(1);
      expect(outputMessages[0].role).toBe('assistant');
      expect(outputMessages[0].parts[0]).toEqual({
        type: 'text',
        content: 'It is 3 PM.',
      });
    });

    it('omits message attributes when captureContent is false', () => {
      const {exporter, adapter} = makeAdapter({captureContent: false});
      startInvoke(adapter, 'what time is it?');
      startAssistant(adapter, 'msg-assistant-no-content');
      addTextPart(adapter, 'It is 3 PM.');
      adapter.endInvokeAgentSpan();

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent opencode')!;
      expect(invoke.attributes['gen_ai.input.messages']).toBeUndefined();
      expect(invoke.attributes['gen_ai.output.messages']).toBeUndefined();
      expect(invoke.attributes['gen_ai.system_instructions']).toBeUndefined();
    });

    it('supports custom agent name', () => {
      const {exporter, adapter} = makeAdapter({agentName: 'my-custom-agent'});
      startSession(adapter);
      adapter.onEvent({
        type: 'message.updated',
        properties: {
          id: 'msg-user-custom',
          role: 'user',
          sessionID: TEST_SESSION.id,
          createdAt: new Date().toISOString(),
        },
      });
      adapter.endInvokeAgentSpan();

      const span = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent my-custom-agent');
      expect(span).toBeDefined();
      expect(span!.attributes['gen_ai.agent.name']).toBe('my-custom-agent');
    });

    it('ends invoke_agent span on session.idle', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);
      expect(adapter.isActive).toBe(true);

      adapter.onEvent({
        type: 'session.idle',
        properties: {sessionID: TEST_SESSION.id},
      });
      expect(adapter.isActive).toBe(false);

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent opencode');
      expect(invoke).toBeDefined();
    });

    it('marks invoke_agent as error on session.error', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);

      adapter.onEvent({
        type: 'session.error',
        properties: {
          sessionID: TEST_SESSION.id,
          error: 'Rate limit exceeded',
        },
      });

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent opencode')!;
      expect(invoke.attributes['error.type']).toBe('session_error');
      expect(invoke.status.code).toBe(SpanStatusCode.ERROR);
      expect(invoke.status.message).toBe('Rate limit exceeded');
    });
  });

  // ── chat span ─────────────────────────────────────────────────────────────

  describe('chat span', () => {
    it('has correct attributes and is a child of invoke_agent', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);
      startAssistant(adapter, 'msg-assistant-chat');
      addTextPart(adapter, 'Hello!');
      adapter.endInvokeAgentSpan();

      const spans = exporter.getFinishedSpans();
      const invoke = spans.find(s => s.name === 'invoke_agent opencode')!;
      const chat = spans.find(s => s.name.startsWith('chat '))!;
      expect(chat).toBeDefined();
      expect(chat.kind).toBe(SpanKind.CLIENT);
      expect(chat.parentSpanId).toBe(invoke.spanContext().spanId);
      expect(chat.attributes['gen_ai.operation.name']).toBe('chat');
      expect(chat.attributes['gen_ai.provider.name']).toBe('anthropic');
      expect(chat.attributes['gen_ai.request.model']).toBe(
        'claude-sonnet-4-20250514'
      );
      expect(chat.attributes['gen_ai.conversation.id']).toBe('test-session-id');
    });

    it('sets gen_ai.output.messages with assistant content', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);
      startAssistant(adapter, 'msg-assistant-output');
      addTextPart(adapter, 'The answer is 42.');
      adapter.endInvokeAgentSpan();

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
        content: 'The answer is 42.',
      });
    });

    it('omits message attributes when captureContent is false', () => {
      const {exporter, adapter} = makeAdapter({captureContent: false});
      startInvoke(adapter);
      startAssistant(adapter, 'msg-assistant-no-content-2');
      addTextPart(adapter, 'Secret content');
      adapter.endInvokeAgentSpan();

      const chat = exporter
        .getFinishedSpans()
        .find(s => s.name.startsWith('chat '))!;
      expect(chat.attributes['gen_ai.output.messages']).toBeUndefined();
    });

    it('handles reasoning parts', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);
      startAssistant(adapter, 'msg-assistant-reasoning');

      adapter.onEvent({
        type: 'message.part.updated',
        properties: {
          sessionID: TEST_SESSION.id,
          messageID: 'msg-assistant-reasoning',
          part: {type: 'reasoning', text: 'Let me think about this...'},
        },
      });
      addTextPart(adapter, 'Done thinking.');
      adapter.endInvokeAgentSpan();

      const chat = exporter
        .getFinishedSpans()
        .find(s => s.name.startsWith('chat '))!;
      const outputMessages = JSON.parse(
        chat.attributes['gen_ai.output.messages'] as string
      );
      expect(outputMessages[0].parts).toEqual([
        {type: 'reasoning', content: 'Let me think about this...'},
        {type: 'text', content: 'Done thinking.'},
      ]);
    });
  });

  // ── tool spans ────────────────────────────────────────────────────────────

  describe('tool spans', () => {
    it('has correct attributes and is a child of invoke_agent', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);

      adapter.onToolExecuteBefore({
        sessionID: TEST_SESSION.id,
        tool: 'bash',
        args: {command: 'ls -la'},
      });
      adapter.onToolExecuteAfter({
        sessionID: TEST_SESSION.id,
        tool: 'bash',
        args: {command: 'ls -la'},
        result: 'file1.ts\nfile2.ts',
      });
      adapter.endInvokeAgentSpan();

      const spans = exporter.getFinishedSpans();
      const invoke = spans.find(s => s.name === 'invoke_agent opencode')!;
      const tool = spans.find(s => s.name === 'execute_tool bash')!;
      expect(tool).toBeDefined();
      expect(tool.kind).toBe(SpanKind.INTERNAL);
      expect(tool.parentSpanId).toBe(invoke.spanContext().spanId);
      expect(tool.attributes['gen_ai.operation.name']).toBe('execute_tool');
      expect(tool.attributes['gen_ai.tool.name']).toBe('bash');
      expect(tool.attributes['gen_ai.conversation.id']).toBe('test-session-id');
      expect(tool.attributes['gen_ai.tool.call.arguments']).toBe(
        JSON.stringify({command: 'ls -la'})
      );
      expect(tool.attributes['gen_ai.tool.call.result']).toBe(
        'file1.ts\nfile2.ts'
      );
    });

    it('omits tool arguments and result when captureContent is false', () => {
      const {exporter, adapter} = makeAdapter({captureContent: false});
      startInvoke(adapter);

      adapter.onToolExecuteBefore({
        sessionID: TEST_SESSION.id,
        tool: 'bash',
        args: {command: 'secret-command'},
      });
      adapter.onToolExecuteAfter({
        sessionID: TEST_SESSION.id,
        tool: 'bash',
        args: {command: 'secret-command'},
        result: 'secret-output',
      });
      adapter.endInvokeAgentSpan();

      const tool = exporter
        .getFinishedSpans()
        .find(s => s.name === 'execute_tool bash')!;
      expect(tool.attributes['gen_ai.tool.call.arguments']).toBeUndefined();
      expect(tool.attributes['gen_ai.tool.call.result']).toBeUndefined();
    });

    it('sets error attributes on tool_execute.after with error', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);

      adapter.onToolExecuteBefore({
        sessionID: TEST_SESSION.id,
        tool: 'bash',
        args: {command: 'bad-command'},
      });
      adapter.onToolExecuteAfter({
        sessionID: TEST_SESSION.id,
        tool: 'bash',
        args: {command: 'bad-command'},
        result: null,
        error: 'Permission denied',
      });
      adapter.endInvokeAgentSpan();

      const tool = exporter
        .getFinishedSpans()
        .find(s => s.name === 'execute_tool bash')!;
      expect(tool.attributes['error.type']).toBe('tool_error');
      expect(tool.status.code).toBe(SpanStatusCode.ERROR);
      expect(tool.status.message).toBe('Permission denied');
    });

    it('aborts open tool spans when invoke_agent ends', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);

      adapter.onToolExecuteBefore({
        sessionID: TEST_SESSION.id,
        tool: 'bash',
        args: {command: 'long-running'},
      });
      // tool_execute.after never fires — agent ends with open tool
      adapter.endInvokeAgentSpan();

      const tool = exporter
        .getFinishedSpans()
        .find(s => s.name === 'execute_tool bash')!;
      expect(tool.attributes['error.type']).toBe('aborted');
      expect(tool.status.code).toBe(SpanStatusCode.ERROR);
    });

    it('handles multiple concurrent tool calls', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);

      adapter.onToolExecuteBefore({
        sessionID: TEST_SESSION.id,
        tool: 'read',
        args: {filePath: '/src/index.ts'},
      });
      adapter.onToolExecuteBefore({
        sessionID: TEST_SESSION.id,
        tool: 'bash',
        args: {command: 'ls'},
      });
      adapter.onToolExecuteAfter({
        sessionID: TEST_SESSION.id,
        tool: 'read',
        args: {filePath: '/src/index.ts'},
        result: 'content',
      });
      adapter.onToolExecuteAfter({
        sessionID: TEST_SESSION.id,
        tool: 'bash',
        args: {command: 'ls'},
        result: 'files',
      });
      adapter.endInvokeAgentSpan();

      const spans = exporter.getFinishedSpans();
      const readTool = spans.find(s => s.name === 'execute_tool read')!;
      const bashTool = spans.find(s => s.name === 'execute_tool bash')!;
      expect(readTool).toBeDefined();
      expect(bashTool).toBeDefined();
      expect(readTool.attributes['gen_ai.tool.call.result']).toBe('content');
      expect(bashTool.attributes['gen_ai.tool.call.result']).toBe('files');
    });
  });

  // ── compaction span ───────────────────────────────────────────────────────

  describe('compaction span', () => {
    it('emits opencode.compaction as a root span', () => {
      const {exporter, adapter} = makeAdapter();
      startSession(adapter);
      adapter.onEvent({
        type: 'session.compacted',
        properties: {sessionID: TEST_SESSION.id},
      });

      const compact = exporter
        .getFinishedSpans()
        .find(s => s.name === 'opencode.compaction')!;
      expect(compact).toBeDefined();
      expect(compact.parentSpanId).toBeUndefined();
      expect(compact.attributes['gen_ai.conversation.id']).toBe(
        'test-session-id'
      );
    });
  });

  // ── session status transitions ────────────────────────────────────────────

  describe('session status transitions', () => {
    it('starts invoke_agent span on session.status running', () => {
      const {exporter, adapter} = makeAdapter();
      startSession(adapter);

      adapter.onEvent({
        type: 'session.status',
        properties: {sessionID: TEST_SESSION.id, status: 'running'},
      });
      expect(adapter.isActive).toBe(true);

      adapter.endInvokeAgentSpan();

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent opencode');
      expect(invoke).toBeDefined();
    });

    it('does not start duplicate invoke_agent on redundant running status', () => {
      const {exporter, adapter} = makeAdapter();
      startInvoke(adapter);

      // Redundant running status should not create a new span
      adapter.onEvent({
        type: 'session.status',
        properties: {sessionID: TEST_SESSION.id, status: 'running'},
      });
      adapter.endInvokeAgentSpan();

      const invokes = exporter
        .getFinishedSpans()
        .filter(s => s.name === 'invoke_agent opencode');
      expect(invokes).toHaveLength(1);
    });
  });

  // ── provider name mapping ─────────────────────────────────────────────────

  describe('provider name mapping', () => {
    const testCases: Array<[string, string]> = [
      ['anthropic', 'anthropic'],
      ['openai', 'openai'],
      ['google', 'gcp.gemini'],
      ['google-genai', 'gcp.gemini'],
      ['azure', 'azure.ai.openai'],
      ['mistral', 'mistral_ai'],
      ['groq', 'groq'],
      ['bedrock', 'aws.bedrock'],
    ];

    test.each(testCases)('maps %s to %s', (providerID, expected) => {
      const {exporter, adapter} = makeAdapter();
      adapter.onEvent({
        type: 'session.created',
        properties: {
          ...TEST_SESSION,
          providerID,
        } as any,
      });
      adapter.onEvent({
        type: 'message.updated',
        properties: {
          id: `msg-${providerID}`,
          role: 'user',
          sessionID: TEST_SESSION.id,
          createdAt: new Date().toISOString(),
        },
      });
      adapter.endInvokeAgentSpan();

      const invoke = exporter
        .getFinishedSpans()
        .find(s => s.name === 'invoke_agent opencode')!;
      expect(invoke.attributes['gen_ai.provider.name']).toBe(expected);
    });
  });
});
