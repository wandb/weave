/**
 * This file contains a few utilities for working with the
 * `MetricDefinitionMap`s in the `EvaluationComparisonData` object. The
 * `EvaluationComparisonData` state is a normalized representation of the data,
 * which is good for not duplicating data, but does present some challenges when
 * trying to build the final rendering of the data. As an application-specific
 * consideration, when comparing evaluations, metrics can be represented by the
 * `CompositeScoreMetricGroup` form - where there is a top-level group for each
 * "scorer", then a list of metrics that are associated with that scorer.
 * Importantly, different versions of a scorer might be used in different
 * evaluations, so we need to be able to resolve the correct metric for a given
 * evaluation.
 */
import _ from 'lodash';

import {EvaluationComparisonData, MetricDefinition} from './ecpTypes';
import {MetricType} from './ecpTypes';
import {getScoreKeyNameFromScorerRef} from './ecpUtil';
import {flattenedDimensionPath} from './ecpUtil';

export const DERIVED_SCORER_REF_PLACEHOLDER = '__DERIVED__';

/**
 * A `CompositeScoreMetrics` object is a map from a group name to a
 * `CompositeScoreMetricGroup`. The group name is the key used to group metrics
 * together, and the `CompositeScoreMetricGroup` contains the metrics associated
 * with that group.
 */
export type CompositeScoreMetrics = {
  // `groupName` is most often the "Scorer" name (unversioned)
  // But also includes a placeholder for derived metrics
  [groupName: string]: CompositeScoreMetricGroup;
};

type CompositeScoreMetricGroup = {
  // Contains a list of scorerRefs that are associated with this group
  // Most typically these are all versions of the same scorer used
  // across different evaluations
  scorerRefs: string[];

  // Contains a map from a flattened keyPath to a `CompositeSummaryMetricGroupKeyPath`
  metrics: {
    [keyPath: string]: CompositeSummaryMetricGroupForKeyPath;
  };
};

/**
 * A `CompositeSummaryMetricGroupForKeyPath` defines the metrics associated with
 * a given keyPath. The `scorerAgnosticMetricDef` is the metric definition that
 * is not specific to any scorer, and the `scorerRefs` is a map from scorerRefs
 * to the metrics associated with that scorer. In an ideal case, there should be
 * one scorerRef per keyPath, but this is not guaranteed.
 */
export type CompositeSummaryMetricGroupForKeyPath = {
  // Useful for deriving properties about the metric that are not
  // specific to a scorer
  scorerAgnosticMetricDef: Omit<MetricDefinition, 'scorerOpOrObjRef'>;
  scorerRefs: {
    // Contains each of the versions of the scorer that are associated
    // with this metric
    [scoreRef: string]: {
      // Contains the list of evaluation call ids that are associated with
      // this scorer
      evalCallIds: string[];
      // Contains the metric definition
      metric: MetricDefinition;
    };
  };
};

/**
 * Builds a `CompositeScoreMetrics` object from the `EvaluationComparisonData`.
 * This is the primary utility for converting the normalized data into a form
 * that is more useful for rendering the data.
 */
