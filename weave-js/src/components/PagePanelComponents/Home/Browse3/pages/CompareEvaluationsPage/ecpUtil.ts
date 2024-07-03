import { EvaluationCall, EvaluationMetricDimension, isBinarySummaryScore, isContinuousSummaryScore, isDerivedMetricDefinition, isScorerMetricDimension,MetricResult, PredictAndScoreCall, ScoreType, SummaryScore } from './ecpTypes';

export const dimensionLabel = (dim: EvaluationMetricDimension): string => {
  if (isScorerMetricDimension(dim)) {
    const parts = [dim.scorerDef.likelyTopLevelKeyName , ...dim.metricSubPath];
    return parts.join('.');
  } else if (isDerivedMetricDefinition(dim)) {
    return dim.derivedMetricName;
  } else {
    throw new Error('Unknown dimension type');
  }
};

export const dimensionUnit = (dim: EvaluationMetricDimension): string => {
  if (isScorerMetricDimension(dim)) {
    return '';
  } else if (isDerivedMetricDefinition(dim)) {
    return dim.unit ?? '';
  } else {
    throw new Error('Unknown dimension type');
  }
};

export const dimensionShouldMinimize = (dim: EvaluationMetricDimension): boolean => {
  if (isScorerMetricDimension(dim)) {
    return false
  } else if (isDerivedMetricDefinition(dim)) {
    return dim.shouldMinimize ?? false;
  } else {
    throw new Error('Unknown dimension type');
  }
};



export const dimensionId = (dim: EvaluationMetricDimension): string => {
  if (isScorerMetricDimension(dim)) {
    return dim.scorerDef.scorerOpOrObjRef + '#' + dim.metricSubPath.join('.');
  } else if (isDerivedMetricDefinition(dim)) {
    return dim.derivedMetricName;
  } else {
    throw new Error('Unknown dimension type');
  }
};
export const resolveDimensionMetricResultForPASCall = (
  dim: EvaluationMetricDimension,
  pasCall: PredictAndScoreCall
): MetricResult | undefined => {
  if (isScorerMetricDimension(dim)) {
    return pasCall.scorerMetrics[dimensionId(dim)];
  } else if (isDerivedMetricDefinition(dim)) {
    return pasCall.derivedMetrics[dimensionId(dim)];
  } else {
    throw new Error(`Unknown metric dimension type: ${dim}`);
  }
};


export const resolveDimensionValueForPASCall = (
  dim: EvaluationMetricDimension,
  pasCall: PredictAndScoreCall
): ScoreType | undefined => {
  const metricResult = resolveDimensionMetricResultForPASCall(dim, pasCall);
  if (metricResult) {
    return metricResult.value;
  }
  return undefined;
};


export const resolveDimensionSummaryScoreForEvaluateCall = (
  dim: EvaluationMetricDimension,
  evaluateCall: EvaluationCall
): SummaryScore | undefined => {
  return evaluateCall.summaryMetrics[dimensionId(dim)];
};


export const resolveDimensionValueForEvaluateCall = (
  dim: EvaluationMetricDimension,
  evaluateCall: EvaluationCall
): number | undefined => {
  const score = resolveDimensionSummaryScoreForEvaluateCall(dim, evaluateCall);
  if (isBinarySummaryScore(score)) {
    return score.true_fraction;
  } else if (isContinuousSummaryScore(score)) {
    return score.mean;
  }
  return undefined;
}
