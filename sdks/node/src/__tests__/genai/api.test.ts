import {
  endLLM,
  endSession,
  endTurn,
  startLLM,
  startSession,
  startSubagent,
  startTool,
  startTurn,
} from '../../genai/api';
import {
  getCurrentLLM,
  getCurrentSession,
  getCurrentTurn,
  runIsolated,
} from '../../genai/context';
import {ATTR_GEN_AI_CONVERSATION_ID} from '../../genai/semconv';

import {
  expectSpanTimesToMatch,
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

describe('genai api (top-level functions)', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  // -------------------------------------------------------------------------
  // Happy path
  // -------------------------------------------------------------------------

  it('startSession → startTurn → startLLM → startTool wires up the full chain', () => {
    const session = startSession({
      agentName: 'weather-bot',
      sessionId: 'conv-1',
    });
    const turn = startTurn({});
    const llm = startLLM({model: 'gpt-4o'});
    const tool = startTool({name: 'get_weather'});
    tool.end();
    llm.end();
    turn.end();
    session.end();

    const spans = getExporter().getFinishedSpans();
    expect(spans).toHaveLength(3);
    const turnSpan = findSpan(spans, 'invoke_agent');
    const llmSpan = findSpan(spans, 'chat');
    const toolSpan = findSpan(spans, 'execute_tool');
    expect(llmSpan.parentSpanId).toBe(turnSpan.spanContext().spanId);
    expect(toolSpan.parentSpanId).toBe(llmSpan.spanContext().spanId);
    for (const s of spans) {
      expect(s.attributes[ATTR_GEN_AI_CONVERSATION_ID]).toBe('conv-1');
    }
  });

  // -------------------------------------------------------------------------
  // getCurrent* accessors
  // -------------------------------------------------------------------------

  it('getCurrentSession / Turn / LLM reflect the active instances', () => {
    expect(getCurrentSession()).toBeUndefined();
    expect(getCurrentTurn()).toBeUndefined();
    expect(getCurrentLLM()).toBeUndefined();

    const session = startSession({});
    expect(getCurrentSession()).toBe(session);

    const turn = startTurn({});
    expect(getCurrentTurn()).toBe(turn);
    expect(getCurrentSession()).toBe(session);

    const llm = startLLM({model: 'gpt-4o'});
    expect(getCurrentLLM()).toBe(llm);

    llm.end();
    expect(getCurrentLLM()).toBeUndefined();
    turn.end();
    expect(getCurrentTurn()).toBeUndefined();
    session.end();
    expect(getCurrentSession()).toBeUndefined();
  });

  // -------------------------------------------------------------------------
  // Tool / SubAgent parent resolution
  // -------------------------------------------------------------------------

  it('startTool with an active LLM nests the Tool under the LLM', () => {
    const turn = startTurn({});
    const llm = startLLM({model: 'gpt-4o'});
    const tool = startTool({name: 'get_weather'});
    tool.end();
    llm.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    const toolSpan = findSpan(spans, 'execute_tool');
    const llmSpan = findSpan(spans, 'chat');
    expect(toolSpan.parentSpanId).toBe(llmSpan.spanContext().spanId);
  });

  it('startTool without an active LLM places the Tool as a sibling under Turn', () => {
    const turn = startTurn({});
    const tool = startTool({name: 'get_weather'});
    tool.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    const toolSpan = findSpan(spans, 'execute_tool');
    const turnSpan = findSpan(spans, 'invoke_agent');
    expect(toolSpan.parentSpanId).toBe(turnSpan.spanContext().spanId);
  });

  // -------------------------------------------------------------------------
  // Error paths
  // -------------------------------------------------------------------------

  it('startLLM throws when no Turn is active', () => {
    expect(() => startLLM({model: 'gpt-4o'})).toThrow(/active Turn/);
  });

  it('startTool throws when no Turn or LLM is active', () => {
    expect(() => startTool({name: 'foo'})).toThrow(/active Turn or LLM/);
  });

  it('startSubagent throws when no Turn or LLM is active', () => {
    expect(() => startSubagent({name: 'foo'})).toThrow(/active Turn or LLM/);
  });

  it('starting a Session / Turn / LLM while one is already active throws', () => {
    startSession({});
    expect(() => startSession({})).toThrow(/Session is already active/);

    startTurn({});
    expect(() => startTurn({})).toThrow(/Turn is already active/);

    startLLM({model: 'gpt-4o'});
    expect(() => startLLM({model: 'gpt-4o'})).toThrow(/LLM is already active/);
  });

  // -------------------------------------------------------------------------
  // runIsolated — isolation for parallel work
  // -------------------------------------------------------------------------

  it('runIsolated isolates concurrent Sessions in Promise.all', async () => {
    const sessionIds: string[] = [];
    await Promise.all([
      runIsolated(async () => {
        const s = startSession({sessionId: 'parallel-a'});
        await new Promise(r => setTimeout(r, 5));
        sessionIds.push(getCurrentSession()!.sessionId);
        s.end();
      }),
      runIsolated(async () => {
        const s = startSession({sessionId: 'parallel-b'});
        await new Promise(r => setTimeout(r, 5));
        sessionIds.push(getCurrentSession()!.sessionId);
        s.end();
      }),
    ]);
    expect(sessionIds.sort()).toEqual(['parallel-a', 'parallel-b']);
    // Neither leaks to the outer chain.
    expect(getCurrentSession()).toBeUndefined();
  });

  it('runIsolated supports a full Session → Turn → LLM stack per frame', async () => {
    const results = await Promise.all([
      runIsolated(async () => {
        const s = startSession({sessionId: 'chain-a'});
        const t = startTurn({});
        const l = startLLM({model: 'gpt-4o'});
        await new Promise(r => setTimeout(r, 5));
        const snapshot = {
          session: getCurrentSession()!.sessionId,
          turn: getCurrentTurn() === t,
          llm: getCurrentLLM() === l,
        };
        l.end();
        t.end();
        s.end();
        return snapshot;
      }),
      runIsolated(async () => {
        const s = startSession({sessionId: 'chain-b'});
        const t = startTurn({});
        const l = startLLM({model: 'gpt-4o'});
        await new Promise(r => setTimeout(r, 5));
        const snapshot = {
          session: getCurrentSession()!.sessionId,
          turn: getCurrentTurn() === t,
          llm: getCurrentLLM() === l,
        };
        l.end();
        t.end();
        s.end();
        return snapshot;
      }),
    ]);
    expect(results).toEqual([
      {session: 'chain-a', turn: true, llm: true},
      {session: 'chain-b', turn: true, llm: true},
    ]);
  });

  it('parallel sessions WITHOUT runIsolated clash on the default state and throw', async () => {
    // Without runIsolated, both async branches mutate the same default state
    // object. One installs its session; the other sees state.session != null
    // and the nesting guard throws.
    const results = await Promise.allSettled([
      (async () => {
        const s = startSession({sessionId: 'shared-a'});
        await new Promise(r => setTimeout(r, 5));
        s.end();
      })(),
      (async () => {
        await new Promise(r => setTimeout(r, 1));
        // By now the first branch has installed its session on the default
        // state. This call hits the nesting guard.
        startSession({sessionId: 'shared-b'});
      })(),
    ]);
    expect(results[0].status).toBe('fulfilled');
    expect(results[1].status).toBe('rejected');
    if (results[1].status === 'rejected') {
      expect(String(results[1].reason)).toMatch(/Session is already active/);
    }
  });

  // -------------------------------------------------------------------------
  // end* are idempotent no-ops when no instance is active
  // -------------------------------------------------------------------------

  it('endSession / endTurn / endLLM are no-ops when nothing is active', () => {
    expect(() => endSession()).not.toThrow();
    expect(() => endTurn()).not.toThrow();
    expect(() => endLLM()).not.toThrow();
  });

  it('endLLM / endTurn / endSession clear their current instances', () => {
    const session = startSession({});
    const turn = startTurn({});
    startLLM({model: 'gpt-4o'});

    endLLM();
    expect(getCurrentLLM()).toBeUndefined();
    expect(getCurrentTurn()).toBe(turn);
    expect(getCurrentSession()).toBe(session);

    endTurn();
    expect(getCurrentTurn()).toBeUndefined();
    expect(getCurrentSession()).toBe(session);

    endSession();
    expect(getCurrentSession()).toBeUndefined();
    // Turn + LLM each emit a span on end; Session does not emit its own.
    expect(getExporter().getFinishedSpans()).toHaveLength(2);
  });

  it('endSession cascades — ends any active LLM and Turn before clearing Session', () => {
    startSession({});
    startTurn({});
    startLLM({model: 'gpt-4o'});

    endSession();

    expect(getCurrentSession()).toBeUndefined();
    expect(getCurrentTurn()).toBeUndefined();
    expect(getCurrentLLM()).toBeUndefined();
    // Turn + LLM spans were closed by the cascade.
    expect(getExporter().getFinishedSpans()).toHaveLength(2);
  });

  it('endSession passes options when implicitly ending LLM and Turn', () => {
    const startedAt = new Date('2026-05-29T10:00:00.000Z');
    const endedAt = new Date('2026-05-29T10:00:01.700Z');

    startSession({});
    startTurn({startTime: startedAt});
    startLLM({model: 'gpt-4o', startTime: startedAt});

    endSession({endTime: endedAt});

    const spans = getExporter().getFinishedSpans();
    const turnSpan = findSpan(spans, 'invoke_agent');
    const llmSpan = findSpan(spans, 'chat');
    expectSpanTimesToMatch(turnSpan, startedAt, endedAt);
    expectSpanTimesToMatch(llmSpan, startedAt, endedAt);
  });

  it('startTurn and endTurn respect given times', () => {
    const startedAt = new Date('2026-05-29T10:00:00.000Z');
    const endedAt = new Date('2026-05-29T10:00:01.700Z');

    startTurn({startTime: startedAt});
    endTurn({endTime: endedAt});

    const turnSpan = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expectSpanTimesToMatch(turnSpan, startedAt, endedAt);
  });

  it('startLLM and endLLM respect given times', () => {
    const startedAt = new Date('2026-05-29T10:00:00.000Z');
    const endedAt = new Date('2026-05-29T10:00:00.800Z');

    startTurn({});
    startLLM({model: 'gpt-4o', startTime: startedAt});
    endLLM({endTime: endedAt});

    const llmSpan = findSpan(getExporter().getFinishedSpans(), 'chat');
    expectSpanTimesToMatch(llmSpan, startedAt, endedAt);
  });
});
