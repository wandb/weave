import {EvaluationComparisonState} from '../../ecpTypes';
import {
  dimensionLabel,
  dimensionShouldMinimize,
  dimensionUnit,
  resolveDimensionValueForEvaluateCall,
} from '../../ecpUtil';

type SummaryPlotsLegacyComparisonMetric = {
  path: string;
  unit: string;
  lowerIsBetter: boolean;
  values: {[callId: string]: number | undefined};
};

export const summaryMetrics = (
  state: EvaluationComparisonState
): SummaryPlotsLegacyComparisonMetric[] => {
  const results: SummaryPlotsLegacyComparisonMetric[] = [];
  const allEntries = [
    ...Object.entries(state.data.scorerMetricDimensions),
    ...Object.entries(state.data.derivedMetricDimensions),
  ];
  allEntries.forEach(([metricId, metric]) => {
    results.push({
      path: dimensionLabel(metric),
      unit: dimensionUnit(metric),
      lowerIsBetter: dimensionShouldMinimize(metric),
      values: Object.fromEntries(
        Object.entries(state.data.evaluationCalls).map(([callId, call]) => [
          callId,
          resolveDimensionValueForEvaluateCall(metric, call),
        ])
      ),
    });
  });

  return results;
};
