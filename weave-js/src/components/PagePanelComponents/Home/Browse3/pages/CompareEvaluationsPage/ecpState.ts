/**
 * This file defines `EvaluationComparisonState` which is the global state object used to
 * render the Evaluations Comparison Page. Furthermore, we defined a custom hook that is used
 * to fetch the data and populate some default values for the state object. Finally, we define
 * some helper functions.
 */

import {useMemo} from 'react';

import {useEvaluationComparisonData} from '../wfReactInterface/tsDataModelHooksEvaluationComparison';
import {Loadable} from '../wfReactInterface/wfDataModelHooksInterface';
import {EvaluationComparisonData} from './ecpTypes';
import {getMetricIds} from './ecpUtil';

/**
 * The global state object used to render the Evaluations Comparison Page.
 */
export type EvaluationComparisonState = {
  // The normalized data for the evaluations
  data: EvaluationComparisonData;
  // The evaluation call id of the baseline model
  baselineEvaluationCallId: string;
  // The dimensions to compare & filter results
  comparisonDimensions?: ComparisonDimensionsType;
  // The current digest which is in view
  selectedInputDigest?: string;
};

export type ComparisonDimensionsType = Array<{
  metricId: string;
  rangeSelection?: RangeSelection;
}>;

type RangeSelection = {[evalCallId: string]: {min: number; max: number}};

/**
 * Fetches the data and populates some default values for the state object. This is the primary
 * bridge between react and the evaluation comparison data retrieval.
 */
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

    const scorerDimensions = Object.keys(
      getMetricIds(data.result, 'score', 'scorer')
    );
    const derivedDimensions = Object.keys(
      getMetricIds(data.result, 'score', 'derived')
    );

    let newComparisonDimensions = comparisonDimensions;
    if (newComparisonDimensions == null) {
      newComparisonDimensions = [];
      if (scorerDimensions.length > 0) {
        newComparisonDimensions.push({
          metricId: scorerDimensions[0],
        });
        if (derivedDimensions.length > 0) {
          newComparisonDimensions.push({
            metricId: derivedDimensions[0],
          });
        }
      } else {
        if (derivedDimensions.length > 0) {
          newComparisonDimensions.push({
            metricId: derivedDimensions[0],
          });
        }
        if (derivedDimensions.length > 1) {
          newComparisonDimensions.push({
            metricId: derivedDimensions[1],
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

/**
 * Should use this over keys of `state.data.evaluationCalls` because it ensures the baseline
 * evaluation call is first.
 */
export const getOrderedCallIds = (state: EvaluationComparisonState) => {
  const initial = Object.keys(state.data.evaluationCalls);
  moveItemToFront(initial, state.baselineEvaluationCallId);
  return initial;
};

/**
 * Should use this over keys of `state.data.models` because it ensures the baseline model is first.
 */
export const getOrderedModelRefs = (state: EvaluationComparisonState) => {
  const baselineRef =
    state.data.evaluationCalls[state.baselineEvaluationCallId].modelRef;
  const refs = Object.keys(state.data.models);
  // Make sure the baseline model is first
  moveItemToFront(refs, baselineRef);
  return refs;
};

// Helpers

// Consider merging with `EmojiDetails.tsx::moveToFront`
const moveItemToFront = <T>(arr: T[], item: T): T[] => {
  const index = arr.indexOf(item);
  if (index > -1) {
    arr.splice(index, 1);
    arr.unshift(item);
  }
  return arr;
};
