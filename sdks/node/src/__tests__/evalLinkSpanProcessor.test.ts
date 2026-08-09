import {ROOT_CONTEXT, TraceFlags} from '@opentelemetry/api';
import {
  InMemorySpanExporter,
  SimpleSpanProcessor,
  type ReadableSpan,
  type Span,
} from '@opentelemetry/sdk-trace-base';

import {requireGlobalClient} from '../clientApi';
import {
  EVAL_EVALUATION_NAME_SPAN_ATTR,
  EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR,
  EVAL_PROJECT_ID_SPAN_ATTR,
  EVAL_RUN_ID_SPAN_ATTR,
} from '../constants';
import {Dataset} from '../dataset';
import {Evaluation} from '../evaluation';
import {EvalLinkSpanProcessor} from '../evalLinkSpanProcessor';
import {runIsolated} from '../genai/context';
import {
  getWeaveTracer,
  getWeaveTracerProvider,
  shutdownWeaveTracerProvider,
} from '../genai/provider';
import {Turn} from '../genai/turn';
import {InMemoryTraceServer} from './helpers/inMemoryTraceServer';
import {op} from '../op';
import {CallStack, type CallStackEntry} from '../weaveClient';
import {initWithCustomTraceServer} from './clientMock';
import {installFakeClient, setupGenAITestEnvironment} from './genai/common';

const TRACE_ID = '1234567890abcdef1234567890abcdef';
const SPAN_ID = '1234567890abcdef';
const SECOND_SPAN_ID = 'fedcba0987654321';

function readableGenAISpan(spanId = SPAN_ID): ReadableSpan {
  return {
    attributes: {'gen_ai.operation.name': 'chat'},
    spanContext: () => ({
      traceId: TRACE_ID,
      spanId,
      traceFlags: TraceFlags.SAMPLED,
    }),
  } as unknown as ReadableSpan;
}

describe('EvalLinkSpanProcessor', () => {
  let traceServer: InMemoryTraceServer;
  const projectId = 'test-project';

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(projectId, traceServer);
  });

  test('injects eval metadata on span start and stores GenAI span refs on end', () => {
    const client = requireGlobalClient();
    const processor = new EvalLinkSpanProcessor(() => requireGlobalClient());
    const evaluateEntry: CallStackEntry = {
      callId: 'eval-call',
      traceId: 'weave-trace',
      childSummary: {},
      opName: 'Evaluation.evaluate',
      displayName: 'my-eval-my-model',
    };
    const predictAndScoreEntry: CallStackEntry = {
      callId: 'predict-and-score-call',
      traceId: 'weave-trace',
      childSummary: {},
      opName: 'Evaluation.predictAndScore',
    };
    const span = {setAttribute: jest.fn()} as unknown as Span;

    client.runWithCallStack(
      new CallStack([evaluateEntry, predictAndScoreEntry]),
      () => {
        processor.onStart(span, ROOT_CONTEXT);
        processor.onEnd(readableGenAISpan());
        processor.onEnd(readableGenAISpan(SECOND_SPAN_ID));
      }
    );

    // Ordered: a span that is already at its attribute limit drops whatever
    // arrives next, and the server needs the first two to link the span at all.
    expect((span.setAttribute as jest.Mock).mock.calls).toEqual([
      ['weave.eval.run_id', 'eval-call'],
      ['weave.eval.predict_and_score_call_id', 'predict-and-score-call'],
      ['weave.eval.project_id', projectId],
      ['weave.eval.evaluation_name', 'my-eval-my-model'],
    ]);
    expect(predictAndScoreEntry.childSummary).toEqual({
      weave: {
        genai_span_ref: [
          {
            trace_id: TRACE_ID,
            span_id: SPAN_ID,
          },
          {
            trace_id: TRACE_ID,
            span_id: SECOND_SPAN_ID,
          },
        ],
      },
    });
  });

  test('upgrades existing single GenAI span ref summary and deduplicates refs', () => {
    const processor = new EvalLinkSpanProcessor(() => requireGlobalClient());
    const predictAndScoreEntry: CallStackEntry = {
      callId: 'predict-and-score-call',
      traceId: 'weave-trace',
      childSummary: {
        weave: {
          genai_span_ref: {
            trace_id: TRACE_ID,
            span_id: SPAN_ID,
          },
        },
      },
      opName: 'Evaluation.predictAndScore',
    };

    requireGlobalClient().runWithCallStack(
      new CallStack([predictAndScoreEntry]),
      () => {
        processor.onEnd(readableGenAISpan());
        processor.onEnd(readableGenAISpan(SECOND_SPAN_ID));
      }
    );

    expect(predictAndScoreEntry.childSummary.weave.genai_span_ref).toEqual([
      {
        trace_id: TRACE_ID,
        span_id: SPAN_ID,
      },
      {
        trace_id: TRACE_ID,
        span_id: SECOND_SPAN_ID,
      },
    ]);
  });

  test('links GenAI spans to declarative Evaluation.predictAndScore calls', async () => {
    const processor = new EvalLinkSpanProcessor(() => requireGlobalClient());
    const dataset = new Dataset({rows: [{question: 'hello'}]});
    const model = op(async function model({
      datasetRow,
    }: {
      datasetRow: {question: string};
    }) {
      processor.onEnd(readableGenAISpan());
      return `answer: ${datasetRow.question}`;
    });
    const evaluation = new Evaluation({dataset, scorers: []});

    await evaluation.evaluate({model, maxConcurrency: 1});

    const calls = await traceServer.getCalls(projectId);
    const predictAndScoreCall = calls.find(c =>
      c.op_name.includes('Evaluation.predictAndScore')
    );

    expect(predictAndScoreCall?.summary?.weave?.genai_span_ref).toEqual([
      {
        trace_id: TRACE_ID,
        span_id: SPAN_ID,
      },
    ]);
  });
});

