import { parseRef, WeaveObjectRef } from '../../../../../../react';
import {
  TraceCallSchema,
  TraceObjSchema,
} from '../wfReactInterface/traceServerClient';

export type EvaluationComparisonState = {
  data: EvaluationComparisonData;
  baselineEvaluationCallId: string;
  comparisonDimensions?: ComparisonDimensionsType;
  selectedInputDigest?: string;
};

type BinarySummaryScore = {
  true_count: number;
  true_fraction: number;
};

type BinaryValue = boolean;

export const isBinaryScore = (score: any): score is BinaryValue => {
  return typeof score === 'boolean';
};

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

type ContinuousValue = number;

export const isContinuousScore = (score: any): score is ContinuousValue => {
  return typeof score === 'number';
};

type SourceType = 'derived' | 'scorer' | 'model_output';
type MetricType = 'score' | 'summary';

export type MetricDefinition = {
  metricSubPath: string[];
  // TODO: Not sure if this is used anymore - should review afterwards
  // TODO: Remember to cleanup unused symbols
  scoreType: 'binary' | 'continuous';
  source: SourceType;
  scorerOpOrObjRef?: string;
  shouldMinimize?: boolean;
  unit?: string;
};

export const metricDefinitionId = (metricDef: MetricDefinition): string => {
  const path = metricDef.metricSubPath
    .map(p => {
      return p.replace('.', '\\.');
    })
    .join('.');
  if (metricDef.source === 'derived') {
    return `derived#${path}`;
  } else if (metricDef.source === 'model_output') {
    return `model_output#${path}`;
  } else if (metricDef.source === 'scorer') {
    if (metricDef.scorerOpOrObjRef == null) {
      throw new Error('scorerOpOrObjRef must be defined for scorer metric');
    }
    return `${metricDef.scorerOpOrObjRef}#${path}`;
  } else {
    throw new Error(`Unknown metric source: ${metricDef.source}`);
  }
};

// const metricIdToDefinition = (
//   data: EvaluationComparisonData,
//   scoreOrSummary: 'score' | 'summary',
//   metricId: string
// ): MetricDefinition => {
//   if (scoreOrSummary === 'score') {
//     if (!(metricId in data.scoreMetrics)) {
//       throw new Error(`Metric ID ${metricId} not found in scoreMetrics`);
//     }
//     return data.scoreMetrics[metricId];
//   } else if (scoreOrSummary === 'summary') {
//     if (!(metricId in data.summaryMetrics)) {
//       throw new Error(`Metric ID ${metricId} not found in summaryMetrics`);
//     }
//     return data.summaryMetrics[metricId];
//   } else {
//     throw new Error(`Unknown scoreOrSummary: ${scoreOrSummary}`);
//   }
// };

export type MetricValueType = BinaryValue | ContinuousValue;

export type MetricResult = {
  value: MetricValueType;
  sourceCallId: string;
};

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

type SummaryScore = BinarySummaryScore | ContinuousSummaryScore;

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
  scoreMetrics: MetricDefinitionMap;
  summaryMetrics: MetricDefinitionMap;
};

type MetricDefinitionMap = {[metricId: string]: MetricDefinition};
type MetricResultMap = {[metricId: string]: MetricResult};

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

type RangeSelection = {[evalCallId: string]: {min: number; max: number}};

export type ComparisonDimensionsType = Array<{
  metricId: string;
  rangeSelection?: RangeSelection;
}>;

export type EvaluationCall = {
  callId: string;
  name: string;
  color: string;
  evaluationRef: string;
  modelRef: string;
  summaryMetrics: MetricResultMap;
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

export const getMetricIds = (
  data: EvaluationComparisonData,
  type: MetricType,
  source: SourceType
): MetricDefinitionMap => {
  const metrics = type === 'score' ? data.scoreMetrics : data.summaryMetrics;
  return Object.fromEntries(
    Object.entries(metrics).filter(([k, v]) => v.source === source)
  );
};

export const getScoreKeyNameFromScorerRef = (scorerRef: string) => {
  const parsed = parseRef(scorerRef) as WeaveObjectRef;
  return parsed.artifactName;
};
