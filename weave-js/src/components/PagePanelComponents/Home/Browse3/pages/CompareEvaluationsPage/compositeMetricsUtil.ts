import {
  EvaluationComparisonData,
  getScoreKeyNameFromScorerRef,
  MetricDefinition,
  MetricType,
} from './ecpTypes';
import {flattenedDimensionPath} from './ecpUtil';
import {DERIVED_SCORER_REF} from './sections/ScorecardSection/summaryMetricUtil';

export type CompositeSummaryMetricGroupKeyPath = {
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

export type ResolvePeerDimensionFn2 = (
  compositeScoreMetrics: CompositeScoreMetrics,
  evalCallId: string,
  peerDimension: MetricDefinition
) => MetricDefinition | undefined;

export const resolvePeerDimension: ResolvePeerDimensionFn2 = (
  compositeScoreMetrics: CompositeScoreMetrics,
  evalCallId: string,
  peerDimension: MetricDefinition
): MetricDefinition | undefined => {
  const groupName = groupNameForMetric(peerDimension);
  const keyPath = flattenedDimensionPath(peerDimension);
  return Object.values(
    compositeScoreMetrics[groupName].metrics[keyPath].scorerRefs
  ).find(scorerRef => scorerRef.evalCallIds.includes(evalCallId))?.metric;
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
