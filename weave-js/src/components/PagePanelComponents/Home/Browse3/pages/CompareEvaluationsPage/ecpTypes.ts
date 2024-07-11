/**
 * TODO:
 *
 * * Scorers here are not as well defined as they should be. Let's get a better
 *   understanding:
 * 1. Scorers can come in 2 flavors: Ops or Object Classes. Ops are pure
 *    functions whereas Object Classes have a `score` method and optionally a
 *    `summarize` method. If not provided, the summarization will recursively
 *    `auto_summarize` the outputs of the `score` method. Therefore we have the
 *    following scorer types:
 *    - Ops
 *    - Object Classes (auto_summarize)
 *    - Object Classes (summarize)
 * 2. The output of a scorer can be a boolean or a number (or a possibly-nested
 *    dictionary of such values)
 *    - For sake of processing, we call each leaf path of the `score` or
 *      `summarize` output a "metric"
 *        - TODO: Refactor such that (we currently don't make a distinction):
 *            - Leaf paths of `score` method are: `ScoreMetric`
 *            - Leaf path of `summarize` method are: `SummaryMetric`
 * 3. Autosummarization works by operating on the leaf nodes of the output
 *    dictionary and applying a summarization function: 
 *    - For binary values: {"true_count": X, "true_fraction": Y}
 *       - Note: we typically ignore "true_count" and only use "true_fraction"
 *         for binary values
 *    - For continuous values: {'mean': X}
 * 4. Custom summarization has no rules - it is yet again a primitive or
 *    possibly-nested dictionary of primitives.
 * 5. An evaluation can have any number of scorers.
 * 6. Scorers are versioned - meaning Scorers of the same name should be
 *    conceptually comparable, but might vary in implementation.
 *
 * Now, how do we walk through the data?
 * * EvaluationObj -> DatasetObjRef (via inputs.dataset)
 * * EvaluationObj -> ScoreOpRef[]  (via inputs.scorers)
 * * EvaluateCall -> ModelObjRef (via inputs.model)
 * * EvaluateCall -> EvaluationObjRef (via op_name)
 * * EvaluateCall -> {[scoreName: string]: SummaryMetric} (via output)
 * * EvaluateCall -> (derived metric special case) Model Latency (via output.model_latency)
 * * EvaluateCall -> (derived metric special case) Token Usage (via summary.usage) - flawed as it includes non-model tokens
 * * PredictAndScoreCall -> EvaluateCall (via parent_id callId)
 * * ModelPredictCall -> ModelRef (via inputs.self)
 * * ModelPredictCall -> DatasetRowRef (via inputs.example).
 * * DatasetRowRef -> DatasetObjRef (via string parsing) - fragile due to ref structure
 * * DatasetRowRef -> Digest (via string parsing) - fragile and happens to be the last part of the ref
 * * ModelPredictCall -> PredictAndScoreCall (via parent_id callId)
 * * ModelPredictCall -> Output (via output)
 * * ModelPredictCall -> (derived metric special case) Model Latency (via end_time - start_time)
 * * ModelPredictCall -> (derived metric special case) Token Usage (via summary.usage)
 * * ScoreCall -> PredictAndScoreCall (via parent_id callId)
 * * ScoreCall -> ScoreOpRef (via inputs.self)
 * * ScoreCall -> ScoreMetric (via output)
 * * ScoreOp (optional) -> ScorerObjRef (via inputs.self)
 * * DatasetObj -> DatasetRow[] (via api TableQuery)
 * * DatasetRow -> RowDigest (via digest)
 * * DatasetRow -> RowValue (via val)
 * 
 * * Critical: DatasetRows have a Digest which can be used to associate the same data
 *  across different datasets.
 */

import {
  TraceCallSchema,
  TraceObjSchema,
} from '../wfReactInterface/traceServerClient';

export type EvaluationComparisonState = {
  data: EvaluationComparisonData;
  baselineEvaluationCallId: string;
  comparisonDimensions?: ComparisonDimensionsType;
  selectedInputDigest?: string;
};

type BinarySummaryScore = {
  true_count: number;
  true_fraction: number;
};

type BinaryScore = boolean;

export const isBinaryScore = (score: any): score is BinaryScore => {
  return typeof score === 'boolean';
};

type ContinuousSummaryScore = {
  mean: number;
};

export const isBinarySummaryScore = (
  score: any
): score is BinarySummaryScore => {
  return (
    typeof score === 'object' &&
    score != null &&
    'true_count' in score &&
    'true_fraction' in score
  );
};

