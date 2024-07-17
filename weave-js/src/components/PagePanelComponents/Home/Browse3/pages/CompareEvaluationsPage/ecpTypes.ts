/**
 * TODO:
 * * Really try to cleanup the code - specifically:
 *    * there is a lot of slopiness with react memoing
 *    * There is a lot of slopiness in symbol names and files
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
 *       * Scorecard links work
 *       * Filters are changeable and selectable
 *       * Filtered data is correct
 *       * SummaryScorers link correctly (both single and mixed)
 *       * MetricScorers link correctly (both single and mixed)
 *       * MetricValues link to scoring call correctly
 */

import {
  TraceCallSchema,
  TraceObjSchema,
} from '../wfReactInterface/traceServerClient';

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

export type BinarySummaryScore = {
  true_count: number;
  true_fraction: number;
};

export type BinaryValue = boolean;

export type ContinuousSummaryScore = {
  mean: number;
};

export type ContinuousValue = number;

// In the future, we can add `model_output` to capture self-reported model metrics
export type SourceType = 'derived' | 'scorer';
export type MetricType = 'score' | 'summary';

export type MetricDefinition = {
  metricSubPath: string[];
  scoreType: 'binary' | 'continuous';
  source: SourceType;
  scorerOpOrObjRef?: string;
  shouldMinimize?: boolean;
  unit?: string;
};

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

export type MetricDefinitionMap = {[metricId: string]: MetricDefinition};
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
