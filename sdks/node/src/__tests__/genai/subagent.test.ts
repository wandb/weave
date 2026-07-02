import type {ReadableSpan} from '@opentelemetry/sdk-trace-base';

import {ATTR_GEN_AI_AGENT_NAME} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {
  expectSpanTimesToMatch,
  setupExporterPerTest,
  setupGenAITestEnvironment,
  spanSnapshot,
} from './common';

describe('SubAgent', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('emits a nested invoke_agent span as a child of the turn', () => {
    const turn = Turn.create({agentName: 'parent'});
    const sub = turn.startSubagent({
      name: 'child-bot',
      model: 'gpt-4o',
      systemInstructions: ['Be helpful', 'Be concise'],
    });
    sub.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    // Two spans, both named 'invoke_agent'. Differentiate by agent name.
    const subSpan = spans.find(
      s =>
        s.name === 'invoke_agent' &&
        s.attributes[ATTR_GEN_AI_AGENT_NAME] === 'child-bot'
    );
    const parentTurnSpan = spans.find(
      s =>
        s.name === 'invoke_agent' &&
        s.attributes[ATTR_GEN_AI_AGENT_NAME] === 'parent'
    );
    expect(subSpan).toBeDefined();
    expect(parentTurnSpan).toBeDefined();
    expect(subSpan!.parentSpanId).toBe(parentTurnSpan!.spanContext().spanId);

    expect(spanSnapshot(subSpan!)).toMatchInlineSnapshot(`
      {
        "attributes": {
          "gen_ai.agent.name": "child-bot",
          "gen_ai.operation.name": "invoke_agent",
          "gen_ai.request.model": "gpt-4o",
          "gen_ai.system_instructions": "[{"type":"text","content":"Be helpful"},{"type":"text","content":"Be concise"}]",
        },
        "endTime": "<timestamp>",
        "startTime": "<timestamp>",
      }
    `);
  });

  const findSub = (spans: ReadableSpan[]) => {
    const found = spans.find(
      s =>
        s.name === 'invoke_agent' &&
        s.attributes[ATTR_GEN_AI_AGENT_NAME] === 'researcher'
    );
    if (!found) throw new Error('no researcher invoke_agent span found');
    return found;
  };

  it('setAttributes records attributes on the subagent span; warns + no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const turn = Turn.create({});
    const sub = turn.startSubagent({name: 'researcher'});
    sub.setAttributes({
      'weave.claude_code.display_name': 'Agent: research-bot',
      'weave.tag': 'enterprise',
    });
    sub.end();
    sub.setAttributes({'after.end': 'x'});
    turn.end();

    const subSpan = findSub(getExporter().getFinishedSpans());
    expect(subSpan.attributes['weave.claude_code.display_name']).toBe(
      'Agent: research-bot'
    );
    expect(subSpan.attributes['weave.tag']).toBe('enterprise');
    expect(subSpan.attributes['after.end']).toBeUndefined();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('SubAgent.setAttributes() called after end()')
    );
    warnSpy.mockRestore();
  });

  it('addEvent records a span event on the subagent span; warns + no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const turn = Turn.create({});
    const sub = turn.startSubagent({name: 'researcher'});
    sub.addEvent('weave.lifecycle', {state: 'spawned'});
    sub.end();
    sub.addEvent('after.end');
    turn.end();

    const subSpan = findSub(getExporter().getFinishedSpans());
    expect(subSpan.events).toHaveLength(1);
    expect(subSpan.events[0].name).toBe('weave.lifecycle');
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('SubAgent.addEvent() called after end()')
    );
    warnSpy.mockRestore();
  });

  it('record() updates fields, which are emitted at end()', () => {
    const turn = Turn.create({});
    const sub = turn.startSubagent({name: 'researcher'});
    sub.record({
      agentId: 'agent-9',
      agentDescription: 'A research bot',
      agentVersion: 'v4',
      systemInstructions: ['Find authoritative sources'],
    });
    sub.end();
    turn.end();

    const span = findSub(getExporter().getFinishedSpans());
    expect(spanSnapshot(span)).toMatchInlineSnapshot(`
      {
        "attributes": {
          "gen_ai.agent.description": "A research bot",
          "gen_ai.agent.id": "agent-9",
          "gen_ai.agent.name": "researcher",
          "gen_ai.agent.version": "v4",
          "gen_ai.operation.name": "invoke_agent",
          "gen_ai.system_instructions": "[{"type":"text","content":"Find authoritative sources"}]",
        },
        "endTime": "<timestamp>",
        "startTime": "<timestamp>",
      }
    `);
  });

  it('record() preserves untouched values', () => {
    const turn = Turn.create({});
    const sub = turn.startSubagent({
      name: 'researcher',
      agentId: 'preset',
      agentVersion: 'v1',
      systemInstructions: ['initial'],
    });
    sub.record({agentVersion: 'v2'});
    sub.end();
    turn.end();

    const span = findSub(getExporter().getFinishedSpans());
    expect(spanSnapshot(span)).toMatchInlineSnapshot(`
      {
        "attributes": {
          "gen_ai.agent.id": "preset",
          "gen_ai.agent.name": "researcher",
          "gen_ai.agent.version": "v2",
          "gen_ai.operation.name": "invoke_agent",
          "gen_ai.system_instructions": "[{"type":"text","content":"initial"}]",
        },
        "endTime": "<timestamp>",
        "startTime": "<timestamp>",
      }
    `);
  });

  it('record() is chainable', () => {
    const turn = Turn.create({});
    const sub = turn.startSubagent({name: 'researcher'});
    expect(sub.record({agentId: 'x'}).record({agentDescription: 'foo'})).toBe(
      sub
    );
    sub.end();
    turn.end();
  });

  it('record() warns and is a no-op after end()', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    const turn = Turn.create({});
    const sub = turn.startSubagent({name: 'researcher'});
    sub.end();
    sub.record({agentId: 'after-end'});
    turn.end();

    const subSpan = findSub(getExporter().getFinishedSpans());
    expect(subSpan.attributes['gen_ai.agent.id']).toBeUndefined();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('SubAgent.record() called after end()')
    );
    warnSpy.mockRestore();
  });

  it('startTime/endTime backdate the invoke_agent span window', () => {
    const startedAt = new Date('2026-01-01T00:00:00Z');
    const endedAt = new Date('2026-01-01T00:00:05Z');
    const turn = Turn.create({});
    const sub = turn.startSubagent({name: 'researcher', startTime: startedAt});
    sub.end({endTime: endedAt});
    turn.end();

    expectSpanTimesToMatch(
      findSub(getExporter().getFinishedSpans()),
      startedAt,
      endedAt
    );
  });

  it('nests child LLM and Tool spans under the subagent span', () => {
    const turn = Turn.create({agentName: 'parent'});
    const sub = turn.startSubagent({name: 'researcher', model: 'gpt-4o'});
    sub.startLLM({model: 'gpt-4o', providerName: 'openai'}).end();
    sub.startTool({name: 'search'}).end();
    sub.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    const subSpan = findSub(spans);
    const chatSpan = spans.find(s => s.name === 'chat');
    const toolSpan = spans.find(s => s.name === 'execute_tool');
    expect(chatSpan).toBeDefined();
    expect(toolSpan).toBeDefined();
    // Both children parent to the sub-agent, not the enclosing Turn.
    expect(chatSpan!.parentSpanId).toBe(subSpan.spanContext().spanId);
    expect(toolSpan!.parentSpanId).toBe(subSpan.spanContext().spanId);
  });

  it('nests a child SubAgent (and its descendants) under the parent subagent', () => {
    const turn = Turn.create({agentName: 'parent'});
    const outer = turn.startSubagent({name: 'outer'});
    const inner = outer.startSubagent({name: 'inner', model: 'gpt-4o'});
    inner.startLLM({model: 'gpt-4o', providerName: 'openai'}).end();
    inner.end();
    outer.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    const bySubName = (name: string) => {
      const found = spans.find(
        s =>
          s.name === 'invoke_agent' &&
          s.attributes[ATTR_GEN_AI_AGENT_NAME] === name
      );
      if (!found) throw new Error(`no invoke_agent span for ${name}`);
      return found;
    };
    const turnSpan = bySubName('parent');
    const outerSpan = bySubName('outer');
    const innerSpan = bySubName('inner');
    const chatSpan = spans.find(s => s.name === 'chat');
    expect(chatSpan).toBeDefined();
    // Full chain: turn -> outer -> inner -> chat. The nested SubAgent parents
    // to the outer sub (not the Turn), and threads its own context down to the
    // LLM it starts.
    expect(outerSpan.parentSpanId).toBe(turnSpan.spanContext().spanId);
    expect(innerSpan.parentSpanId).toBe(outerSpan.spanContext().spanId);
    expect(chatSpan!.parentSpanId).toBe(innerSpan.spanContext().spanId);
  });

  it('binds children eagerly, not via ambient context: a child created after the SubAgent (and Turn) end still nests under it', () => {
    // The TS analog of the Python out-of-block bug. In Python the child span is
    // created lazily (at `with child:`) from whatever ambient OTel context is
    // current, so it detaches once the parent's context is popped. TS binds the
    // parent context eagerly inside start*(), so the parent link holds even if
    // the child span is created after the SubAgent and Turn have already ended.
    // This guards against a regression to active/ambient-context parenting.
    const turn = Turn.create({agentName: 'parent'});
    const sub = turn.startSubagent({name: 'researcher', model: 'gpt-4o'});
    sub.end();
    turn.end();
    // Children created AFTER both parents have ended.
    sub.startLLM({model: 'gpt-4o', providerName: 'openai'}).end();
    sub.startTool({name: 'search'}).end();

    const spans = getExporter().getFinishedSpans();
    const subSpan = findSub(spans);
    const chatSpan = spans.find(s => s.name === 'chat');
    const toolSpan = spans.find(s => s.name === 'execute_tool');
    expect(chatSpan).toBeDefined();
    expect(toolSpan).toBeDefined();
    expect(chatSpan!.parentSpanId).toBe(subSpan.spanContext().spanId);
    expect(toolSpan!.parentSpanId).toBe(subSpan.spanContext().spanId);
  });
});
