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
} from '../../genai/context';
import {GEN_AI_ATTR} from '../../genai/semconv';

import {
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
      expect(s.attributes[GEN_AI_ATTR.GEN_AI_CONVERSATION_ID]).toBe('conv-1');
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
  // ALS restore-on-end with nested same-class instances
  // -------------------------------------------------------------------------

  it('ending the inner Turn restores the outer as current', () => {
    const outer = startTurn({agentName: 'outer'});
    const inner = startTurn({agentName: 'inner'});
    expect(getCurrentTurn()).toBe(inner);
    inner.end();
    expect(getCurrentTurn()).toBe(outer);
    outer.end();
    expect(getCurrentTurn()).toBeUndefined();
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

  // -------------------------------------------------------------------------
  // end* are idempotent no-ops when no instance is active
  // -------------------------------------------------------------------------

  it('endSession / endTurn / endLLM are no-ops when nothing is active', () => {
    expect(() => endSession()).not.toThrow();
    expect(() => endTurn()).not.toThrow();
    expect(() => endLLM()).not.toThrow();
  });

  it('endTurn ends the current Turn and restores prior ALS state', () => {
    const turn = startTurn({agentName: 'a'});
    expect(getCurrentTurn()).toBe(turn);
    endTurn();
    expect(getCurrentTurn()).toBeUndefined();
    expect(getExporter().getFinishedSpans()).toHaveLength(1);
  });
});
