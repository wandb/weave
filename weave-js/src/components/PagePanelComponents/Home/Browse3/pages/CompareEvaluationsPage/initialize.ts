import {useEffect, useMemo, useState} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {Loadable} from '../wfReactInterface/wfDataModelHooksInterface';
import {EvaluationComparisonState} from './compareEvaluationsContext';
import {
  EvaluationComparisonData,
  fetchEvaluationComparisonData,
} from './evaluationResults';
import {ScoreDimension} from './evaluations';

export type RangeSelection = {[evalCallId: string]: {min: number; max: number}};

export const useInitialState = (
  entity: string,
  project: string,
  evaluationCallIds: string[],
  baselineEvaluationCallId?: string,
  comparisonDimension?: ScoreDimension,
  rangeSelection?: RangeSelection
): Loadable<EvaluationComparisonState> => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [data, setData] = useState<EvaluationComparisonData | null>(null);
  const evaluationCallIdsMemo = useDeepMemo(evaluationCallIds);
  useEffect(() => {
    setData(null);
    let mounted = true;
    fetchEvaluationComparisonData(
      getTraceServerClient(),
      entity,
      project,
      evaluationCallIdsMemo
    ).then(dataRes => {
      if (mounted) {
        setData(dataRes);
      }
    });
    return () => {
      mounted = false;
    };
  }, [entity, evaluationCallIdsMemo, project, getTraceServerClient]);

  const value = useMemo(() => {
    if (data == null) {
      return {loading: true, result: null};
    }
    const dimensions = evaluationCallDimensions(data.evaluationCalls);
    return {
      loading: false,
      result: {
        data,
        baselineEvaluationCallId:
          baselineEvaluationCallId ?? evaluationCallIds[0],
        comparisonDimension: comparisonDimension ?? dimensions[0],
        rangeSelection: rangeSelection ?? {},
      },
    };
  }, [
    data,
    baselineEvaluationCallId,
    evaluationCallIds,
    comparisonDimension,
    rangeSelection,
  ]);

  return value;
};

const evaluationCallDimensions = (
  evaluationCalls: EvaluationComparisonData['evaluationCalls']
): ScoreDimension[] => {
  const availableScorers = Object.values(evaluationCalls)
    .map(evalCall =>
      Object.entries(evalCall.scores)
        .map(([k, v]) => Object.keys(v).map(innerKey => k + '.' + innerKey))
        .flat()
    )
    .flat();

  return [
    ...Array.from(new Set(availableScorers)),
    'model_latency',
    'total_tokens',
  ];
};

export const useEvaluationCallDimensions = (
  state: EvaluationComparisonState
): ScoreDimension[] => {
  return useMemo(() => {
    return evaluationCallDimensions(state.data.evaluationCalls);
  }, [state.data.evaluationCalls]);
};
