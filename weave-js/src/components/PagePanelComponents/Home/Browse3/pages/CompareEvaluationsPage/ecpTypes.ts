/**
 * Contains the primary data definition for the Evaluation Comparison Page. Note:
 * `ecpState.ts` contains the state definition for the Evaluation Comparison Page.
 *
 * The `EvaluationComparisonData` fully defines a normalized data structure for the
 * Comparing Evaluations.
 */
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';

export type EvaluationComparisonData = {
  // Entity and Project are constant across all calls
  entity: string;
  project: string;

  // Evaluations are the Weave Objects that define the evaluation itself
  evaluations: {
    [objectRef: string]: EvaluationObj;
  };

  // EvaluationCalls are the specific calls of an evaluation.
  evaluationCalls: {
    [callId: string]: EvaluationCall;
  };

  // Inputs are the intersection of all inputs used in the evaluations.
  // Note, we are able to "merge" the same input digest even if it is
  // used in different evaluations.
  inputs: {
    [rowDigest: string]: DatasetRow;
  };

  // Models are the Weave Objects used to define the model logic and properties.
  models: {
    [modelRef: string]: ModelObj;
  };

  // ResultRows are the actual results of running the evaluation against
  // the inputs.
  resultRows: {
    // Each rowDigest is a unique identifier for the input data.
    [rowDigest: string]: {
      // Each RowDigest is further broken down by the evaluations that
      // used the input.
      evaluations: {
        [evaluationCallId: string]: {
          // Each evaluation is further broken down by the predictAndScore
          // calls that were made. (The case where this is more than 1 is
          // when the evaluation is using multiple trials)
          predictAndScores: {
            [predictAndScoreCallId: string]: PredictAndScoreCall;
          };
        };
      };
    };
  };

  // ScoreMetrics define the metrics that are associated on each individual prediction
  scoreMetrics: MetricDefinitionMap;

  // SummaryMetrics define the metrics that are associated with the evaluation as a whole
  // often aggregated from the scoreMetrics.
  summaryMetrics: MetricDefinitionMap;
};

/**
 * The EvaluationObj is the primary object that defines the evaluation itself.
 */
type EvaluationObj = {
  ref: string;
  datasetRef: string;
  scorerRefs: string[];
  entity: string;
  project: string;
};

/**
 * The EvaluationCall is the specific call of an evaluation.
 */
export type EvaluationCall = {
  callId: string;
  evaluationRef: string;
  modelRef: string;
  name: string;
  color: string;
  summaryMetrics: MetricResultMap;
};

/**
 * The DatasetRow is the primary object that defines the input data.
 */
type DatasetRow = {
  digest: string;
  val: any;
};

/**
 * The ModelObj is the primary object that defines the model logic and properties.
 */
type ModelObj = {
  ref: string;
  predictOpRef: string;
  entity: string;
  project: string;
  properties: {[prop: string]: any};
};

/**
 * The PredictAndScoreCall is the specific call of a model prediction and scoring.
 * This is the aggregate view of the model prediction and scores for a given input.
 */
export type PredictAndScoreCall = {
  callId: string;
  exampleRef: string;
  rowDigest: string;
  modelRef: string;
  evaluationCallId: string;
  scoreMetrics: MetricResultMap;
  _rawPredictAndScoreTraceData: TraceCallSchema;
  _rawPredictTraceData?: TraceCallSchema;
};

/**
 * While not used in this file, used to differentiate between score and summary metrics.
 */
export type MetricType = 'score' | 'summary';

/**
 * A metric definition map maps metric ids to metric definitions.
 */
export type MetricDefinitionMap = {[metricId: string]: MetricDefinition};
export type SourceType = 'derived' | 'scorer'; // In the future, we can add `model_output` to capture self-reported model metrics
export type MetricDefinition = {
  metricSubPath: string[];
  scoreType: 'binary' | 'continuous';
  source: SourceType;
  scorerOpOrObjRef?: string;
  shouldMinimize?: boolean;
  unit?: string;
};

/**
 * A result map maps metric ids to metric results.
 */
type MetricResultMap = {[metricId: string]: MetricResult};
export type MetricValueType = boolean | number;
export type MetricResult = {
  value: MetricValueType;
  sourceCallId: string;
};
