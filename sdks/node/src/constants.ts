export const TRACE_CALL_EMOJI = '🍩';
export const TRACE_OBJECT_EMOJI = '📦';
export const MAX_OBJECT_NAME_LENGTH = 128;

export const EVALUATION_RUN_OP_NAME = 'Evaluation.evaluate';
export const EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME =
  'Evaluation.predict_and_score';
export const EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS =
  'Evaluation.predictAndScore';
export const EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAMES = [
  EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
  EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS,
] as const;

/**
 * Call-attribute key for evaluation metadata. Reserved internal Weave key:
 * user ops must not write to it. Both eval paths — declarative
 * `Evaluation.evaluate` and imperative `EvaluationLogger` — tag their calls
 * with it so consumers (eval-results rendering, server-side ingest sampling)
 * can recognize eval calls.
 */
export const EVAL_META_KEY = '_weave_eval_meta';

export const EVAL_RUN_ID_SPAN_ATTR = 'weave.eval.run_id';
export const EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR =
  'weave.eval.predict_and_score_call_id';
export const EVAL_PROJECT_ID_SPAN_ATTR = 'weave.eval.project_id';
export const EVAL_EVALUATION_NAME_SPAN_ATTR = 'weave.eval.evaluation_name';

/**
 * Span-attribute keys carrying the enclosing op call. Spelled the same as
 * `weave/shared/otel_span_attrs.py`, which the server's semconv promotes into
 * the `parent_call_id` / `parent_call_trace_id` span columns.
 */
export const PARENT_CALL_ID_SPAN_ATTR = 'weave.parent_call.id';
export const PARENT_CALL_TRACE_ID_SPAN_ATTR = 'weave.parent_call.trace_id';

/**
 * Request header advertising the sampling-relevant capabilities this SDK build
 * guarantees, so a future server-side ingest sampler can tell a sampling-safe
 * client from an older one and leave unsupported traffic unsampled. Sent on
 * every ingest request (it describes the client, not one trace); a
 * comma-separated, forward-compatible token list.
 */
export const CLIENT_CAPABILITIES_HEADER = 'X-Weave-Client-Capabilities';
export const CLIENT_CAPABILITIES = 'trace_id_on_end,eval_child_meta';