export const isContinuousSummaryScore = (
  score: any
): score is ContinuousSummaryScore => {
  return typeof score === 'object' && score != null && 'mean' in score;
};

type ContinuousScore = number;

export const isContinuousScore = (score: any): score is ContinuousScore => {
  return typeof score === 'number';
};

export type ScorerDefinition = {
  scorerOpOrObjRef: string;
  likelyTopLevelKeyName: string;
};

export type ScorerMetricDimension = {
  dimensionType: 'scorerMetric';
  scorerDef: ScorerDefinition;
  metricSubPath: string[];
  scoreType: 'binary' | 'continuous';
};

export type DerivedMetricDefinition = {
  dimensionType: 'derivedMetric';
  derivedMetricName: string;
  scoreType: 'binary' | 'continuous';
  shouldMinimize?: boolean;
  unit?: string;
};

export const isScorerMetricDimension = (
  dim: EvaluationMetricDimension
): dim is ScorerMetricDimension => {
  return typeof dim === 'object' && dim.dimensionType === 'scorerMetric';
};

export const isDerivedMetricDefinition = (
  dim: EvaluationMetricDimension
): dim is DerivedMetricDefinition => {
  return typeof dim === 'object' && dim.dimensionType === 'derivedMetric';
};

export type EvaluationMetricDimension =
  | ScorerMetricDimension
  | DerivedMetricDefinition;

export type EvaluationEvaluateCallSchema = TraceCallSchema & {
  inputs: TraceCallSchema['inputs'] & {
    self: string;
    model: string;
  };
  output: TraceCallSchema['output'] & {
    [scorer: string]: {
      [score: string]: SummaryScore;
    };
  } & {
    model_latency: ContinuousSummaryScore;
  };
  summary: TraceCallSchema['summary'] & {
    usage?: {
      [model: string]: {
        requests?: number;
        completion_tokens?: number;
        prompt_tokens?: number;
        total_tokens?: number;
      };
    };
  };
};

export type SummaryScore = BinarySummaryScore | ContinuousSummaryScore;

type DatasetRow = {
  digest: string;
  val: any;
};
type ModelObj = {
  ref: string;
  predictOpRef: string;
  properties: {[prop: string]: any};
  project: string;
  entity: string;
  _rawModelObject: TraceObjSchema;
};

export type ScoreType = BinaryScore | ContinuousScore;
export type MetricResult = {
  value: ScoreType;
  sourceCall: {
    callId: string;
    _rawScoreTraceData: TraceCallSchema;
  };
};

export type EvaluationComparisonData = {
  entity: string;
  project: string;
  evaluationCalls: {
    [callId: string]: EvaluationCall;
  };
  evaluations: {
    [objectRef: string]: EvaluationObj;
  };
  inputs: {
    [rowDigest: string]: DatasetRow;
  };
  models: {
    [modelRef: string]: ModelObj;
  };
  resultRows: {
    [rowDigest: string]: {
      evaluations: {
        [evaluationCallId: string]: {
          predictAndScores: {
            [predictAndScoreCallId: string]: PredictAndScoreCall;
          };
        };
      };
    };
  };
  derivedMetricDimensions: {
    [metricDimensionId: string]: DerivedMetricDefinition;
  };
  scorerMetricDimensions: {[metricDimensionId: string]: ScorerMetricDimension};
};

export type PredictAndScoreCall = {
  callId: string;
  exampleRef: string;
  rowDigest: string;
  modelRef: string;
  evaluationCallId: string;
  scorerMetrics: {
    [metricDimensionId: string]: MetricResult;
  };
  derivedMetrics: {
    [metricDimensionId: string]: MetricResult;
  };
  _rawPredictAndScoreTraceData: TraceCallSchema;
  _rawPredictTraceData?: TraceCallSchema;
};

type RangeSelection = {[evalCallId: string]: {min: number; max: number}};

export type ComparisonDimensionsType = Array<{
  dimension: EvaluationMetricDimension;
  rangeSelection?: RangeSelection;
}>;

export type EvaluationCall = {
  callId: string;
  name: string;
  color: string;
  evaluationRef: string;
  modelRef: string;
  summaryMetrics: {
    [metricDimensionId: string]: SummaryScore;
  };
  _rawEvaluationTraceData: EvaluationEvaluateCallSchema;
};

type EvaluationObj = {
  ref: string;
  datasetRef: string;
  scorerRefs: string[];
  project: string;
  entity: string;
  _rawEvaluationObject: TraceObjSchema;
};
