INFERENCE_HOST = "api.inference.wandb.ai"

COMPLETIONS_CREATE_OP_NAME = "weave.completions_create"
IMAGE_GENERATION_CREATE_OP_NAME = "weave.image_generation_create"

DEFAULT_CUSTOM_RUNTIME_MAX_TOKENS = 4096
MAX_DISPLAY_NAME_LENGTH = 1024
MAX_OP_NAME_LENGTH = 128
MAX_OBJECT_NAME_LENGTH = 128

# Evaluation Run V2 API Constants
EVALUATION_RUN_OP_NAME = "Evaluation.evaluate"
EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME = "Evaluation.predict_and_score"
# TS SDK's Evaluation class (non-imperative) derives op names from method names,
# yielding camelCase. The imperative TS EvaluationLogger and Python SDK both use
# the snake_case form above.
EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS = "Evaluation.predictAndScore"
EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAMES = (
    EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME,
    EVALUATION_RUN_PREDICTION_AND_SCORE_OP_NAME_TS,
)
EVALUATION_SUMMARIZE_OP_NAME = "Evaluation.summarize"
MODEL_PREDICT_OP_NAME = "Model.predict"
SCORER_SCORE_OP_NAME = "Scorer.score"

# Attribute keys for evaluation runs
EVALUATION_RUN_ATTR_KEY = "evaluation_run"
EVALUATION_RUN_EVALUATION_ATTR_KEY = "evaluation"
EVALUATION_RUN_MODEL_ATTR_KEY = "model"
EVALUATION_RUN_PREDICTION_ATTR_KEY = "prediction"
EVALUATION_RUN_SCORE_ATTR_KEY = "score"
EVALUATION_RUN_PREDICT_CALL_ID_ATTR_KEY = "predict_call_id"
EVALUATION_RUN_SCORER_ATTR_KEY = "scorer"
GENAI_SPAN_REF_ATTR_KEY = "genai_span_ref"
EVALUATION_RUN_SOURCE_ATTR_KEY = "source_evaluation_run_id"

# Attribute keys for predictions
PREDICTION_ATTR_KEY = "prediction"
PREDICTION_MODEL_ATTR_KEY = "model"
PREDICTION_EVALUATION_RUN_ID_ATTR_KEY = "evaluation_run_id"

# Attribute keys for scores
SCORE_ATTR_KEY = "score"
SCORE_PREDICTION_ID_ATTR_KEY = "prediction_id"
SCORE_SCORER_ATTR_KEY = "scorer"
SCORE_EVALUATION_RUN_ID_ATTR_KEY = "evaluation_run_id"

# Weave attributes namespace
WEAVE_ATTRIBUTES_NAMESPACE = "weave"

# OTel span attribute keys for eval context
EVAL_SPAN_ATTR_PREFIX = "weave.eval"
EVAL_RUN_ID_SPAN_ATTR = "weave.eval.run_id"
EVAL_PREDICT_AND_SCORE_CALL_ID_SPAN_ATTR = "weave.eval.predict_and_score_call_id"
EVAL_PROJECT_ID_SPAN_ATTR = "weave.eval.project_id"
EVAL_KIND_SPAN_ATTR = "weave.eval.kind"
EVAL_ROW_DIGEST_SPAN_ATTR = "weave.eval.row_digest"
EVAL_EXAMPLE_ID_SPAN_ATTR = "weave.eval.example_id"
EVAL_TRIAL_INDEX_SPAN_ATTR = "weave.eval.trial_index"
EVAL_EVALUATION_NAME_SPAN_ATTR = "weave.eval.evaluation_name"
