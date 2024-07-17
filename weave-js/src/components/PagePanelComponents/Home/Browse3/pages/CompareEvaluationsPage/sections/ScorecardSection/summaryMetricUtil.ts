import {EvaluationComparisonState, MetricDefinition} from '../../ecpTypes';
import {
  adjustValueForDisplay,
  dimensionUnit,
  flattenedDimensionPath,
  resolveSummaryMetricValueForEvaluateCall,
} from '../../ecpUtil';

export const DERIVED_SCORER_REF = '__DERIVED__';
export const OUTPUT_SCORER_REF = '__DERIVED__';

export type CompositeSummaryMetric = {
  scorerRefToDimensionId: {[scorerRef: string]: string};
  metricLabel: string;
  unit: string;
  lowerIsBetter: boolean;
  evalScores: {[evalCallId: string]: number | undefined};
};

export type CompositeSummaryScoreGroup = {
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
  dimension: MetricDefinition
): {
  scorerGroupName: string;
  dimensionPath: string;
} => {
  let scorerGroupName = '';
  if (dimension.source === 'derived') {
    scorerGroupName = DERIVED_SCORER_REF;
  } else if (dimension.source === 'model_output') {
    scorerGroupName = OUTPUT_SCORER_REF;
  } else {
    scorerGroupName = dimension.metricSubPath[0];
  }
  return {
    scorerGroupName,
    dimensionPath: flattenedDimensionPath(dimension),
  };
};

export type ResolvePeerDimensionFn = (
  evalCallId: string,
  peerDimension: MetricDefinition
) => MetricDefinition | undefined;

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
        ([metricId, metricDimension]) => {
          const scorerMetricsDimension = state.data.summaryMetrics[metricId];
          // const derivedMetricsDimension =
          //   state.data.derivedMetricDimensions[metricId];
          if (scorerMetricsDimension != null) {
            const dimKeys = dimensionKeys(scorerMetricsDimension);
            let scorerRef = '';
            if (scorerMetricsDimension.source === 'model_output') {
              scorerRef = OUTPUT_SCORER_REF;
            } else if (scorerMetricsDimension.source === 'derived') {
              scorerRef = DERIVED_SCORER_REF;
            } else if (scorerMetricsDimension.source === 'scorer') {
              if (scorerMetricsDimension.scorerOpOrObjRef == null) {
                throw new Error(
                  'scorerOpOrObjRef must be defined for scorer metric'
                );
              }
              scorerRef = scorerMetricsDimension.scorerOpOrObjRef;
            } else {
              throw new Error(
                `Unknown metric source: ${scorerMetricsDimension.source}`
              );
            }
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
                scorerRefToDimensionId: {[scorerRef]: metricId},
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
              ].scorerRefToDimensionId[scorerRef] = metricId;
            }

            compositeMetrics[dimKeys.scorerGroupName].metrics[
              dimKeys.dimensionPath
            ].evalScores[evaluationCall.callId] = adjustValueForDisplay(
              resolveSummaryMetricValueForEvaluateCall(
                scorerMetricsDimension,
                evaluationCall
              ),
              scorerMetricsDimension.scoreType === 'binary'
            );
            // } else if (derivedMetricsDimension != null) {
            //   const dimKeys = dimensionKeys(derivedMetricsDimension);
            //   const scorerRef = DERIVED_SCORER_REF;
            //   const unit = dimensionUnit(derivedMetricsDimension, true);
            //   const lowerIsBetter =
            //     derivedMetricsDimension.shouldMinimize ?? false;
            //   if (compositeMetrics[dimKeys.scorerGroupName] == null) {
            //     compositeMetrics[dimKeys.scorerGroupName] = {
            //       evalCallIdToScorerRef: {},
            //       scorerName: dimKeys.scorerGroupName,
            //       metrics: {},
            //     };
            //   }
            //   compositeMetrics[dimKeys.scorerGroupName].evalCallIdToScorerRef[
            //     evalCallId
            //   ] = scorerRef;

            //   if (
            //     compositeMetrics[dimKeys.scorerGroupName].metrics[
            //       dimKeys.dimensionPath
            //     ] == null
            //   ) {
            //     compositeMetrics[dimKeys.scorerGroupName].metrics[
            //       dimKeys.dimensionPath
            //     ] = {
            //       metricLabel: dimKeys.dimensionPath,
            //       scorerRefToDimensionId: {[scorerRef]: metricId},
            //       unit,
            //       lowerIsBetter,
            //       evalScores: {},
            //     };
            //   }
            //   if (
            //     compositeMetrics[dimKeys.scorerGroupName].metrics[
            //       dimKeys.dimensionPath
            //     ].scorerRefToDimensionId[scorerRef] == null
            //   ) {
            //     compositeMetrics[dimKeys.scorerGroupName].metrics[
            //       dimKeys.dimensionPath
            //     ].scorerRefToDimensionId[scorerRef] = metricId;
            //   }

            //   compositeMetrics[dimKeys.scorerGroupName].metrics[
            //     dimKeys.dimensionPath
            //   ].evalScores[evaluationCall.callId] = adjustValueForDisplay(
            //     resolveSummaryMetricValueForEvaluateCall(
            //       derivedMetricsDimension,
            //       evaluationCall
            //     ),
            //     derivedMetricsDimension.scoreType === 'binary'
            //   );
          } else {
            throw new Error('Unknown metric dimension type');
          }
        }
      );
    }
  );

  const resolvePeerDimension = (
    evalCallId: string,
    peerDimension: MetricDefinition
  ): MetricDefinition | undefined => {
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
      state.data.summaryMetrics[dimensionId] ??
      state.data.scoreMetrics[dimensionId]
    ); // TODO: Verify this fallback is correct
  };

  return {compositeMetrics, resolvePeerDimension};
};
