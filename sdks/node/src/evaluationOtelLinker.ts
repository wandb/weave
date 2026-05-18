import {
  isSpanContextValid,
  trace,
  type Context,
  type TracerProvider,
} from '@opentelemetry/api';
import type {
  ReadableSpan,
  Span,
  SpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {
  EVAL_EVALUATION_NAME_SPAN_ATTR,
  EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR,
  EVAL_PROJECT_ID_SPAN_ATTR,
  EVALUATION_RUN_OP_NAME,
  EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAMES,
  GENAI_SPAN_REF_ATTR_KEY,
  WEAVE_ATTRIBUTES_NAMESPACE,
} from './constants';
import type {CallStackEntry, WeaveClient} from './weaveClient';

const GENAI_OPERATION_NAME_ATTR = 'gen_ai.operation.name';
const EVAL_LINK_PROCESSOR_REGISTERED = Symbol.for(
  '_weave_eval_link_span_processor_registered'
);

type SpanProcessorProvider = TracerProvider & {
  addSpanProcessor?: (processor: SpanProcessor) => void;
  [EVAL_LINK_PROCESSOR_REGISTERED]?: boolean;
};

let getClient: () => WeaveClient | null = () => null;

export function setEvalLinkClientGetter(
  clientGetter: () => WeaveClient | null
): void {
  getClient = clientGetter;
}

export interface GenAISpanRef {
  trace_id: string;
  span_id: string;
}

export function attachGenAISpanRefToCallSummary(
  call: CallStackEntry,
  genaiSpanRef: GenAISpanRef
): void {
  const existingWeaveSummary = call.childSummary[WEAVE_ATTRIBUTES_NAMESPACE];
  const weaveSummary =
    existingWeaveSummary != null &&
    typeof existingWeaveSummary === 'object' &&
    !Array.isArray(existingWeaveSummary)
      ? existingWeaveSummary
      : {};

  call.childSummary[WEAVE_ATTRIBUTES_NAMESPACE] = {
    ...weaveSummary,
    [GENAI_SPAN_REF_ATTR_KEY]: genaiSpanRef,
  };
}

function findPredictAndScoreCall(): CallStackEntry | null {
  return (
    getClient()
      ?.getCallStack()
      .findLastByOpName(EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAMES) ?? null
  );
}

function findEvaluateCall(): CallStackEntry | null {
  return (
    getClient()
      ?.getCallStack()
      .findLastByOpName([EVALUATION_RUN_OP_NAME]) ?? null
  );
}

/**
 * OpenTelemetry SpanProcessor that links GenAI spans created during an
 * Evaluation.predictAndScore call back to that evaluation row.
 */
export class EvalLinkSpanProcessor implements SpanProcessor {
  onStart(span: Span, _parentContext: Context): void {
    const client = getClient();
    const call = findPredictAndScoreCall();
    if (!client || !call) {
      return;
    }

    span.setAttribute(EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR, call.callId);
    span.setAttribute(EVAL_PROJECT_ID_SPAN_ATTR, client.projectId);

    const evalName = findEvaluateCall()?.displayName;
    if (evalName) {
      span.setAttribute(EVAL_EVALUATION_NAME_SPAN_ATTR, evalName);
    }
  }

  onEnd(span: ReadableSpan): void {
    const attrs = span.attributes || {};
    if (!(GENAI_OPERATION_NAME_ATTR in attrs)) {
      return;
    }

    const call = findPredictAndScoreCall();
    if (!call) {
      return;
    }

    const spanContext = span.spanContext();
    if (!isSpanContextValid(spanContext)) {
      return;
    }

    attachGenAISpanRefToCallSummary(call, {
      trace_id: spanContext.traceId,
      span_id: spanContext.spanId,
    });
  }

  forceFlush(): Promise<void> {
    return Promise.resolve();
  }

  shutdown(): Promise<void> {
    return Promise.resolve();
  }
}

/**
 * Register EvalLinkSpanProcessor on a TracerProvider when the provider exposes
 * the SDK addSpanProcessor API.
 *
 * Returns true when the processor is installed or was already installed.
 * Returns false for API-only proxy providers or other custom providers that do
 * not expose addSpanProcessor.
 */
export function registerEvalLinkSpanProcessor(
  provider: TracerProvider = trace.getTracerProvider()
): boolean {
  const spanProcessorProvider = provider as SpanProcessorProvider;
  if (spanProcessorProvider[EVAL_LINK_PROCESSOR_REGISTERED]) {
    return true;
  }
  if (typeof spanProcessorProvider.addSpanProcessor !== 'function') {
    return false;
  }

  spanProcessorProvider.addSpanProcessor(new EvalLinkSpanProcessor());
  spanProcessorProvider[EVAL_LINK_PROCESSOR_REGISTERED] = true;
  return true;
}
