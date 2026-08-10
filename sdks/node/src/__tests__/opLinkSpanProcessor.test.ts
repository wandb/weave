import {
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {requireGlobalClient} from '../clientApi';
import {
  EVAL_EVALUATION_NAME_SPAN_ATTR,
  EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR,
  EVAL_PROJECT_ID_SPAN_ATTR,
  EVAL_RUN_ID_SPAN_ATTR,
  PARENT_CALL_ID_SPAN_ATTR,
  PARENT_CALL_TRACE_ID_SPAN_ATTR,
} from '../constants';
import {Dataset} from '../dataset';
import {Evaluation} from '../evaluation';
import {runIsolated} from '../genai/context';
import {getWeaveTracer} from '../genai/provider';
import {Turn} from '../genai/turn';
import {op} from '../op';
import {parseWeaveUri} from '../uriParser';
import {initWithCustomTraceServer} from './clientMock';
import {
  findSpan,
  setupGenAITestEnvironment,
  TEST_PROJECT,
} from './genai/common';
import {type Call, InMemoryTraceServer} from './helpers/inMemoryTraceServer';

// The overflow tests need a known ceiling. The provider takes no spanLimits, so
// declare it through the variable OTel reads while building one.
const LIMIT_ENV = 'OTEL_SPAN_ATTRIBUTE_COUNT_LIMIT';
const SPAN_ATTRIBUTE_LIMIT = 128;

// Every test here goes through the public path — run an op, emit a span, read
// the exported span — because a processor that is never reached still passes
// any test that calls onStart directly.
describe('OpLinkSpanProcessor', () => {
  setupGenAITestEnvironment();

  const originalLimit = process.env[LIMIT_ENV];
  let traceServer: InMemoryTraceServer;
  let exporter: InMemorySpanExporter;

  beforeEach(() => {
    process.env[LIMIT_ENV] = String(SPAN_ATTRIBUTE_LIMIT);
    traceServer = new InMemoryTraceServer();
    exporter = new InMemorySpanExporter();
    initWithCustomTraceServer(TEST_PROJECT, traceServer, {
      genai: {spanProcessor: new SimpleSpanProcessor(exporter)},
    });
  });

  afterEach(() => {
    if (originalLimit === undefined) {
      delete process.env[LIMIT_ENV];
    } else {
      process.env[LIMIT_ENV] = originalLimit;
    }
  });

  /** Emit one weave span, already carrying `ownAttributes` of its own. */
  function emitSpan(name: string, ownAttributes = 0): void {
    const attributes = Object.fromEntries(
      Array.from({length: ownAttributes}, (_, i) => [`custom.${i}`, i])
    );
    getWeaveTracer('test').startSpan(name, {attributes}).end();
  }

  /** The calls the trace server stored, keyed by the op that made them. */
  async function storedCalls(
    server: InMemoryTraceServer = traceServer
  ): Promise<Record<string, Call>> {
    // Query directly once the client has drained: getCalls() waits for the call
    // count to move, so after a flush it burns its full 1500ms timeout and logs
    // a warning.
    await requireGlobalClient().flush();
    const {calls} = await server.calls.callsStreamQueryPost({
      project_id: TEST_PROJECT,
    });
    return Object.fromEntries(
      calls.flatMap((c: Call) => {
        const ref = parseWeaveUri(c.op_name);
        return ref?.type === 'op' ? [[ref.name, c] as const] : [];
      })
    );
  }

  test('stamps the enclosing call onto a span an op emits', async () => {
    await op(() => emitSpan('agent_work'), {name: 'orchestrate'})();
    const {orchestrate} = await storedCalls();

    expect(
      findSpan(exporter.getFinishedSpans(), 'agent_work').attributes
    ).toEqual({
      [PARENT_CALL_ID_SPAN_ATTR]: orchestrate.id,
      [PARENT_CALL_TRACE_ID_SPAN_ATTR]: orchestrate.trace_id,
    });
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

    expect(findSpan(spans, 'outer_work').attributes).toEqual({
      [PARENT_CALL_ID_SPAN_ATTR]: outerCall.id,
      [PARENT_CALL_TRACE_ID_SPAN_ATTR]: outerCall.trace_id,
    });
    // A nested call keeps its parent's trace, so only the id moves.
    expect(findSpan(spans, 'inner_work').attributes).toEqual({
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
    expect(
      findSpan(exporter.getFinishedSpans(), 'isolated_work').attributes
    ).toEqual({
      [PARENT_CALL_ID_SPAN_ATTR]: orchestrate.id,
      [PARENT_CALL_TRACE_ID_SPAN_ATTR]: orchestrate.trace_id,
    });
  });

  test('links to the client a later same-project init installed', async () => {
    await op(() => emitSpan('before'), {name: 'before'})();

    // A same-project init() swaps the client but keeps the cached provider, so a
    // processor holding the first client would read a stack nothing pushes to.
    const reinitialized = new InMemoryTraceServer();
    initWithCustomTraceServer(TEST_PROJECT, reinitialized, {
      genai: {spanProcessor: new SimpleSpanProcessor(exporter)},
    });
    await op(() => emitSpan('after'), {name: 'after'})();
    const {after} = await storedCalls(reinitialized);

    expect(findSpan(exporter.getFinishedSpans(), 'after').attributes).toEqual({
      [PARENT_CALL_ID_SPAN_ATTR]: after.id,
      [PARENT_CALL_TRACE_ID_SPAN_ATTR]: after.trace_id,
    });
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

  test('gives up its slots to the eval link on a crowded span', async () => {
    const model = op(
      async () => {
        emitSpan('crowded', SPAN_ATTRIBUTE_LIMIT - 4);
        return 'answer';
      },
      {name: 'model'}
    );
    await new Evaluation({
      dataset: new Dataset({rows: [{question: 'hello'}]}),
      scorers: [],
    }).evaluate({model, maxConcurrency: 1});

    // Four free slots and six attributes wanting them: the eval link runs
    // first, so all four of its writes land and both of ours go. It writes four
    // because Evaluation always names the evaluate call.
    const attrs = findSpan(exporter.getFinishedSpans(), 'crowded').attributes;
    expect(
      Object.keys(attrs)
        .filter(k => k.startsWith('weave.'))
        .sort()
    ).toEqual(
      [
        EVAL_RUN_ID_SPAN_ATTR,
        EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR,
        EVAL_PROJECT_ID_SPAN_ATTR,
        EVAL_EVALUATION_NAME_SPAN_ATTR,
      ].sort()
    );
  });
});
