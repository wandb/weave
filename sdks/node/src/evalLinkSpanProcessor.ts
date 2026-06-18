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
import {ATTR_GEN_AI_OPERATION_NAME} from './genai/semconv';
import type {CallStackEntry, WeaveClient} from './weaveClient';
import state from './state';

// The API TracerProvider type only exposes getTracer. addSpanProcessor is an
// SDK-specific, deprecated late-registration hook, so we feature-detect it and
// no-op for API-only or newer providers that do not support it.
type SpanProcessorProvider = TracerProvider & {
  addSpanProcessor: (processor: SpanProcessor) => void;
};

function isSpanProcessorProvider(
  provider: TracerProvider
): provider is SpanProcessorProvider {
  return (
    'addSpanProcessor' in provider &&
    typeof provider.addSpanProcessor === 'function'
  );
}

type ClientGetter = () => WeaveClient | null;

interface GenAISpanRef {
  trace_id: string;
  span_id: string;
}

function attachGenAISpanRefToCallSummary(
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
  const existingGenAISpanRefs = weaveSummary[GENAI_SPAN_REF_ATTR_KEY];
  const genaiSpanRefs = Array.isArray(existingGenAISpanRefs)
    ? existingGenAISpanRefs
    : existingGenAISpanRefs != null
      ? [existingGenAISpanRefs]
      : [];

  const alreadyAttached = genaiSpanRefs.some(
    ref =>
      ref != null &&
      typeof ref === 'object' &&
      ref.trace_id === genaiSpanRef.trace_id &&
      ref.span_id === genaiSpanRef.span_id
  );

  call.childSummary[WEAVE_ATTRIBUTES_NAMESPACE] = {
    ...weaveSummary,
    [GENAI_SPAN_REF_ATTR_KEY]: alreadyAttached
      ? genaiSpanRefs
      : [...genaiSpanRefs, genaiSpanRef],
  };
}

function findPredictAndScoreCall(
  getClient: ClientGetter
): CallStackEntry | null {
  // The predict-and-score call is the per-row eval call that owns the model
  // prediction. This is where we store GenAI span refs for eval result rows.
  return (
    getClient()
      ?.getCallStack()
      .findLastByOpName(EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAMES) ?? null
  );
}

function findEvaluateCall(getClient: ClientGetter): CallStackEntry | null {
  // The evaluate call is the parent eval run. We only use it to attach the
  // human-readable evaluation name onto GenAI spans for filtering/deep links.
  return (
    getClient()?.getCallStack().findLastByOpName([EVALUATION_RUN_OP_NAME]) ??
    null
  );
}

/**
 * OpenTelemetry SpanProcessor that links GenAI spans created during an
 * Evaluation.predictAndScore call back to that evaluation row.
 */
export class EvalLinkSpanProcessor implements SpanProcessor {
  constructor(private readonly getClient: ClientGetter) {}

  onStart(span: Span, _parentContext: Context): void {
    const client = this.getClient();
    const call = findPredictAndScoreCall(this.getClient);
    if (!client || !call) {
      return;
    }

    span.setAttribute(EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR, call.callId);
    span.setAttribute(EVAL_PROJECT_ID_SPAN_ATTR, client.projectId);

    const evalName = findEvaluateCall(this.getClient)?.displayName;
    if (evalName) {
      span.setAttribute(EVAL_EVALUATION_NAME_SPAN_ATTR, evalName);
    }
  }

  onEnd(span: ReadableSpan): void {
    const attrs = span.attributes || {};
    if (!(ATTR_GEN_AI_OPERATION_NAME in attrs)) {
      return;
    }

    const call = findPredictAndScoreCall(this.getClient);
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
  getClient: ClientGetter,
  provider: TracerProvider = trace.getTracerProvider()
): boolean {
  if (state.evalLink.registeredProviders.has(provider)) {
    return true;
  }

  if (!isSpanProcessorProvider(provider)) {
    return false;
  }

  provider.addSpanProcessor(new EvalLinkSpanProcessor(getClient));
  state.evalLink.registeredProviders.add(provider);
  return true;
}
