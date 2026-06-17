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

export const WEAVE_ATTRIBUTES_NAMESPACE = 'weave';
export const GENAI_SPAN_REF_ATTR_KEY = 'genai_span_ref';

export const EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR =
  'weave.eval.predict_and_score_call_id';
export const EVAL_PROJECT_ID_SPAN_ATTR = 'weave.eval.project_id';
export const EVAL_EVALUATION_NAME_SPAN_ATTR = 'weave.eval.evaluation_name';
