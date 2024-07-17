/**
 * TODO:
 * * Test each of the example pages
 * * Really try to cleanup the code - specifically:
 *    * the summary metrics scorecard and the comparison view now have a lot of similar code
 *    * there is a lot of slopiness with react memoing
 *    * There is a lot of slopiness in symbol names and files
 * * // TODO: Verify this fallback is correct - i think this is not correct
 * * Audit all the source call ids (sourceCallId:)
 * * See all code TODOs
 * * Remember to cleanup unused symbols (knip)
 */

/**
 * Notes on the shape of Evaluation Data:
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

import {parseRef, WeaveObjectRef} from '../../../../../../react';
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

type BinaryValue = boolean;

export const isBinaryScore = (score: any): score is BinaryValue => {
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

type ContinuousValue = number;

export const isContinuousScore = (score: any): score is ContinuousValue => {
  return typeof score === 'number';
};

type SourceType = 'derived' | 'scorer'; // In the future, we can add `model_output` to capture self-reported model metrics
export type MetricType = 'score' | 'summary';

export type MetricDefinition = {
  metricSubPath: string[];
  scoreType: 'binary' | 'continuous';
  source: SourceType;
  scorerOpOrObjRef?: string;
  shouldMinimize?: boolean;
  unit?: string;
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

// const metricIdToDefinition = (
//   data: EvaluationComparisonData,
//   scoreOrSummary: 'score' | 'summary',
//   metricId: string
// ): MetricDefinition => {
//   if (scoreOrSummary === 'score') {
//     if (!(metricId in data.scoreMetrics)) {
//       throw new Error(`Metric ID ${metricId} not found in scoreMetrics`);
//     }
//     return data.scoreMetrics[metricId];
//   } else if (scoreOrSummary === 'summary') {
//     if (!(metricId in data.summaryMetrics)) {
//       throw new Error(`Metric ID ${metricId} not found in summaryMetrics`);
//     }
//     return data.summaryMetrics[metricId];
//   } else {
//     throw new Error(`Unknown scoreOrSummary: ${scoreOrSummary}`);
//   }
// };

export type MetricValueType = BinaryValue | ContinuousValue;

export type MetricResult = {
  value: MetricValueType;
  sourceCallId: string;
};

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

type SummaryScore = BinarySummaryScore | ContinuousSummaryScore;

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
  scoreMetrics: MetricDefinitionMap;
  summaryMetrics: MetricDefinitionMap;
};

type MetricDefinitionMap = {[metricId: string]: MetricDefinition};
type MetricResultMap = {[metricId: string]: MetricResult};

export type PredictAndScoreCall = {
  callId: string;
  exampleRef: string;
  rowDigest: string;
  modelRef: string;
  evaluationCallId: string;
  scoreMetrics: MetricResultMap;
  _rawPredictAndScoreTraceData: TraceCallSchema;
  _rawPredictTraceData?: TraceCallSchema;
};

type RangeSelection = {[evalCallId: string]: {min: number; max: number}};

export type ComparisonDimensionsType = Array<{
  metricId: string;
  rangeSelection?: RangeSelection;
}>;

export type EvaluationCall = {
  callId: string;
  name: string;
  color: string;
  evaluationRef: string;
  modelRef: string;
  summaryMetrics: MetricResultMap;
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
