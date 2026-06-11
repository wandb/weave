import type {ReadableSpan} from '@opentelemetry/sdk-trace-base';

import {ATTR_GEN_AI_AGENT_NAME} from '../../genai/semconv';
import type {SpanBase} from '../../genai/spanBase';
import {Turn} from '../../genai/turn';

import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

/**
 * Parametrized coverage for the shared `SpanBase` mutators
 * (`setAttribute` / `setAttributes` / `addEvent`) across all four span
 * wrappers. Mirrors the Python SDK's `test_span_attributes.py`, which runs the
 * same assertions over `(Tool, LLM, SubAgent, Turn)`.
 */
interface SpanCase {
  label: string;
  start: () => {
    target: SpanBase;
    endAll: () => void;
    locate: (spans: ReadableSpan[]) => ReadableSpan;
  };
}

const CASES: SpanCase[] = [
  {
    label: 'Turn',
    start: () => {
      const turn = Turn.create({});
      return {
        target: turn,
        endAll: () => turn.end(),
        locate: spans => findSpan(spans, 'invoke_agent'),
      };
    },
  },
  {
    label: 'LLM',
    start: () => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o'});
      return {
        target: llm,
        endAll: () => {
          llm.end();
          turn.end();
        },
        locate: spans => findSpan(spans, 'chat'),
      };
    },
  },
  {
    label: 'Tool',
    start: () => {
      const turn = Turn.create({});
      const tool = turn.startTool({name: 'get_weather'});
      return {
        target: tool,
        endAll: () => {
          tool.end();
          turn.end();
        },
        locate: spans => findSpan(spans, 'execute_tool'),
      };
    },
  },
  {
    label: 'SubAgent',
    start: () => {
      const turn = Turn.create({agentName: 'parent'});
      const sub = turn.startSubagent({name: 'child-bot'});
      return {
        target: sub,
        endAll: () => {
          sub.end();
          turn.end();
        },
        locate: spans => {
          const found = spans.find(
            s =>
              s.name === 'invoke_agent' &&
              s.attributes[ATTR_GEN_AI_AGENT_NAME] === 'child-bot'
          );
          if (!found) {
            throw new Error('no child-bot invoke_agent span found');
          }
          return found;
        },
      };
    },
  },
];

describe.each(CASES)('SpanBase mutators on $label', ({start}) => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('setAttribute writes a single attribute to the span', () => {
    const {target, endAll, locate} = start();
    target.setAttribute('weave.cost.usd', 0.42);
    endAll();
    expect(
      locate(getExporter().getFinishedSpans()).attributes['weave.cost.usd']
    ).toBe(0.42);
  });

  it('setAttribute returns this for chaining', () => {
    const {target, endAll} = start();
    expect(target.setAttribute('k', 'v')).toBe(target);
    endAll();
  });

  it('setAttribute is a no-op after end()', () => {
    const {target, endAll, locate} = start();
    endAll();
    target.setAttribute('after.end', 'x');
    expect(
      locate(getExporter().getFinishedSpans()).attributes['after.end']
    ).toBeUndefined();
  });

  it('setAttributes writes multiple attributes at once', () => {
    const {target, endAll, locate} = start();
    target.setAttributes({'weave.tag': 'prod', 'weave.run': 7});
    endAll();
    const attrs = locate(getExporter().getFinishedSpans()).attributes;
    expect(attrs['weave.tag']).toBe('prod');
    expect(attrs['weave.run']).toBe(7);
  });

  it('setAttributes is a no-op after end()', () => {
    const {target, endAll, locate} = start();
    endAll();
    target.setAttributes({'after.end': 'x'});
    expect(
      locate(getExporter().getFinishedSpans()).attributes['after.end']
    ).toBeUndefined();
  });

  it('addEvent writes a named event with attributes', () => {
    const {target, endAll, locate} = start();
    target.addEvent('context_compacted', {items_before: 50, items_after: 10});
    endAll();
    const ev = locate(getExporter().getFinishedSpans()).events.find(
      e => e.name === 'context_compacted'
    );
    expect(ev?.attributes).toMatchObject({items_before: 50, items_after: 10});
  });

  it('addEvent returns this for chaining', () => {
    const {target, endAll} = start();
    expect(target.addEvent('e')).toBe(target);
    endAll();
  });

  it('addEvent is a no-op after end()', () => {
    const {target, endAll, locate} = start();
    endAll();
    target.addEvent('after.end');
    expect(
      locate(getExporter().getFinishedSpans()).events.find(
        e => e.name === 'after.end'
      )
    ).toBeUndefined();
  });
});
