import {sum} from 'lodash';

import {flattenObject} from '../../../Browse2/browse2Util';
import {TraceCallSchema} from '../wfReactInterface/traceServerClient';
import {EvaluationComparisonState} from './types';

type BinarySummaryScore = {
  true_count: number;
  true_fraction: number;
};

type ContinuousSummaryScore = {
  mean: number;
};

export type ScoreDimension = {
  scorerRef: string;
  scoreKeyPath: string;
  scoreType: 'binary' | 'continuous';
  minimize?: boolean;
};

export type EvaluationEvaluateCallSchema = TraceCallSchema & {
  inputs: TraceCallSchema['inputs'] & {
    self: string;
    model: string;
  };
  output: TraceCallSchema['output'] & {
    [scorer: string]: {
      [score: string]: BinarySummaryScore | ContinuousSummaryScore;
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

type ComparisonMetric = {
  path: string;
  unit: string;
  lowerIsBetter: boolean;
  values: {[callId: string]: number};
};

export const evaluationMetrics = (
  state: EvaluationComparisonState
): ComparisonMetric[] => {
  const evaluationCalls = Object.values(state.data.evaluationCalls).map(
    e => e._rawEvaluationTraceData
  );
  // There are a few hard-coded possible metrics, then a handful of custom metrics:

  // Tokens
  const tokensMetric: ComparisonMetric = {
    path: 'total_tokens',
    unit: ' tokens',
    values: Object.fromEntries(
      evaluationCalls.map(call => [
        call.id,
        sum(Object.values(call.summary.usage ?? {}).map(v => v.total_tokens)),
      ])
    ),
    lowerIsBetter: true,
  };

  // scorers
  const allScorers: {[scorer: string]: ComparisonMetric} = {};
  const allCallIds = evaluationCalls.map(call => call.id);
  evaluationCalls.forEach(call => {
    const flattenedOutput = flattenObject(call.output);
    const scorerKeys: string[] = [];
    Object.keys(flattenedOutput).forEach(scorerKey => {
      const allButLastKey = scorerKey.split('.').slice(0, -1).join('.');
      if (scorerKeys.includes(allButLastKey)) {
        return;
      }
      scorerKeys.push(allButLastKey);
    });
    scorerKeys.forEach(scorerKey => {
      const fractionKey = `${scorerKey}.true_fraction`;
      const meanKey = `${scorerKey}.mean`;
      const hasFraction = flattenedOutput[fractionKey] !== undefined;
      if (allScorers[scorerKey] === undefined) {
        let unit = '';
        let lowerIsBetter = false;
        if (scorerKey === 'model_latency') {
          unit = 'ms';
          lowerIsBetter = true;
        } else if (hasFraction) {
          unit = '%';
        }
        allScorers[scorerKey] = {
          path: scorerKey,
          unit,
          values: Object.fromEntries(allCallIds.map(id => [id, 0])),
          lowerIsBetter,
        };
      }
      if (hasFraction) {
        allScorers[scorerKey].values[call.id] = flattenedOutput[fractionKey];
      } else {
        allScorers[scorerKey].values[call.id] = flattenedOutput[meanKey];
      }
    });
  });

  return [...Object.values(allScorers), tokensMetric];
};
