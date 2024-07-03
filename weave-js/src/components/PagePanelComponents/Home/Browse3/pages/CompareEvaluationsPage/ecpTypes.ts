import {
  TraceCallSchema,
  TraceObjSchema,
} from '../wfReactInterface/traceServerClient';

export type EvaluationComparisonState = {
  data: EvaluationComparisonData;
  baselineEvaluationCallId: string;
  comparisonDimension?: EvaluationMetricDimension;
  rangeSelection: RangeSelection;
  selectedInputDigest?: string;
};
type BinarySummaryScore = {
  true_count: number;
  true_fraction: number;
};
type BinaryScore = boolean;
export const isBinaryScore = (score: any): score is BinaryScore => {
  return typeof score === 'boolean';
}


type ContinuousSummaryScore = {
  mean: number;
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

type ContinuousScore = number;

export const isContinuousScore = (score: any): score is ContinuousScore => {
  return typeof score === 'number';
};


export type ScorerDefinition = {
  scorerOpOrObjRef: string;
  likelyTopLevelKeyName: string;
}

export type ScorerMetricDimension = {
  dimensionType: 'scorerMetric';
  scorerDef: ScorerDefinition;
  metricSubPath: string[];
  scoreType: 'binary' | 'continuous';
};

export type DerivedMetricDefinition = {
  dimensionType: 'derivedMetric';
  derivedMetricName: string;
  scoreType: 'binary' | 'continuous';
  shouldMinimize?: boolean;
  unit?: string;
};

export const isScorerMetricDimension = (
  dim: EvaluationMetricDimension
): dim is ScorerMetricDimension => {
  return typeof dim === 'object' &&dim.dimensionType === 'scorerMetric';
}

export const isDerivedMetricDefinition = (
  dim: EvaluationMetricDimension
): dim is DerivedMetricDefinition => {
  return typeof dim === 'object' && dim.dimensionType === 'derivedMetric';
}

export type EvaluationMetricDimension = ScorerMetricDimension | DerivedMetricDefinition

export type EvaluationEvaluateCallSchema = TraceCallSchema & {
  inputs: TraceCallSchema['inputs'] & {
    self: string;
    model: string;
  };
  output: TraceCallSchema['output'] & {
    [scorer: string]: {
      [score: string]: SummaryScore;
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


export type SummaryScore = BinarySummaryScore | ContinuousSummaryScore
export type EvaluationCall = {
  callId: string;
  name: string;
  color: string;
  evaluationRef: string;
  modelRef: string;
  summaryMetrics: {
    [metricDimensionId: string]: SummaryScore;
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
  properties: {[prop: string]: any};
  project: string;
  entity: string;
  _rawModelObject: TraceObjSchema;
};

export type ScoreType = BinaryScore | ContinuousScore
export type MetricResult = {
  value: ScoreType;
  sourceCall: {
    callId: string;
    _rawScoreTraceData: TraceCallSchema;
  };
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
  derivedMetricDimensions: {[metricDimensionId: string]: DerivedMetricDefinition}
  scorerMetricDimensions: {[metricDimensionId: string]: ScorerMetricDimension}
};
export type PredictAndScoreCall = {
  callId: string;
  firstExampleRef: string;
  rowDigest: string;
  modelRef: string;
  evaluationCallId: string;
  _legacy_predictCall?: {
    callId: string;
    output: any;
    latencyMs: number;
    totalUsageTokens: number;
    _rawPredictTraceData: TraceCallSchema;
  };
  scorerMetrics: {
    [metricDimensionId: string]: MetricResult;
  };
  derivedMetrics: {
    [metricDimensionId: string]: MetricResult;
  };
  _rawPredictAndScoreTraceData: TraceCallSchema;
};export type RangeSelection = { [evalCallId: string]: { min: number; max: number; }; };

