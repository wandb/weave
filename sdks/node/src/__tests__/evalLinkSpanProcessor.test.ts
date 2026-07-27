import {ROOT_CONTEXT, TraceFlags} from '@opentelemetry/api';
import type {ReadableSpan, Span} from '@opentelemetry/sdk-trace-base';

import {requireGlobalClient} from '../clientApi';
import {Dataset} from '../dataset';
import {Evaluation} from '../evaluation';
import {
  EvalLinkSpanProcessor,
  registerEvalLinkSpanProcessor,
} from '../evalLinkSpanProcessor';
import {InMemoryTraceServer} from './helpers/inMemoryTraceServer';
import {op} from '../op';
import {CallStack, type CallStackEntry} from '../weaveClient';
import {initWithCustomTraceServer} from './clientMock';

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

    expect(span.setAttribute).toHaveBeenCalledWith(
      'weave.eval.predict_and_score_call_id',
      'predict-and-score-call'
    );
    expect(span.setAttribute).toHaveBeenCalledWith(
      'weave.eval.project_id',
      projectId
    );
    expect(span.setAttribute).toHaveBeenCalledWith(
      'weave.eval.evaluation_name',
      'my-eval-my-model'
    );
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

  test('registers on SDK tracer providers once', () => {
    const provider = {
      addSpanProcessor: jest.fn(),
      getTracer: jest.fn(),
    };

    expect(
      registerEvalLinkSpanProcessor(
        () => requireGlobalClient(),
        provider as any
      )
    ).toBe(true);
    expect(
      registerEvalLinkSpanProcessor(
        () => requireGlobalClient(),
        provider as any
      )
    ).toBe(true);

    expect(provider.addSpanProcessor).toHaveBeenCalledTimes(1);
    expect(provider.addSpanProcessor.mock.calls[0][0]).toBeInstanceOf(
      EvalLinkSpanProcessor
    );
  });

  test('does not register on API-only tracer providers', () => {
    const provider = {
      getTracer: jest.fn(),
    };

    expect(
      registerEvalLinkSpanProcessor(
        () => requireGlobalClient(),
        provider as any
      )
    ).toBe(false);
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
