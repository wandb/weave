import {useMemo} from 'react';

import {useEvaluationComparisonData} from '../wfReactInterface/tsDataModelHooksEvaluationComparison';
import {Loadable} from '../wfReactInterface/wfDataModelHooksInterface';
import {ComparisonDimensionsType} from './ecpTypes';
import {EvaluationComparisonState} from './ecpTypes';

export const useEvaluationComparisonState = (
  entity: string,
  project: string,
  evaluationCallIds: string[],
  baselineEvaluationCallId?: string,
  comparisonDimensions?: ComparisonDimensionsType,
  selectedInputDigest?: string
): Loadable<EvaluationComparisonState> => {
  const data = useEvaluationComparisonData(entity, project, evaluationCallIds);

  const value = useMemo(() => {
    if (data.result == null || data.loading) {
      return {loading: true, result: null};
    }

    const scorerDimensions = Object.values(data.result.scorerMetricDimensions);
    const derivedDimensions = Object.values(
      data.result.derivedMetricDimensions
    );

    let newComparisonDimensions = comparisonDimensions;
    if (newComparisonDimensions == null) {
      newComparisonDimensions = [];
      if (scorerDimensions.length > 0) {
        newComparisonDimensions.push({
          dimension: scorerDimensions[0],
        });
        if (derivedDimensions.length > 0) {
          newComparisonDimensions.push({
            dimension: derivedDimensions[0],
          });
        }
      } else {
        if (derivedDimensions.length > 0) {
          newComparisonDimensions.push({
            dimension: derivedDimensions[0],
          });
        }
        if (derivedDimensions.length > 1) {
          newComparisonDimensions.push({
            dimension: derivedDimensions[1],
          });
        }
      }
    }

    return {
      loading: false,
      result: {
        data: data.result,
        baselineEvaluationCallId:
          baselineEvaluationCallId ?? evaluationCallIds[0],
        comparisonDimensions: newComparisonDimensions,
        selectedInputDigest,
      },
    };
  }, [
    data.result,
    data.loading,
    baselineEvaluationCallId,
    evaluationCallIds,
    comparisonDimensions,
    selectedInputDigest,
  ]);

  return value;
};

const moveItemToFront = (arr: any[], item: any) => {
  const index = arr.indexOf(item);
  if (index > -1) {
    arr.splice(index, 1);
    arr.unshift(item);
  }
};

export const getOrderedCallIds = (state: EvaluationComparisonState) => {
  const initial = Object.keys(state.data.evaluationCalls);
  moveItemToFront(initial, state.baselineEvaluationCallId);
  return initial;
};

export const getOrderedModelRefs = (state: EvaluationComparisonState) => {
  const baselineRef =
    state.data.evaluationCalls[state.baselineEvaluationCallId].modelRef;
  const refs = Object.keys(state.data.models);
  // Make sure the baseline model is first
  moveItemToFront(refs, baselineRef);
  return refs;
};