// Everything above drives the processor directly. These go through the public
// path instead — emit a real GenAI span and read the exported span — because
// the processor was wired to a provider Weave never emits through, and no
// direct-call test can see that.
describe('EvalLinkSpanProcessor wiring', () => {
  setupGenAITestEnvironment();

  const projectId = 'test-entity/test-project';
  let traceServer: InMemoryTraceServer;
  let exporter: InMemorySpanExporter;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    exporter = new InMemorySpanExporter();
    initWithCustomTraceServer(projectId, traceServer, {
      genai: {spanProcessor: new SimpleSpanProcessor(exporter)},
    });
  });

  function evalLinkProcessorCount(): number {
    // No public API lists a provider's processors, and being in that list is
    // the whole contract here, so read the SDK's own array.
    const registered =
      (getWeaveTracerProvider() as any)?._registeredSpanProcessors ?? [];
    return registered.filter((p: unknown) => p instanceof EvalLinkSpanProcessor)
      .length;
  }

  async function evaluateOnce(emitSpan: () => void): Promise<void> {
    const dataset = new Dataset({rows: [{question: 'hello'}]});
    const model = op(async function model({
      datasetRow,
    }: {
      datasetRow: {question: string};
    }) {
      emitSpan();
      return `answer: ${datasetRow.question}`;
    });
    await new Evaluation({dataset, scorers: []}).evaluate({
      model,
      maxConcurrency: 1,
    });
  }

  test('stamps eval metadata on a span a declarative evaluation emits', async () => {
    await evaluateOnce(() => Turn.create({}).end());

    const calls = await traceServer.getCalls(projectId);
    const evaluateCall = calls.find(c =>
      c.op_name.includes('Evaluation.evaluate')
    );
    const predictAndScoreCall = calls.find(c =>
      c.op_name.includes('Evaluation.predictAndScore')
    );
    const spans = exporter.getFinishedSpans();
    expect(spans).toHaveLength(1);
    const spanContext = spans[0].spanContext();

    // The server only accepts a span as eval-linked when both run_id and
    // predict_and_score_call_id are set, so assert the pair, not either half.
    expect(spans[0].attributes[EVAL_RUN_ID_SPAN_ATTR]).toBe(evaluateCall!.id);
    expect(spans[0].attributes[EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR]).toBe(
      predictAndScoreCall!.id
    );
    expect(spans[0].attributes[EVAL_PROJECT_ID_SPAN_ATTR]).toBe(projectId);
    expect(spans[0].attributes[EVAL_EVALUATION_NAME_SPAN_ATTR]).toBe(
      evaluateCall!.display_name
    );
    // onEnd runs on the same span, so the trial also carries the legacy ref.
    expect(predictAndScoreCall!.summary?.weave?.genai_span_ref).toEqual([
      {trace_id: spanContext.traceId, span_id: spanContext.spanId},
    ]);
  });

  test('stamps a span emitted inside runIsolated', async () => {
    await evaluateOnce(() => runIsolated(() => Turn.create({}).end()));

    const predictAndScoreCall = (await traceServer.getCalls(projectId)).find(
      c => c.op_name.includes('Evaluation.predictAndScore')
    );
    const [span] = exporter.getFinishedSpans();

    expect(span.attributes[EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR]).toBe(
      predictAndScoreCall!.id
    );
  });

  test('installs the processor on a provider built with default settings', () => {
    installFakeClient();

    getWeaveTracer('weave-genai');

    expect(evalLinkProcessorCount()).toBe(1);
  });

  test('reinstalls the processor when a project switch rebuilds the provider', () => {
    getWeaveTracer('weave-genai');
    const first = getWeaveTracerProvider();

    // What init() does when the project changes.
    installFakeClient({projectId: 'test-entity/other-project'});
    shutdownWeaveTracerProvider();
    getWeaveTracer('weave-genai');

    expect(getWeaveTracerProvider()).not.toBe(first);
    expect(evalLinkProcessorCount()).toBe(1);
  });
});
