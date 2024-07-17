import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {
  BinarySummaryScore,
  BinaryValue,
  ContinuousSummaryScore,
  ContinuousValue,
  EvaluationCall,
  EvaluationComparisonData,
  MetricDefinition,
  MetricDefinitionMap,
  MetricResult,
  MetricValueType,
  PredictAndScoreCall,
  SourceType,
} from './ecpTypes';

export const adjustValueForDisplay = (
  value: number | boolean | undefined,
  isBooleanAggregate?: boolean
): number | undefined => {
  if (value === undefined) {
    return undefined;
  }
  if (isBinaryScore(value)) {
    return value ? 100 : 0;
  } else if (isBooleanAggregate) {
    return value * 100;
  } else {
    return value;
  }
};

export const flattenedDimensionPath = (dim: MetricDefinition): string => {
  const paths = [...dim.metricSubPath];
  if (dim.source === 'scorer') {
    if (dim.scorerOpOrObjRef == null) {
      throw new Error('scorerOpOrObjRef must be defined for scorer metric');
    }
    paths.unshift(getScoreKeyNameFromScorerRef(dim.scorerOpOrObjRef));
  }
  return paths.join('.');
};

export const dimensionUnit = (
  dim: MetricDefinition,
  isAggregate?: boolean
): string => {
  if (isAggregate && dim.scoreType === 'binary') {
    return '%';
  }
  return dim.unit ?? '';
};

export const dimensionShouldMinimize = (dim: MetricDefinition): boolean => {
  return dim.shouldMinimize ?? false;
};

export const resolveScoreMetricResultForPASCall = (
  dim: MetricDefinition,
  pasCall: PredictAndScoreCall
): MetricResult | undefined => {
  const metricId = metricDefinitionId(dim);
  return pasCall.scoreMetrics[metricId];
};

export const resolveScoreMetricValueForPASCall = (
  dim: MetricDefinition,
  pasCall: PredictAndScoreCall
): MetricValueType | undefined => {
  const metricResult = resolveScoreMetricResultForPASCall(dim, pasCall);
  if (metricResult) {
    return metricResult.value;
  }
  return undefined;
};

export const resolveSummaryMetricResultForEvaluateCall = (
  dim: MetricDefinition,
  evaluateCall: EvaluationCall
): MetricResult | undefined => {
  return evaluateCall.summaryMetrics[metricDefinitionId(dim)];
};

export const resolveSummaryMetricValueForEvaluateCall = (
  dim: MetricDefinition,
  evaluateCall: EvaluationCall
): MetricValueType | undefined => {
  const score = resolveSummaryMetricResultForEvaluateCall(dim, evaluateCall);
  if (score) {
    return score.value;
  }
  return undefined;
};

export type MetricType = 'score' | 'summary';
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

export const metricDefinitionId = (metricDef: MetricDefinition): string => {
  const path = metricDef.metricSubPath
    .map(p => {
      return p.replace('.', '\\.');
    })
    .join('.');
  if (metricDef.source === 'derived') {
    return `derived#${path}`;
  } else if (metricDef.source === 'scorer') {
    if (metricDef.scorerOpOrObjRef == null) {
      throw new Error('scorerOpOrObjRef must be defined for scorer metric');
    }
    return `${metricDef.scorerOpOrObjRef}#${path}`;
  } else {
    throw new Error(`Unknown metric source: ${metricDef.source}`);
  }
};
export const isBinaryScore = (score: any): score is BinaryValue => {
  return typeof score === 'boolean';
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

export const isContinuousScore = (score: any): score is ContinuousValue => {
  return typeof score === 'number';
};
