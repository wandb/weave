import { TraceCallSchema, TraceObjSchema } from '../wfReactInterface/traceServerClient';
import {RangeSelection} from './initialize';

export type EvaluationComparisonState = {
  data: EvaluationComparisonData;
  baselineEvaluationCallId: string;
  comparisonDimension: ScoreDimension;
  rangeSelection: RangeSelection;
  selectedInputDigest?: string;
};
type BinarySummaryScore = {
  true_count: number;
  true_fraction: number;
};
type ContinuousSummaryScore = {
  mean: number;
};

export type ScoreDimension = {
  scorerRef: string;
  scoreKeyPath: string;
  scoreType: 'binary' | 'continuous';
  minimize?: boolean;
};

export type EvaluationEvaluateCallSchema = TraceCallSchema & {
  inputs: TraceCallSchema['inputs'] & {
    self: string;
    model: string;
  };
  output: TraceCallSchema['output'] & {
    [scorer: string]: {
      [score: string]: BinarySummaryScore | ContinuousSummaryScore;
    };
  } & {
    model_latency: ContinuousSummaryScore;
  };
  summary: TraceCallSchema['summary'] & {
    usage?: {
      [model: string]: {
        requests?: number;
        completion_tokens?: number;
        prompt_tokens?: number;
        total_tokens?: number;
      };
    };
  };
};
export type ComparisonMetric = {
  path: string;
  unit: string;
  lowerIsBetter: boolean;
  values: { [callId: string]: number; };
};

export const isBinarySummaryScore = (
  score: any
): score is BinarySummaryScore => {
  return (
    typeof score === 'object' &&
    score != null &&
    'true_count' in score &&
    'true_fraction' in score
  );
};

export const isContinuousSummaryScore = (
  score: any
): score is ContinuousSummaryScore => {
  return typeof score === 'object' && score != null && 'mean' in score;
};
type EvaluationCall = {
  callId: string;
  name: string;
  color: string;
  evaluationRef: string;
  modelRef: string;
  scores: {
    [scoreName: string]: {
      [path: string]: BinarySummaryScore | ContinuousSummaryScore;
    };
  };
  _rawEvaluationTraceData: EvaluationEvaluateCallSchema;
};
type EvaluationObj = {
  ref: string;
  datasetRef: string;
  scorerRefs: string[];
  project: string;
  entity: string;
  _rawEvaluationObject: TraceObjSchema;
};
type DatasetRow = {
  digest: string;
  val: any;
};
type ModelObj = {
  ref: string;
  predictOpRef: string;
  properties: { [prop: string]: any; };
  project: string;
  entity: string;
  _rawModelObject: TraceObjSchema;
};
type ScoreResults = {
  callId: string;
  results: { [path: string]: number | boolean; };
  _rawScoreTraceData: TraceCallSchema;
};

export type EvaluationComparisonData = {
  entity: string;
  project: string;
  evaluationCalls: {
    [callId: string]: EvaluationCall;
  };
  evaluations: {
    [objectRef: string]: EvaluationObj;
  };
  inputs: {
    [rowDigest: string]: DatasetRow;
  };
  models: {
    [modelRef: string]: ModelObj;
  };
  resultRows: {
    [rowDigest: string]: {
      evaluations: {
        [evaluationCallId: string]: {
          predictAndScores: {
            [predictAndScoreCallId: string]: PredictAndScoreCall;
          };
        };
      };
    };
  };
};
type PredictAndScoreCall = {
  callId: string;
  firstExampleRef: string;
  rowDigest: string;
  modelRef: string;
  evaluationCallId: string;
  predictCall?: {
    callId: string;
    output: any;
    latencyMs: number;
    totalUsageTokens: number;
    _rawPredictTraceData: TraceCallSchema;
  };
  scores: {
    [scorerRef: string]: ScoreResults;
  };
  _rawPredictAndScoreTraceData: TraceCallSchema;
};

