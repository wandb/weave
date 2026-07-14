import {
  endConversation,
  endLLM,
  endTurn,
  startConversation,
  startLLM,
  startSubagent,
  startTool,
  startTurn,

  /* @deprecated */
  endSession,
  startSession,
} from '../../genai/api';
import {
  getCurrentConversation,
  getCurrentLLM,
  getCurrentTurn,
  runIsolated,

  /* @deprecated */
  getCurrentSession,
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

  it('deprecated `startSession` is an alias for `startConversation`', () => {
    expect(startSession).toBe(startConversation);
    const conversation = startSession({sessionId: 'aliased'});
    expect(getCurrentConversation()).toBe(conversation);
    conversation.end();
  });

  it('deprecated `getCurrentSession` is an alias for `getCurrentConversation`', () => {
    expect(getCurrentSession).toBe(getCurrentConversation);
    expect(getCurrentSession()).toBeUndefined();
    const conversation = startConversation({sessionId: 'gcs-alias'});
    expect(getCurrentSession()).toBe(conversation);
    conversation.end();
  });

  it('deprecated `endSession` is an alias for `endConversation`', () => {
    expect(endSession).toBe(endConversation);
    const conversation = startConversation({sessionId: 'es-alias'});
    expect(getCurrentConversation()).toBe(conversation);
    endSession();
    expect(getCurrentConversation()).toBeUndefined();
  });

  it('startConversation → startTurn → startLLM → startTool wires up the full chain', () => {
    const conversation = startConversation({
      agentName: 'weather-bot',
      conversationId: 'conv-1',
    });
    const turn = startTurn({});
    const llm = startLLM({model: 'gpt-4o'});
    const tool = startTool({name: 'get_weather'});
    tool.end();
    llm.end();
    turn.end();
    conversation.end();

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

  it('getCurrentConversation / Turn / LLM reflect the active instances', () => {
    expect(getCurrentConversation()).toBeUndefined();
    expect(getCurrentTurn()).toBeUndefined();
    expect(getCurrentLLM()).toBeUndefined();

    const conversation = startConversation({});
    expect(getCurrentConversation()).toBe(conversation);

    const turn = startTurn({});
    expect(getCurrentTurn()).toBe(turn);
    expect(getCurrentConversation()).toBe(conversation);

    const llm = startLLM({model: 'gpt-4o'});
    expect(getCurrentLLM()).toBe(llm);

    llm.end();
    expect(getCurrentLLM()).toBeUndefined();
    turn.end();
    expect(getCurrentTurn()).toBeUndefined();
    conversation.end();
    expect(getCurrentConversation()).toBeUndefined();
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

  it('starting a Conversation / Turn / LLM while one is already active throws', () => {
    startConversation({});
    expect(() => startConversation({})).toThrow(
      /Conversation is already active/
    );

    startTurn({});
    expect(() => startTurn({})).toThrow(/Turn is already active/);

    startLLM({model: 'gpt-4o'});
    expect(() => startLLM({model: 'gpt-4o'})).toThrow(/LLM is already active/);
  });

  // -------------------------------------------------------------------------
  // runIsolated — isolation for parallel work
  // -------------------------------------------------------------------------

  it('runIsolated isolates concurrent Conversations in Promise.all', async () => {
    const conversationIds: string[] = [];
    await Promise.all([
      runIsolated(async () => {
        const s = startConversation({conversationId: 'parallel-a'});
        await new Promise(r => setTimeout(r, 5));
        conversationIds.push(getCurrentConversation()!.conversationId);
        s.end();
      }),
      runIsolated(async () => {
        const s = startConversation({conversationId: 'parallel-b'});
        await new Promise(r => setTimeout(r, 5));
        conversationIds.push(getCurrentConversation()!.conversationId);
        s.end();
      }),
    ]);
    expect(conversationIds.sort()).toEqual(['parallel-a', 'parallel-b']);
    // Neither leaks to the outer chain.
    expect(getCurrentConversation()).toBeUndefined();
  });

  it('runIsolated supports a full Conversation → Turn → LLM stack per frame', async () => {
    const results = await Promise.all([
      runIsolated(async () => {
        const s = startConversation({conversationId: 'chain-a'});
        const t = startTurn({});
        const l = startLLM({model: 'gpt-4o'});
        await new Promise(r => setTimeout(r, 5));
        const snapshot = {
          conversation: getCurrentConversation()!.conversationId,
          turn: getCurrentTurn() === t,
          llm: getCurrentLLM() === l,
        };
        l.end();
        t.end();
        s.end();
        return snapshot;
      }),
      runIsolated(async () => {
        const s = startConversation({conversationId: 'chain-b'});
        const t = startTurn({});
        const l = startLLM({model: 'gpt-4o'});
        await new Promise(r => setTimeout(r, 5));
        const snapshot = {
          conversation: getCurrentConversation()!.conversationId,
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
      {conversation: 'chain-a', turn: true, llm: true},
      {conversation: 'chain-b', turn: true, llm: true},
    ]);
  });

  it('parallel conversations WITHOUT runIsolated clash on the default state and throw', async () => {
    // Without runIsolated, both async branches mutate the same default state
    // object. One installs its conversation; the other sees state.conversation
    // != null and the nesting guard throws.
    const results = await Promise.allSettled([
      (async () => {
        const s = startConversation({conversationId: 'shared-a'});
        await new Promise(r => setTimeout(r, 5));
        s.end();
      })(),
      (async () => {
        await new Promise(r => setTimeout(r, 1));
        // By now the first branch has installed its conversation on the default
        // state. This call hits the nesting guard.
        startConversation({conversationId: 'shared-b'});
      })(),
    ]);
    expect(results[0].status).toBe('fulfilled');
    expect(results[1].status).toBe('rejected');
    if (results[1].status === 'rejected') {
      expect(String(results[1].reason)).toMatch(
        /Conversation is already active/
      );
    }
  });

  // -------------------------------------------------------------------------
  // end* are idempotent no-ops when no instance is active
  // -------------------------------------------------------------------------

  it('endConversation / endTurn / endLLM are no-ops when nothing is active', () => {
    expect(() => endConversation()).not.toThrow();
    expect(() => endTurn()).not.toThrow();
    expect(() => endLLM()).not.toThrow();
  });

  it('endLLM / endTurn / endConversation clear their current instances', () => {
    const conversation = startConversation({});
    const turn = startTurn({});
    startLLM({model: 'gpt-4o'});

    endLLM();
    expect(getCurrentLLM()).toBeUndefined();
    expect(getCurrentTurn()).toBe(turn);
    expect(getCurrentConversation()).toBe(conversation);

    endTurn();
    expect(getCurrentTurn()).toBeUndefined();
    expect(getCurrentConversation()).toBe(conversation);

    endConversation();
    expect(getCurrentConversation()).toBeUndefined();
    // Turn + LLM each emit a span on end; Conversation does not emit its own.
    expect(getExporter().getFinishedSpans()).toHaveLength(2);
  });

  it('endConversation cascades — ends any active LLM and Turn before clearing Conversation', () => {
    startConversation({});
    startTurn({});
    startLLM({model: 'gpt-4o'});

    endConversation();

    expect(getCurrentConversation()).toBeUndefined();
    expect(getCurrentTurn()).toBeUndefined();
    expect(getCurrentLLM()).toBeUndefined();
    // Turn + LLM spans were closed by the cascade.
    expect(getExporter().getFinishedSpans()).toHaveLength(2);
  });

  it('endConversation passes options when implicitly ending LLM and Turn', () => {
    const startedAt = new Date('2026-05-29T10:00:00.000Z');
    const endedAt = new Date('2026-05-29T10:00:01.700Z');

    startConversation({});
    startTurn({startTime: startedAt});
    startLLM({model: 'gpt-4o', startTime: startedAt});

    endConversation({endTime: endedAt});

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

  test('startConversation stamps custom attributes on every emitted span', () => {
    startConversation({
      attributes: {
        'weave.integration.name': 'wb-agent',
        'weave.custom.run_id': 42,
      },
    });
    startTurn({});
    startLLM({model: 'gpt-4o'});
    const tool = startTool({name: 'get_weather'});
    tool.end();
    endLLM();
    endConversation();

    const spans = getExporter().getFinishedSpans();
    expect(spans.map(s => s.name).sort()).toEqual([
      'chat',
      'execute_tool',
      'invoke_agent',
    ]);
    for (const s of spans) {
      expect(s.attributes['weave.integration.name']).toBe('wb-agent');
      expect(s.attributes['weave.custom.run_id']).toBe(42);
    }
  });

  test('custom attributes do not override the emitter`s own semconv keys', () => {
    startConversation({
      attributes: {'gen_ai.operation.name': 'custom-loses'},
    });
    startTurn({});
    endTurn();
    endConversation();

    const turnSpan = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expect(turnSpan.attributes['gen_ai.operation.name']).toBe('invoke_agent');
  });

  test('conversation attributes reach spans created in a separate runIsolated frame', () => {
    // The conversation and its turn are created in one frame; a later, unrelated
    // frame reuses the turn handle. The attributes must still land on the child,
    // since the frame-B container has no ambient conversation.
    let turn!: ReturnType<typeof startTurn>;
    runIsolated(() => {
      const convo = startConversation({
        conversationId: 'session-x',
        attributes: {'weave.integration.name': 'claude-code', 'tenant.id': 'acme'},
      });
      turn = convo.startTurn({agentName: 'claude-code'});
    });
    runIsolated(() => {
      turn.startTool({name: 'read_file'}).end();
    });
    turn.end();

    const toolSpan = findSpan(getExporter().getFinishedSpans(), 'execute_tool');
    expect(toolSpan.attributes['weave.integration.name']).toBe('claude-code');
    expect(toolSpan.attributes['tenant.id']).toBe('acme');
  });

  test('per-turn attributes override conversation attributes on key collision', () => {
    const convo = startConversation({attributes: {env: 'prod', team: 'core'}});
    const turn = convo.startTurn({attributes: {env: 'staging'}});
    turn.end();
    convo.end();

    const turnSpan = findSpan(getExporter().getFinishedSpans(), 'invoke_agent');
    expect(turnSpan.attributes['env']).toBe('staging'); // per-turn wins
    expect(turnSpan.attributes['team']).toBe('core'); // conversation value kept
  });

  test('rootless startTurn attributes propagate to child spans', () => {
    const turn = startTurn({attributes: {'weave.integration.name': 'my-harness'}});
    turn.startTool({name: 'search'}).end();
    turn.end();

    const toolSpan = findSpan(getExporter().getFinishedSpans(), 'execute_tool');
    expect(toolSpan.attributes['weave.integration.name']).toBe('my-harness');
  });

  test('conversation attributes reach a tool nested under an LLM across frames', () => {
    // The claude-code daemon nests tool spans under the active chat (LLM) span,
    // opening the chat in one frame and its tools in later ones. The identity
    // must forward conversation -> turn -> llm -> tool, never read from ambient.
    let turn!: ReturnType<typeof startTurn>;
    let llm!: ReturnType<typeof startLLM>;
    runIsolated(() => {
      const convo = startConversation({
        conversationId: 'session-y',
        attributes: {'weave.integration.name': 'weave-claude-code'},
      });
      turn = convo.startTurn({agentName: 'claude-code'});
      llm = turn.startLLM({model: 'claude-opus-4'});
    });
    runIsolated(() => {
      llm.startTool({name: 'Bash'}).end();
    });
    llm.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    expect(findSpan(spans, 'chat').attributes['weave.integration.name']).toBe(
      'weave-claude-code'
    );
    expect(
      findSpan(spans, 'execute_tool').attributes['weave.integration.name']
    ).toBe('weave-claude-code');
  });

  test('conversation attributes reach a subagent and the tools nested under it', () => {
    // Both plugins spawn subagents, whose own tools nest under the subagent's
    // invoke_agent span. The identity must reach the subagent and forward on.
    let turn!: ReturnType<typeof startTurn>;
    let subagent!: ReturnType<typeof startSubagent>;
    runIsolated(() => {
      const convo = startConversation({
        conversationId: 'session-z',
        attributes: {'weave.integration.name': 'weave-openclaw'},
      });
      turn = convo.startTurn({agentName: 'openclaw'});
      subagent = turn.startSubagent({name: 'researcher'});
    });
    runIsolated(() => {
      subagent.startTool({name: 'search'}).end();
    });
    subagent.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    // Two invoke_agent spans (turn + subagent); pick the subagent's by its name.
    const subagentSpan = spans.find(
      s =>
        s.name === 'invoke_agent' &&
        s.attributes['gen_ai.agent.name'] === 'researcher'
    );
    expect(subagentSpan?.attributes['weave.integration.name']).toBe(
      'weave-openclaw'
    );
    expect(
      findSpan(spans, 'execute_tool').attributes['weave.integration.name']
    ).toBe('weave-openclaw');
  });
});
