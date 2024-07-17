/**
 * TODO:
 * * Really try to cleanup the code - specifically:
 *    * there is a lot of slopiness with react memoing
 *    * There is a lot of slopiness in symbol names and files
 * *  // TODO: Update the SourceCall for auto-generated metrics to the summarizer
 * *  // TODO: Update the SourceCall for custom metrics to the summary call of the custom scorer
 * * Add click ability to the summary metrics
             
 * * See all code TODOs
 * * Remember to cleanup unused symbols (knip)
 *  * Test each of the example pages
 *    * URLS:
 *       * Unit Test
 *       * https://app.wandb.test/timssweeney/dev_testing/weave/compare-evaluations?evaluationCallIds=%5B%22b473c999-0468-4692-a03c-4e5120112a3b%22%2C%222c8b8f41-b249-44b4-b2dc-ada94987dd7c%22%5D
 *       * Anish
 *       * https://app.wandb.test/a-sh0ts/arxiv-papers-anthropic-testv6-8/weave/compare-evaluations?evaluationCallIds=%5B%224d26e233-37ab-4134-8985-f3ed58bb5c73%22%2C%22c99bca2c-3798-4b24-b5e6-75b245f3a0c8%22%5D
 *       * Lavanya
 *       * https://app.wandb.test/lavanyashukla/nims_rag_2/weave/compare-evaluations?evaluationCallIds=%5B%227ca7836f-e055-42eb-94c5-1625b73af789%22%2C%221024b6c8-6707-4e61-9474-463ad424a067%22%5D
 *       * https://app.wandb.test/lavanyashukla/nims_rag_2/weave/compare-evaluations?evaluationCallIds=%5B%22fad0e96b-e9e3-4a84-8ce0-ad61dce5987e%22%2C%221024b6c8-6707-4e61-9474-463ad424a067%22%2C%227ca7836f-e055-42eb-94c5-1625b73af789%22%5D
 *       * https://app.wandb.test/lavanyashukla/nims_rag_2/weave/compare-evaluations?evaluationCallIds=%5B%223fd22e88-84a6-4f66-ba71-2f789d44aded%22%2C%227ca7836f-e055-42eb-94c5-1625b73af789%22%2C%221024b6c8-6707-4e61-9474-463ad424a067%22%2C%22d6358605-5c1d-4561-819d-179bb433a7a7%22%5D
 *       * Jason
 *       * https://app.wandb.test/jzhao/resume-bot-eval/weave/compare-evaluations?evaluationCallIds=%5B%22fecc2462-10c1-4a7b-a0b9-4e1726e5618d%22%2C%224bc16671-95b6-4044-94d4-b34417b44868%22%5D
 *       * Shawn
 *       * https://app.wandb.test/shawn/humaneval6/weave/compare-evaluations?evaluationCallIds=%5B%2258c9db2c-c1f8-4643-a79d-7a13c55fbc72%22%5D
 *       * https://app.wandb.test/shawn/humaneval6/weave/compare-evaluations?evaluationCallIds=%5B%2258c9db2c-c1f8-4643-a79d-7a13c55fbc72%22%2C%228563f89b-07e8-4042-9417-e22b4257bf95%22%5D
 *       * https://app.wandb.test/shawn/humaneval6/weave/compare-evaluations?evaluationCallIds=%5B%2258c9db2c-c1f8-4643-a79d-7a13c55fbc72%22%2C%228563f89b-07e8-4042-9417-e22b4257bf95%22%2C%2232f3e6bc-5488-4dd4-b9c4-801929f2c541%22%2C%2234c0a20f-657f-407e-bb33-277abbb9997f%22%5D
 *       * Adam
 *       * https://app.wandb.test/wandb-designers/signal-maven/weave/compare-evaluations?evaluationCallIds=%5B%22eb4a3bed-5e67-4caf-a911-db4705f5254e%22%5D
 *       * https://app.wandb.test/wandb-designers/signal-maven/weave/compare-evaluations?evaluationCallIds=%5B%22eb4a3bed-5e67-4caf-a911-db4705f5254e%22%2C%22c4345512-ef52-4112-a941-83fd6dac779f%22%5D
 *       * https://app.wandb.test/wandb-designers/signal-maven/weave/compare-evaluations?evaluationCallIds=%5B%22eb4a3bed-5e67-4caf-a911-db4705f5254e%22%2C%22c4345512-ef52-4112-a941-83fd6dac779f%22%2C%22bf5188ba-48cd-4c6d-91ea-e25464570c13%22%2C%228d76bb68-837e-4fff-8159-489958fd1f65%22%5D
 *    * Tests:
 *       * Loads
 *       * Charts look good
 *       * Scorecard looks good
 *       * Filters are changeable and selectable
 *       * Filtered data is correct
 *       * SummaryScorers link correctly (both single and mixed)
 *       * MetricScorers link correctly (both single and mixed)
 *       * MetricValues link to scoring call correctly
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
