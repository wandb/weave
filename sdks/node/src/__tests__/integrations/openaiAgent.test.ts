import {InMemoryTraceServer} from '../../inMemoryTraceServer';
import {createOpenAIAgentsTracingProcessor} from '../../integrations/openai.agent';
import {initWithCustomTraceServer} from '../clientMock';

describe('OpenAI Agents Integration', () => {
  let inMemoryTraceServer: InMemoryTraceServer;
  const testProjectName = 'test-project';

  beforeEach(() => {
    inMemoryTraceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(testProjectName, inMemoryTraceServer);
  });

  test('trace lifecycle creates and finishes call', async () => {
    const processor = createOpenAIAgentsTracingProcessor();
    const trace = {
      type: 'trace' as const,
      traceId: 'test-trace-123',
      name: 'Agent Workflow',
      groupId: null,
      metadata: {},
    };

    await processor.onTraceStart(trace);
    await processor.onTraceEnd(trace);

    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toBe('openai_agent_trace');
    expect(calls[0].display_name).toBe('Agent Workflow');
    expect(calls[0].attributes).toMatchObject({
      kind: 'agent',
      agent_trace_id: 'test-trace-123',
    });
    expect(calls[0].ended_at).not.toBeNull();
  });

  test('maps span types to correct kinds', async () => {
    const processor = createOpenAIAgentsTracingProcessor();

    await processor.onTraceStart({
      type: 'trace',
      traceId: 'test-trace',
      name: 'Test',
      groupId: null,
    });

    // Test key span types
    const spans = [
      {id: 'span-agent', type: 'agent', expectedKind: 'agent'},
      {id: 'span-function', type: 'function', expectedKind: 'tool'},
      {id: 'span-guardrail', type: 'guardrail', expectedKind: 'guardrail'},
    ];

    for (const {id, type} of spans) {
      await processor.onSpanStart({
        type: 'trace.span',
        traceId: 'test-trace',
        spanId: id,
        parentId: null,
        spanData: {type, name: `test-${type}`} as any,
        startedAt: null,
        endedAt: null,
        error: null,
      });
    }

    const calls = await inMemoryTraceServer.getCalls(testProjectName);

    for (const {id, expectedKind} of spans) {
      const call = calls.find(c => c.attributes?.agent_span_id === id);
      expect(call?.attributes?.kind).toBe(expectedKind);
    }
  });

  test('creates parent-child hierarchy', async () => {
    const processor = createOpenAIAgentsTracingProcessor();

    await processor.onTraceStart({
      type: 'trace',
      traceId: 'trace-123',
      name: 'Workflow',
      groupId: null,
    });

    await processor.onSpanStart({
      type: 'trace.span',
      traceId: 'trace-123',
      spanId: 'span-123',
      parentId: null,
      spanData: {type: 'agent', name: 'Agent'} as any,
      startedAt: null,
      endedAt: null,
      error: null,
    });

    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    expect(calls).toHaveLength(2);

    const traceCall = calls.find(c => c.op_name === 'openai_agent_trace');
    const spanCall = calls.find(
      c => c.attributes?.agent_span_id === 'span-123'
    );

    expect(spanCall!.parent_id).toBe(traceCall!.id);
    expect(spanCall!.trace_id).toBe(traceCall!.trace_id);
  });
});
