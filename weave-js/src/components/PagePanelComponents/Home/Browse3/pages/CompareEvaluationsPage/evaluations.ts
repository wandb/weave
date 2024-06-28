import {sum} from 'lodash';
import {useMemo} from 'react';

import {flattenObject} from '../../../Browse2/browse2Util';
import {useWFHooks} from '../wfReactInterface/context';
import {TraceCallSchema} from '../wfReactInterface/traceServerClient';

type BinarySummaryScore = {
  true_count: number;
  true_fraction: number;
};

type ContinuousSummaryScore = {
  mean: number;
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
    model_latency: number;
  };
  summary: TraceCallSchema['summary'] & {
    usage: {
      [model: string]: {
        requests?: number;
        completion_tokens?: number;
        prompt_tokens?: number;
        total_tokens?: number;
      };
    };
  };
};

export const useEvaluationCalls = (
  entity: string,
  project: string,
  evaluationCallIds: string[]
): EvaluationEvaluateCallSchema[] => {
  const {useCalls} = useWFHooks();
  const calls = useCalls(entity, project, {callIds: evaluationCallIds});
  return useMemo(() => {
    // TODO: Should validate that these are EvaluationEvaluateCallSchema
    return (
      calls.result?.map(c => c.traceCall as EvaluationEvaluateCallSchema) || []
    );
  }, [calls.result]);
};

export const useEvaluationCall = (
  entity: string,
  project: string,
  evaluationCallId: string
): EvaluationEvaluateCallSchema | null => {
  const calls = useEvaluationCalls(entity, project, [evaluationCallId]);
  return useMemo(() => {
    if (calls.length === 0) {
      return null;
    }
    return calls[0];
  }, [calls]);
};

type EvaluationModel = {
  ref: string;
  data: any;
};

export const useModelsFromEvaluationCalls = (
  evaluationCalls: EvaluationEvaluateCallSchema[]
): EvaluationModel[] => {
  const {useRefsData} = useWFHooks();
  const modelRefs = useMemo(() => {
    return evaluationCalls.map(call => call.inputs.model);
  }, [evaluationCalls]);
  const modelData = useRefsData(modelRefs);
  return useMemo(() => {
    if (!modelData.result || modelData.result.length !== modelRefs.length) {
      return [];
    }
    return modelRefs.map((ref, i) => ({ref, data: modelData.result![i]}));
  }, [modelData.result, modelRefs]);
};

type ComparisonMetric = {
  path: string;
  unit: string;
  values: number[];
  lowerIsBetter: boolean;
};

export const evaluationMetrics = (
  evaluationCalls: EvaluationEvaluateCallSchema[]
): ComparisonMetric[] => {
  // There are a few hard-coded possible metrics, then a handful of custom metrics:

  // Tokens
  const tokensMetric: ComparisonMetric = {
    path: 'total_tokens',
    unit: ' tokens',
    values: evaluationCalls.map(call =>
      sum(Object.values(call.summary.usage).map(v => v.total_tokens))
    ),
    lowerIsBetter: true,
  };

  // scorers
  const allScorers: {[scorer: string]: ComparisonMetric} = {};
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
          values: [],
          lowerIsBetter,
        };
      }
      if (hasFraction) {
        allScorers[scorerKey].values.push(flattenedOutput[fractionKey]);
      } else {
        allScorers[scorerKey].values.push(flattenedOutput[meanKey]);
      }
    });
  });

  return [tokensMetric, ...Object.values(allScorers)];
};
