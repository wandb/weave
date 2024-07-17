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

import {
  EvaluationComparisonData,
  getScoreKeyNameFromScorerRef,
  MetricDefinition,
  MetricType,
} from './ecpTypes';
import {flattenedDimensionPath} from './ecpUtil';

export const DERIVED_SCORER_REF = '__DERIVED__';

export type CompositeSummaryMetricGroupKeyPath = {
  scorerAgnosticMetricDef: Omit<MetricDefinition, 'scorerOpOrObjRef'>;
  scorerRefs: {
    [scoreRef: string]: {
      evalCallIds: string[];
      metric: MetricDefinition;
    };
  };
};

type CompositeScoreMetricGroup = {
  scorerRefs: string[];
  metrics: {
    [keyPath: string]: CompositeSummaryMetricGroupKeyPath;
  };
};

export type CompositeScoreMetrics = {
  [groupName: string]: CompositeScoreMetricGroup;
};

const groupNameForMetric = (metric: MetricDefinition): string => {
  let groupName = '';

  if (metric.source === 'derived') {
    groupName = DERIVED_SCORER_REF;
  } else if (metric.source === 'scorer') {
    if (metric.scorerOpOrObjRef == null) {
      throw new Error('scorerOpOrObjRef must be defined for scorer metric');
    }
    groupName = getScoreKeyNameFromScorerRef(metric.scorerOpOrObjRef);
  }
  return groupName;
};

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

const refForMetric = (metric: MetricDefinition): string => {
  let ref = '';
  if (metric.source === 'derived') {
    ref = DERIVED_SCORER_REF;
  } else if (metric.source === 'scorer') {
    if (metric.scorerOpOrObjRef == null) {
      throw new Error('scorerOpOrObjRef must be defined for scorer metric');
    }

    ref = metric.scorerOpOrObjRef;
  }
  return ref;
};

export const buildCompositeMetricsMap = (
  data: EvaluationComparisonData,
  mType: MetricType
): CompositeScoreMetrics => {
  let metricDefinitionMap;
  if (mType === 'score') {
    metricDefinitionMap = data.scoreMetrics;
  } else if (mType === 'summary') {
    metricDefinitionMap = data.summaryMetrics;
  } else {
    throw new Error(`Invalid metric type: ${mType}`);
  }
  const composite: CompositeScoreMetrics = {};
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
