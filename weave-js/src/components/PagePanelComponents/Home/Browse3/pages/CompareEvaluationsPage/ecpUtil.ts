/**
 * This file contains a handful of utilities for working with the `EvaluationComparisonData` destructure.
 * These are mostly convenience functions for extracting and resolving metrics from the data, but also
 * include some helper functions for working with the `MetricDefinition` objects and constructing
 * strings correctly.
 */

import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {
  EvaluationCall,
  EvaluationComparisonData,
  MetricDefinition,
  MetricDefinitionMap,
  MetricResult,
  MetricType,
  MetricValueType,
  PredictAndScoreCall,
  SourceType,
} from './ecpTypes';

export const EVALUATION_NAME_DEFAULT = 'Evaluation';

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

export const getMetricIds = (
  data: EvaluationComparisonData,
  type: MetricType,
  source: SourceType
): MetricDefinitionMap => {
  const metrics = type === 'score' ? data.scoreMetrics : data.summaryMetrics;
  return Object.fromEntries(
    Object.entries(metrics).filter(([k, v]) => v.source === source)
  );
};

export const getScoreKeyNameFromScorerRef = (scorerRef: string) => {
  const parsed = parseRef(scorerRef) as WeaveObjectRef;
  return parsed.artifactName;
};

export const metricDefinitionId = (metricDef: MetricDefinition): string => {
  const path = metricDef.metricSubPath
    .map(p => {
      return p.replace('.', '\\.');
    })
    .join('.');
  if (metricDef.source === 'derived') {
    return `derived#${path}`;
  } else if (metricDef.source === 'scorer') {
    if (metricDef.scorerOpOrObjRef == null) {
      throw new Error('scorerOpOrObjRef must be defined for scorer metric');
    }
    return `${metricDef.scorerOpOrObjRef}#${path}`;
  } else {
    throw new Error(`Unknown metric source: ${metricDef.source}`);
  }
};
