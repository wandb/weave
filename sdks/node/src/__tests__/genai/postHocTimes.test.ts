import type {HrTime, TimeInput} from '@opentelemetry/api';
import type {ReadableSpan} from '@opentelemetry/sdk-trace-base';

import {ATTR_GEN_AI_AGENT_NAME} from '../../genai/semconv';
import {Turn} from '../../genai/turn';

import {
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from './common';

/**
 * Parametrized coverage for caller-set start/end times across all four span
 * wrappers. Mirrors the Python SDK's `test_post_hoc_times.py`: a backdated
 * `startTime` passed at creation and an `endTime` passed at `end()` must reach
 * the emitted OTel span verbatim; omitting them falls back to wall-clock now.
 */
const START: HrTime = [1700000000, 0]; // 2023-11-14, well in the past
const END: HrTime = [1700000005, 500];

interface TimeCase {
  label: string;
  run: (times?: {startTime?: TimeInput; endTime?: TimeInput}) => void;
  locate: (spans: ReadableSpan[]) => ReadableSpan;
}

const CASES: TimeCase[] = [
  {
    label: 'Turn',
    run: times => {
      const turn = Turn.create({startTime: times?.startTime});
      turn.end({endTime: times?.endTime});
    },
    locate: spans => findSpan(spans, 'invoke_agent'),
  },
  {
    label: 'LLM',
    run: times => {
      const turn = Turn.create({});
      const llm = turn.startLLM({model: 'gpt-4o', startTime: times?.startTime});
      llm.end({endTime: times?.endTime});
      turn.end();
    },
    locate: spans => findSpan(spans, 'chat'),
  },
  {
    label: 'Tool',
    run: times => {
      const turn = Turn.create({});
      const tool = turn.startTool({
        name: 'get_weather',
        startTime: times?.startTime,
      });
      tool.end({endTime: times?.endTime});
      turn.end();
    },
    locate: spans => findSpan(spans, 'execute_tool'),
  },
  {
    label: 'SubAgent',
    run: times => {
      const turn = Turn.create({agentName: 'parent'});
      const sub = turn.startSubagent({
        name: 'child-bot',
        startTime: times?.startTime,
      });
      sub.end({endTime: times?.endTime});
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
  },
];

describe.each(CASES)('post-hoc times on $label', ({run, locate}) => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('records a caller-set startTime on the span', () => {
    run({startTime: START, endTime: END});
    expect(locate(getExporter().getFinishedSpans()).startTime).toEqual(START);
  });

  it('records a caller-set endTime on the span', () => {
    run({startTime: START, endTime: END});
    expect(locate(getExporter().getFinishedSpans()).endTime).toEqual(END);
  });

  it('falls back to wall-clock now when no times are given', () => {
    run();
    const span = locate(getExporter().getFinishedSpans());
    // No fixture times → OTel stamps real now, which is far newer than START.
    expect(span.startTime[0]).toBeGreaterThan(START[0]);
    expect(span.endTime[0]).toBeGreaterThanOrEqual(span.startTime[0]);
  });
});
