import type {Context} from '@opentelemetry/api';
import type {
  ReadableSpan,
  Span,
  SpanProcessor,
} from '@opentelemetry/sdk-trace-base';

import {
  EVAL_EVALUATION_NAME_SPAN_ATTR,
  EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR,
  EVAL_PROJECT_ID_SPAN_ATTR,
  EVAL_RUN_ID_SPAN_ATTR,
  EVALUATION_RUN_OP_NAME,
  EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAMES,
} from './constants';
import type {CallStackEntry, WeaveClient} from './weaveClient';

type ClientGetter = () => WeaveClient | null;

function findPredictAndScoreCall(
  getClient: ClientGetter
): CallStackEntry | null {
  // The predict-and-score call is the per-row eval call that owns the model
  // prediction. Its ID is what identifies an eval result row.
  return (
    getClient()
      ?.getCallStack()
      .findLastByOpName(EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAMES) ?? null
  );
}

function findEvaluateCall(getClient: ClientGetter): CallStackEntry | null {
  // The evaluate call is the parent eval run: its ID is the run ID eval results
  // match on, and its display name is the human-readable evaluation name.
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
    const evaluateCall = findEvaluateCall(this.getClient);

    // A span already at its attribute limit drops whatever arrives next, so the
    // pair eval results match on is written before the two display-only ones.
    if (evaluateCall) {
      span.setAttribute(EVAL_RUN_ID_SPAN_ATTR, evaluateCall.callId);
    }
    span.setAttribute(EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR, call.callId);
    span.setAttribute(EVAL_PROJECT_ID_SPAN_ATTR, client.projectId);

    if (evaluateCall?.displayName) {
      span.setAttribute(
        EVAL_EVALUATION_NAME_SPAN_ATTR,
        evaluateCall.displayName
      );
    }
  }

  onEnd(_span: ReadableSpan): void {}

  forceFlush(): Promise<void> {
    return Promise.resolve();
  }

  shutdown(): Promise<void> {
    return Promise.resolve();
  }
}
