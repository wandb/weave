import {ROOT_CONTEXT} from '@opentelemetry/api';
import {
  InMemorySpanExporter,
  SimpleSpanProcessor,
  type Span,
} from '@opentelemetry/sdk-trace-base';

import {requireGlobalClient} from '../clientApi';
import {
  EVAL_EVALUATION_NAME_SPAN_ATTR,
  EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR,
  EVAL_PROJECT_ID_SPAN_ATTR,
  EVAL_RUN_ID_SPAN_ATTR,
  EVALUATION_RUN_OP_NAME,
  EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS,
} from '../constants';
import {Dataset} from '../dataset';
import {Evaluation} from '../evaluation';
import {EvalLinkSpanProcessor} from '../evalLinkSpanProcessor';
import {runIsolated} from '../genai/context';
import {Turn} from '../genai/turn';
import {InMemoryTraceServer} from './helpers/inMemoryTraceServer';
import {op} from '../op';
import {CallStack, type CallStackEntry} from '../weaveClient';
import {initWithCustomTraceServer} from './clientMock';
import {findSpan, setupGenAITestEnvironment} from './genai/common';

describe('EvalLinkSpanProcessor', () => {
  const projectId = 'test-project';

  beforeEach(() => {
    initWithCustomTraceServer(projectId, new InMemoryTraceServer());
  });

  test('injects eval metadata on span start', () => {
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
      () => processor.onStart(span, ROOT_CONTEXT)
    );

    // Ordered on purpose — see the comment on onStart.
    expect((span.setAttribute as jest.Mock).mock.calls).toEqual([
      ['weave.eval.run_id', 'eval-call'],
      ['weave.eval.predict_and_score_call_id', 'predict-and-score-call'],
      ['weave.eval.project_id', projectId],
      ['weave.eval.evaluation_name', 'my-eval-my-model'],
    ]);
  });
});

// Everything above drives the processor directly. These go through the public
// path instead — run an evaluation, emit a real GenAI span, read the exported
// span — because the processor was wired to a provider Weave never emits
// through, and no direct-call test can see that.
describe('EvalLinkSpanProcessor - declarative Evaluation', () => {
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

  /** Evaluate one row, emitting `emitSpan()` inside the prediction. */
  async function evaluateOnce(emitSpan: () => void) {
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

    const calls = await traceServer.getCalls(projectId);
    return {
      evaluateCall: calls.find(c =>
        c.op_name.includes(EVALUATION_RUN_OP_NAME)
      )!,
      predictAndScoreCall: calls.find(c =>
        c.op_name.includes(EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS)
      )!,
    };
  }

  test('stamps eval metadata on the spans a declarative evaluation emits', async () => {
    const {evaluateCall, predictAndScoreCall} = await evaluateOnce(() => {
      const turn = Turn.create({});
      turn.startLLM({model: 'gpt-4o'}).end();
      turn.end();
    });

    const spans = exporter.getFinishedSpans();
    const rootSpan = findSpan(spans, 'invoke_agent');
    const childSpan = findSpan(spans, 'chat');

    // Eval results match a span on the pair, so assert it, not either half.
    expect(rootSpan.attributes[EVAL_RUN_ID_SPAN_ATTR]).toBe(evaluateCall.id);
    expect(rootSpan.attributes[EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR]).toBe(
      predictAndScoreCall.id
    );
    expect(rootSpan.attributes[EVAL_PROJECT_ID_SPAN_ATTR]).toBe(projectId);
    expect(rootSpan.attributes[EVAL_EVALUATION_NAME_SPAN_ATTR]).toBe(
      evaluateCall.display_name
    );
    // Every span the prediction emits is stamped, not just the root.
    expect(childSpan.attributes[EVAL_RUN_ID_SPAN_ATTR]).toBe(evaluateCall.id);
  });

  test('stamps a span emitted inside runIsolated', async () => {
    const {evaluateCall, predictAndScoreCall} = await evaluateOnce(() =>
      runIsolated(() => Turn.create({}).end())
    );
    const span = findSpan(exporter.getFinishedSpans(), 'invoke_agent');

    expect(span.attributes[EVAL_RUN_ID_SPAN_ATTR]).toBe(evaluateCall.id);
    expect(span.attributes[EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR]).toBe(
      predictAndScoreCall.id
    );
  });
});
