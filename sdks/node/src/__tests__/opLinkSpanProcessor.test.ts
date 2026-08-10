import {
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {
  PARENT_CALL_ID_SPAN_ATTR,
  PARENT_CALL_TRACE_ID_SPAN_ATTR,
} from '../constants';
import {runIsolated} from '../genai/context';
import {getWeaveTracer} from '../genai/provider';
import {Turn} from '../genai/turn';
import {op} from '../op';
import {initWithCustomTraceServer} from './clientMock';
import {findSpan, setupGenAITestEnvironment} from './genai/common';
import {type Call, InMemoryTraceServer} from './helpers/inMemoryTraceServer';

// OTel JS's default OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT.
const SPAN_ATTRIBUTE_LIMIT = 128;

// Every test here goes through the public path — run an op, emit a span, read
// the exported span — because a processor that is never reached still passes
// any test that calls onStart directly.
describe('OpLinkSpanProcessor', () => {
  setupGenAITestEnvironment();

  const projectId = 'test-project';
  let traceServer: InMemoryTraceServer;
  let exporter: InMemorySpanExporter;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    exporter = new InMemorySpanExporter();
    initWithCustomTraceServer(projectId, traceServer, {
      genai: {spanProcessor: new SimpleSpanProcessor(exporter)},
    });
  });

  /** Emit one weave span, already carrying `ownAttributes` of its own. */
  function emitSpan(name: string, ownAttributes = 0): void {
    const attributes = Object.fromEntries(
      Array.from({length: ownAttributes}, (_, i) => [`custom.${i}`, i])
    );
    getWeaveTracer('test').startSpan(name, {attributes}).end();
  }

  /** The calls the trace server stored, keyed by the op that made them. */
  async function storedCalls(): Promise<Record<string, Call>> {
    const calls = await traceServer.getCalls(projectId);
    return Object.fromEntries(
      calls.map(c => [c.op_name.match(/\/op\/([^:]+):/)![1], c])
    );
  }

  test('stamps the enclosing call onto a span an op emits', async () => {
    await op(() => emitSpan('agent_work'), {name: 'orchestrate'})();
    const {orchestrate} = await storedCalls();

    const span = findSpan(exporter.getFinishedSpans(), 'agent_work');
    expect(span.attributes[PARENT_CALL_ID_SPAN_ATTR]).toBe(orchestrate.id);
    expect(span.attributes[PARENT_CALL_TRACE_ID_SPAN_ATTR]).toBe(
      orchestrate.trace_id
    );
  });

  test('stamps every conversation SDK span in the subtree', async () => {
    await op(
      () => {
        const turn = Turn.create({});
        turn.startLLM({model: 'gpt-4o'}).end();
        turn.end();
      },
      {name: 'converse'}
    )();
    const {converse} = await storedCalls();

    const spans = exporter.getFinishedSpans();
    for (const name of ['invoke_agent', 'chat']) {
      const attrs = findSpan(spans, name).attributes;
      expect(attrs[PARENT_CALL_ID_SPAN_ATTR]).toBe(converse.id);
      expect(attrs[PARENT_CALL_TRACE_ID_SPAN_ATTR]).toBe(converse.trace_id);
    }
  });

  test('writes nothing on a span emitted outside any op', () => {
    emitSpan('standalone');

    // No call means no link, not an empty-string link.
    const span = findSpan(exporter.getFinishedSpans(), 'standalone');
    expect(span.attributes).toEqual({});
  });

  test('stamps the innermost op a span started under', async () => {
    const inner = op(() => emitSpan('inner_work'), {name: 'inner'});
    await op(
      async () => {
        emitSpan('outer_work');
        await inner();
      },
      {name: 'outer'}
    )();

    const {inner: innerCall, outer: outerCall} = await storedCalls();
    const spans = exporter.getFinishedSpans();

    expect(findSpan(spans, 'outer_work').attributes).toMatchObject({
      [PARENT_CALL_ID_SPAN_ATTR]: outerCall.id,
      [PARENT_CALL_TRACE_ID_SPAN_ATTR]: outerCall.trace_id,
    });
    // A nested call keeps its parent's trace, so only the id moves.
    expect(findSpan(spans, 'inner_work').attributes).toMatchObject({
      [PARENT_CALL_ID_SPAN_ATTR]: innerCall.id,
      [PARENT_CALL_TRACE_ID_SPAN_ATTR]: outerCall.trace_id,
    });
  });

  test('stamps a span emitted inside runIsolated', async () => {
    await op(() => runIsolated(() => emitSpan('isolated_work')), {
      name: 'orchestrate',
    })();
    const {orchestrate} = await storedCalls();

    // runIsolated swaps the GenAI state, not the call stack the link reads.
    const span = findSpan(exporter.getFinishedSpans(), 'isolated_work');
    expect(span.attributes[PARENT_CALL_ID_SPAN_ATTR]).toBe(orchestrate.id);
    expect(span.attributes[PARENT_CALL_TRACE_ID_SPAN_ATTR]).toBe(
      orchestrate.trace_id
    );
  });

  test('a crowded span keeps the call id and gives up the trace id', async () => {
    await op(
      () => {
        emitSpan('at_limit', SPAN_ATTRIBUTE_LIMIT - 2);
        emitSpan('one_over', SPAN_ATTRIBUTE_LIMIT - 1);
      },
      {name: 'orchestrate'}
    )();
    const {orchestrate} = await storedCalls();
    const spans = exporter.getFinishedSpans();

    const atLimit = findSpan(spans, 'at_limit').attributes;
    expect(atLimit[PARENT_CALL_ID_SPAN_ATTR]).toBe(orchestrate.id);
    expect(atLimit[PARENT_CALL_TRACE_ID_SPAN_ATTR]).toBe(orchestrate.trace_id);

    // The write order in onStart decides which half of the link survives.
    const oneOver = findSpan(spans, 'one_over').attributes;
    expect(oneOver[PARENT_CALL_ID_SPAN_ATTR]).toBe(orchestrate.id);
    expect(oneOver[PARENT_CALL_TRACE_ID_SPAN_ATTR]).toBeUndefined();
  });
});
