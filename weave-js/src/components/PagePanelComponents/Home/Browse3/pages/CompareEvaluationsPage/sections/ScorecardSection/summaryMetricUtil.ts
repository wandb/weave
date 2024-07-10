import {EvaluationComparisonState} from '../../ecpTypes';
import {
  adjustValueForDisplay,
  dimensionLabel,
  dimensionUnit,
  resolveDimensionValueForEvaluateCall,
} from '../../ecpUtil';

type DerivedSummaryMetric = {
  scorerRefToMetricKey: {[scorerRef: string]: string};
  metricLabel: string;
  unit: string;
  lowerIsBetter: boolean;
  evalScores: {[evalCallId: string]: number | undefined};
};

type DerivedSummaryScoreGroup = {
  evalCallIdToScorerRef: {[evalCallId: string]: string}; // multiple means we might not have apples to apples comparison
  scorerName?: string;
  metrics: {
    [metricName: string]: DerivedSummaryMetric;
  };
};

export type DerivedComparisonSummaryMetrics = {
  [scorerGroupName: string]: DerivedSummaryScoreGroup;
};

export const deriveComparisonSummaryMetrics = (
  state: EvaluationComparisonState
): DerivedComparisonSummaryMetrics => {
  const res: DerivedComparisonSummaryMetrics = {};
  Object.entries(state.data.evaluationCalls).forEach(
    ([evalCallId, evaluationCall]) => {
      Object.entries(evaluationCall.summaryMetrics).forEach(
        ([metricDimensionId, metricDimension]) => {
          const scorerMetricsDimension =
            state.data.scorerMetricDimensions[metricDimensionId];
          const derivedMetricsDimension =
            state.data.derivedMetricDimensions[metricDimensionId];
          if (scorerMetricsDimension != null) {
            const scorerRef = scorerMetricsDimension.scorerDef.scorerOpOrObjRef;
            const scorerName =
              scorerMetricsDimension.scorerDef.likelyTopLevelKeyName;
            const unit = dimensionUnit(scorerMetricsDimension, true);
            const lowerIsBetter = false;
            if (res[scorerName] == null) {
              res[scorerName] = {
                evalCallIdToScorerRef: {},
                scorerName,
                metrics: {},
              };
            }
            res[scorerName].evalCallIdToScorerRef[evalCallId] = scorerRef;

            const displayName = dimensionLabel(scorerMetricsDimension);
            if (res[scorerName].metrics[displayName] == null) {
              res[scorerName].metrics[displayName] = {
                metricLabel: displayName,
                scorerRefToMetricKey: {[scorerRef]: metricDimensionId},
                unit,
                lowerIsBetter,
                evalScores: {},
              };
            }
            if (
              res[scorerName].metrics[displayName].scorerRefToMetricKey[
                scorerRef
              ] == null
            ) {
              res[scorerName].metrics[displayName].scorerRefToMetricKey[
                scorerRef
              ] = metricDimensionId;
            }

            res[scorerName].metrics[displayName].evalScores[
              evaluationCall.callId
            ] = adjustValueForDisplay(
              resolveDimensionValueForEvaluateCall(
                scorerMetricsDimension,
                evaluationCall
              ),
              scorerMetricsDimension.scoreType === 'binary'
            );
          } else if (derivedMetricsDimension != null) {
            const scorerRef = '__DERIVED__';
            const scorerName = '';
            const unit = dimensionUnit(derivedMetricsDimension, true);
            const lowerIsBetter =
              derivedMetricsDimension.shouldMinimize ?? false;
            if (res[scorerName] == null) {
              res[scorerName] = {
                evalCallIdToScorerRef: {},
                scorerName,
                metrics: {},
              };
            }
            res[scorerName].evalCallIdToScorerRef[evalCallId] = scorerRef;

            const displayName = dimensionLabel(derivedMetricsDimension);
            if (res[scorerName].metrics[displayName] == null) {
              res[scorerName].metrics[displayName] = {
                metricLabel: displayName,
                scorerRefToMetricKey: {[scorerRef]: metricDimensionId},
                unit,
                lowerIsBetter,
                evalScores: {},
              };
            }
            if (
              res[scorerName].metrics[displayName].scorerRefToMetricKey[
                scorerRef
              ] == null
            ) {
              res[scorerName].metrics[displayName].scorerRefToMetricKey[
                scorerRef
              ] = metricDimensionId;
            }

            res[scorerName].metrics[displayName].evalScores[
              evaluationCall.callId
            ] = adjustValueForDisplay(
              resolveDimensionValueForEvaluateCall(
                derivedMetricsDimension,
                evaluationCall
              ),
              derivedMetricsDimension.scoreType === 'binary'
            );
          } else {
            throw new Error('Unknown metric dimension type');
          }
        }
      );
    }
  );
  return res;
};
