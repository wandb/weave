import {
  EvaluationComparisonState,
  EvaluationMetricDimension,
  isDerivedMetricDefinition,
  isScorerMetricDimension,
} from '../../ecpTypes';
import {
  adjustValueForDisplay,
  dimensionUnit,
  flattenedDimensionPath,
  resolveDimensionValueForEvaluateCall,
} from '../../ecpUtil';

export const DERIVED_SCORER_REF = '__DERIVED__';

type DerivedSummaryMetric = {
  scorerRefToDimensionId: {[scorerRef: string]: string};
  metricLabel: string;
  unit: string;
  lowerIsBetter: boolean;
  evalScores: {[evalCallId: string]: number | undefined};
};

type DerivedSummaryScoreGroup = {
  evalCallIdToScorerRef: {[evalCallId: string]: string}; // multiple means we might not have apples to apples comparison
  scorerName: string;
  metrics: {
    [dimensionPath: string]: DerivedSummaryMetric;
  };
};

export type DerivedComparisonSummaryMetrics = {
  [scorerGroupName: string]: DerivedSummaryScoreGroup;
};

export const dimensionKeys = (
  dimension: EvaluationMetricDimension
): {
  scorerGroupName: string;
  dimensionPath: string;
} => {
  if (isDerivedMetricDefinition(dimension)) {
    return {
      scorerGroupName: DERIVED_SCORER_REF,
      dimensionPath: dimension.derivedMetricName,
    };
  } else if (isScorerMetricDimension(dimension)) {
    return {
      scorerGroupName: dimension.scorerDef.likelyTopLevelKeyName,
      dimensionPath: flattenedDimensionPath(dimension),
    };
  } else {
    throw new Error('Unknown dimension type');
  }
};

export type ResolvePeerDimensionFn = (
  evalCallId: string,
  peerDimension: EvaluationMetricDimension
) => EvaluationMetricDimension | undefined;

export const deriveComparisonSummaryMetrics = (
  state: EvaluationComparisonState
): {
  derivedMetrics: DerivedComparisonSummaryMetrics;
  resolvePeerDimension: ResolvePeerDimensionFn;
} => {
  const derivedMetrics: DerivedComparisonSummaryMetrics = {};
  Object.entries(state.data.evaluationCalls).forEach(
    ([evalCallId, evaluationCall]) => {
      Object.entries(evaluationCall.summaryMetrics).forEach(
        ([metricDimensionId, metricDimension]) => {
          const scorerMetricsDimension =
            state.data.scorerMetricDimensions[metricDimensionId];
          const derivedMetricsDimension =
            state.data.derivedMetricDimensions[metricDimensionId];
          if (scorerMetricsDimension != null) {
            const dimKeys = dimensionKeys(scorerMetricsDimension);
            const scorerRef = scorerMetricsDimension.scorerDef.scorerOpOrObjRef;
            const unit = dimensionUnit(scorerMetricsDimension, true);
            const lowerIsBetter = false;
            if (derivedMetrics[dimKeys.scorerGroupName] == null) {
              derivedMetrics[dimKeys.scorerGroupName] = {
                evalCallIdToScorerRef: {},
                scorerName: dimKeys.scorerGroupName,
                metrics: {},
              };
            }
            derivedMetrics[dimKeys.scorerGroupName].evalCallIdToScorerRef[
              evalCallId
            ] = scorerRef;
            if (
              derivedMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ] == null
            ) {
              derivedMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ] = {
                metricLabel: dimKeys.dimensionPath,
                scorerRefToDimensionId: {[scorerRef]: metricDimensionId},
                unit,
                lowerIsBetter,
                evalScores: {},
              };
            }
            if (
              derivedMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ].scorerRefToDimensionId[scorerRef] == null
            ) {
              derivedMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ].scorerRefToDimensionId[scorerRef] = metricDimensionId;
            }

            derivedMetrics[dimKeys.scorerGroupName].metrics[
              dimKeys.dimensionPath
            ].evalScores[evaluationCall.callId] = adjustValueForDisplay(
              resolveDimensionValueForEvaluateCall(
                scorerMetricsDimension,
                evaluationCall
              ),
              scorerMetricsDimension.scoreType === 'binary'
            );
          } else if (derivedMetricsDimension != null) {
            const dimKeys = dimensionKeys(derivedMetricsDimension);
            const scorerRef = DERIVED_SCORER_REF;
            const unit = dimensionUnit(derivedMetricsDimension, true);
            const lowerIsBetter =
              derivedMetricsDimension.shouldMinimize ?? false;
            if (derivedMetrics[dimKeys.scorerGroupName] == null) {
              derivedMetrics[dimKeys.scorerGroupName] = {
                evalCallIdToScorerRef: {},
                scorerName: dimKeys.scorerGroupName,
                metrics: {},
              };
            }
            derivedMetrics[dimKeys.scorerGroupName].evalCallIdToScorerRef[
              evalCallId
            ] = scorerRef;

            if (
              derivedMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ] == null
            ) {
              derivedMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ] = {
                metricLabel: dimKeys.dimensionPath,
                scorerRefToDimensionId: {[scorerRef]: metricDimensionId},
                unit,
                lowerIsBetter,
                evalScores: {},
              };
            }
            if (
              derivedMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ].scorerRefToDimensionId[scorerRef] == null
            ) {
              derivedMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ].scorerRefToDimensionId[scorerRef] = metricDimensionId;
            }

            derivedMetrics[dimKeys.scorerGroupName].metrics[
              dimKeys.dimensionPath
            ].evalScores[evaluationCall.callId] = adjustValueForDisplay(
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

  const resolvePeerDimension = (
    evalCallId: string,
    peerDimension: EvaluationMetricDimension
  ): EvaluationMetricDimension | undefined => {
    // Given the Target Dimension, get the scorer group & metricName -> basically gets the common identifier
    // Given the scorer group & the eval id, get the scorerRef       -> resolve part 1
    // Given the scorer group & the metric name, get the DerivedSummaryMetric -> resolve part 2 -> found common metric
    // Given the DerivedSummaryMetric & scorerRef, get the dimension id -> lookup specific dimension
    // Lookup the dimension from the state.
    const {scorerGroupName, dimensionPath} = dimensionKeys(peerDimension);
    const scorerGroup = derivedMetrics[scorerGroupName];
    const scorerRef = scorerGroup.evalCallIdToScorerRef[evalCallId];
    const dimensionId =
      derivedMetrics[scorerGroupName].metrics[dimensionPath]
        .scorerRefToDimensionId[scorerRef];
    return (
      state.data.derivedMetricDimensions[dimensionId] ??
      state.data.scorerMetricDimensions[dimensionId]
    );
  };

  return {derivedMetrics, resolvePeerDimension};
};
