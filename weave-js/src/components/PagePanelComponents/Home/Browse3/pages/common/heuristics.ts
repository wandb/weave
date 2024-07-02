const PREDICT_AND_SCORE_OP_NAME_PRE_PYDANTIC = 'Evaluation-predict_and_score';
export const PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC =
  'Evaluation.predict_and_score';
const EVALUATE_OP_NAME_PRE_PYDANTIC = 'Evaluation-evaluate';
export const EVALUATE_OP_NAME_POST_PYDANTIC = 'Evaluation.evaluate';

export const isPredictAndScoreOp = (opName: string) =>
  opName === PREDICT_AND_SCORE_OP_NAME_PRE_PYDANTIC ||
  opName === PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC;

export const isEvaluateOp = (opName: string) =>
  opName === EVALUATE_OP_NAME_PRE_PYDANTIC ||
  opName === EVALUATE_OP_NAME_POST_PYDANTIC;
