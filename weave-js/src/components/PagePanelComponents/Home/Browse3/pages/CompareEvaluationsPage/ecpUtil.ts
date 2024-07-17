import {
  EvaluationCall,
  getScoreKeyNameFromScorerRef,
  isBinaryScore,
  MetricDefinition,
  metricDefinitionId,
  MetricResult,
  MetricValueType,
  PredictAndScoreCall,
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
