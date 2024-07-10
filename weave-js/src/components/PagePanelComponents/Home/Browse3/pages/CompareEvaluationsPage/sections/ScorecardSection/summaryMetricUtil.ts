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

export type CompositeSummaryMetric = {
  scorerRefToDimensionId: {[scorerRef: string]: string};
  metricLabel: string;
  unit: string;
  lowerIsBetter: boolean;
  evalScores: {[evalCallId: string]: number | undefined};
};

type CompositeSummaryScoreGroup = {
  evalCallIdToScorerRef: {[evalCallId: string]: string}; // multiple means we might not have apples to apples comparison
  scorerName: string;
  metrics: {
    [dimensionPath: string]: CompositeSummaryMetric;
  };
};

export type CompositeComparisonSummaryMetrics = {
  [scorerGroupName: string]: CompositeSummaryScoreGroup;
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

export const buildCompositeComparisonSummaryMetrics = (
  state: EvaluationComparisonState
): {
  compositeMetrics: CompositeComparisonSummaryMetrics;
  resolvePeerDimension: ResolvePeerDimensionFn;
} => {
  const compositeMetrics: CompositeComparisonSummaryMetrics = {};
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
            if (compositeMetrics[dimKeys.scorerGroupName] == null) {
              compositeMetrics[dimKeys.scorerGroupName] = {
                evalCallIdToScorerRef: {},
                scorerName: dimKeys.scorerGroupName,
                metrics: {},
              };
            }
            compositeMetrics[dimKeys.scorerGroupName].evalCallIdToScorerRef[
              evalCallId
            ] = scorerRef;
            if (
              compositeMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ] == null
            ) {
              compositeMetrics[dimKeys.scorerGroupName].metrics[
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
              compositeMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ].scorerRefToDimensionId[scorerRef] == null
            ) {
              compositeMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ].scorerRefToDimensionId[scorerRef] = metricDimensionId;
            }

            compositeMetrics[dimKeys.scorerGroupName].metrics[
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
            if (compositeMetrics[dimKeys.scorerGroupName] == null) {
              compositeMetrics[dimKeys.scorerGroupName] = {
                evalCallIdToScorerRef: {},
                scorerName: dimKeys.scorerGroupName,
                metrics: {},
              };
            }
            compositeMetrics[dimKeys.scorerGroupName].evalCallIdToScorerRef[
              evalCallId
            ] = scorerRef;

            if (
              compositeMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ] == null
            ) {
              compositeMetrics[dimKeys.scorerGroupName].metrics[
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
              compositeMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ].scorerRefToDimensionId[scorerRef] == null
            ) {
              compositeMetrics[dimKeys.scorerGroupName].metrics[
                dimKeys.dimensionPath
              ].scorerRefToDimensionId[scorerRef] = metricDimensionId;
            }

            compositeMetrics[dimKeys.scorerGroupName].metrics[
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
    const scorerGroup = compositeMetrics[scorerGroupName];
    const scorerRef = scorerGroup.evalCallIdToScorerRef[evalCallId];
    const dimensionId =
      compositeMetrics[scorerGroupName].metrics[dimensionPath]
        .scorerRefToDimensionId[scorerRef];
    return (
      state.data.derivedMetricDimensions[dimensionId] ??
      state.data.scorerMetricDimensions[dimensionId]
    );
  };

  return {compositeMetrics, resolvePeerDimension};
};