export const buildCompositeMetricsMap = (
  data: EvaluationComparisonData,
  mType: MetricType
): CompositeScoreMetrics => {
  const composite: CompositeScoreMetrics = {};

  // Get the metric definition map based on the metric type
  let metricDefinitionMap;
  if (mType === 'score') {
    metricDefinitionMap = data.scoreMetrics;
  } else if (mType === 'summary') {
    metricDefinitionMap = data.summaryMetrics;
  } else {
    throw new Error(`Invalid metric type: ${mType}`);
  }

  // Loop through each metric definition and build the composite map
  Object.entries(metricDefinitionMap).forEach(([metricId, metric]) => {
    const groupName = groupNameForMetric(metric);
    const ref = refForMetric(metric);

    if (!composite[groupName]) {
      composite[groupName] = {
        scorerRefs: [],
        metrics: {},
      };
    }
    const metricGroup = composite[groupName];
    if (!metricGroup.scorerRefs.includes(ref)) {
      metricGroup.scorerRefs.push(ref);
    }

    const keyPath = flattenedDimensionPath(metric);

    if (!metricGroup.metrics[keyPath]) {
      metricGroup.metrics[keyPath] = {
        scorerAgnosticMetricDef: _.omit(metric, 'scorerOpOrObjRef'),
        scorerRefs: {},
      };
    }

    const metricKeyPath = metricGroup.metrics[keyPath];

    if (!metricKeyPath.scorerRefs[ref]) {
      metricKeyPath.scorerRefs[ref] = {
        evalCallIds: [],
        metric,
      };
    }

    const evals = Object.values(data.evaluationCalls)
      .filter(evaluationCall => {
        const evaluation = data.evaluations[evaluationCall.evaluationRef];
        return (
          metric.scorerOpOrObjRef == null ||
          evaluation.scorerRefs.includes(metric.scorerOpOrObjRef)
        );
      })
      .map(evaluationCall => {
        return evaluationCall.callId;
      });

    metricKeyPath.scorerRefs[ref].evalCallIds = evals;
  });
  return composite;
};

/**
 * Resolves the metric definition for a given evaluation call id. This is
 * often used when we have the MetricDefinition corresponding to the baseline
 * evaluation, and we want to find the corresponding MetricDefinition for
 * the peer evaluation.
 */
export const resolvePeerDimension = (
  compositeScoreMetrics: CompositeScoreMetrics,
  evalCallId: string,
  peerDimension: MetricDefinition
): MetricDefinition | undefined => {
  const groupName = groupNameForMetric(peerDimension);
  const keyPath = flattenedDimensionPath(peerDimension);
  return resolveDimension(
    compositeScoreMetrics,
    evalCallId,
    groupName,
    keyPath
  );
};

/**
 * Resolves the metric definition for a given evaluation, group name, and key path.
 * This is often used when we have the group name and key path corresponding to the baseline
 * evaluation, and we want to find the corresponding MetricDefinition for the peer evaluation.
 */
export const resolveDimension = (
  compositeScoreMetrics: CompositeScoreMetrics,
  evalCallId: string,
  groupName: string,
  keyPath: string
): MetricDefinition | undefined => {
  return Object.values(
    compositeScoreMetrics[groupName].metrics[keyPath].scorerRefs
  ).find(scorerRef => scorerRef.evalCallIds.includes(evalCallId))?.metric;
};

/**
 * Utility function to obtain a map from evaluation call id to scorer ref
 * for a given `CompositeScoreMetricGroup`.
 */
export const evalCallIdToScorerRefs = (
  metricGroup: CompositeScoreMetricGroup
): {[evalCallId: string]: string} => {
  const res: {[evalCallId: string]: string} = {};
  Object.entries(metricGroup.metrics).forEach(([keyPath, scorerRefs]) => {
    Object.entries(scorerRefs.scorerRefs).forEach(
      ([scorerRef, {evalCallIds}]) => {
        evalCallIds.forEach(evalCallId => (res[evalCallId] = scorerRef));
      }
    );
  });
  return res;
};

// Helper Functions

const groupNameForMetric = (metric: MetricDefinition): string => {
  let groupName = '';

  if (metric.source === 'derived') {
    groupName = DERIVED_SCORER_REF_PLACEHOLDER;
  } else if (metric.source === 'scorer') {
    if (metric.scorerOpOrObjRef == null) {
      throw new Error('scorerOpOrObjRef must be defined for scorer metric');
    }
    groupName = getScoreKeyNameFromScorerRef(metric.scorerOpOrObjRef);
  }
  return groupName;
};

const refForMetric = (metric: MetricDefinition): string => {
  let ref = '';
  if (metric.source === 'derived') {
    ref = DERIVED_SCORER_REF_PLACEHOLDER;
  } else if (metric.source === 'scorer') {
    if (metric.scorerOpOrObjRef == null) {
      throw new Error('scorerOpOrObjRef must be defined for scorer metric');
    }

    ref = metric.scorerOpOrObjRef;
  }
  return ref;
};
