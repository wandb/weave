import {useEffect, useMemo, useState} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {Loadable} from '../wfReactInterface/wfDataModelHooksInterface';
import {EvaluationComparisonState} from './compareEvaluationsContext';
import {
  EvaluationComparisonData,
  fetchEvaluationComparisonData,
  isBinarySummaryScore,
  isContinuousSummaryScore,
} from './evaluationResults';
import {ScoreDimension} from './evaluations';

export type RangeSelection = {[evalCallId: string]: {min: number; max: number}};

export const useInitialState = (
  entity: string,
  project: string,
  evaluationCallIds: string[],
  baselineEvaluationCallId?: string,
  comparisonDimension?: ScoreDimension,
  rangeSelection?: RangeSelection,
  selectedInputDigest?: string
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
    const dimensions = evaluationCallDimensions(data);
    return {
      loading: false,
      result: {
        data,
        baselineEvaluationCallId:
          baselineEvaluationCallId ?? evaluationCallIds[0],
        comparisonDimension: comparisonDimension ?? dimensions[0],
        rangeSelection: rangeSelection ?? {},
        selectedInputDigest,
      },
    };
  }, [
    data,
    baselineEvaluationCallId,
    evaluationCallIds,
    comparisonDimension,
    rangeSelection,
    selectedInputDigest,
  ]);

  return value;
};

const evaluationCallDimensions = (
  data: EvaluationComparisonData
): ScoreDimension[] => {
  // const availableScorers = Object.values(evaluationCalls)
  //   .map(evalCall =>
  //     Object.entries(evalCall.scores)
  //       .map(([k, v]) => Object.keys(v).map(innerKey => k + '.' + innerKey))
  //       .flat()
  //   )
  //   .flat();
  const availableScorersMap: {[ref: string]: {[path: string]: ScoreDimension}} =
    {};
  const recordScorer = (scoreDim: ScoreDimension) => {
    if (!availableScorersMap[scoreDim.scorerRef]) {
      availableScorersMap[scoreDim.scorerRef] = {};
    }
    availableScorersMap[scoreDim.scorerRef][scoreDim.scoreKeyPath] = scoreDim;
  };

  const addScore = (score: any, scoreRef: string, scoreKeyPath: string) => {
    // Two types of scores: single value and dict
    if (isBinarySummaryScore(score)) {
      recordScorer({
        scorerRef: scoreRef,
        scoreKeyPath,
        scoreType: 'binary',
        minimize: false,
      });
    } else if (isContinuousSummaryScore(score)) {
      recordScorer({
        scorerRef: scoreRef,
        scoreKeyPath,
        scoreType: 'continuous',
        minimize: false,
      });
    } else if (
      score != null &&
      typeof score === 'object' &&
      !Array.isArray(score)
    ) {
      Object.entries(score).forEach(([key, value]) => {
        addScore(value, scoreRef, scoreKeyPath + '.' + key);
      });
    }
  };

  Object.values(data.evaluationCalls).forEach(evalCall => {
    const evalObject = data.evaluations[evalCall.evaluationRef];
    evalObject.scorerRefs.forEach(scoreRef => {
      const scorerKey = (parseRef(scoreRef) as WeaveObjectRef).artifactName;
      // TODO: Should put scores at the top level using the ref, not name as the key!
      const score = evalCall._rawEvaluationTraceData.output[scorerKey];
      addScore(score, scoreRef, scorerKey);
    });
  });

  // recordScorer({
  //   scorerRef: ,
  //   scoreKeyPath: scoreKeyPath,
  //   scoreType: 'continuous',
  //   minimize: false,
  // })

  return [
    ...Object.values(availableScorersMap).map(Object.values).flat(),
    // 'model_latency',
    // 'total_tokens',
  ];
};

export const useEvaluationCallDimensions = (
  state: EvaluationComparisonState
): ScoreDimension[] => {
  return useMemo(() => {
    return evaluationCallDimensions(state.data);
  }, [state.data]);
};
