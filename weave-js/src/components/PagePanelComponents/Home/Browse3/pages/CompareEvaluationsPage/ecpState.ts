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
  // The dimensions to compare & filter results
  comparisonDimensions?: ComparisonDimensionsType;
  // The current digest which is in view
  selectedInputDigest?: string;
  // The selected metrics to display
  selectedMetrics?: Record<string, boolean>;
  // Ordered call Ids
  evaluationCallIdsOrdered: string[];
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
  comparisonDimensions?: ComparisonDimensionsType,
  selectedInputDigest?: string,
  selectedMetrics?: Record<string, boolean>
): Loadable<EvaluationComparisonState> => {
  const orderedCallIds = useMemo(() => {
    return getCallIdsOrderedForQuery(evaluationCallIds);
  }, [evaluationCallIds]);
  const data = useEvaluationComparisonData(entity, project, orderedCallIds);

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
        comparisonDimensions: newComparisonDimensions,
        selectedInputDigest,
        selectedMetrics,
        evaluationCallIdsOrdered: evaluationCallIds,
      },
    };
  }, [
    data.result,
    data.loading,
    comparisonDimensions,
    selectedInputDigest,
    selectedMetrics,
    evaluationCallIds,
  ]);

  return value;
};

export const getOrderedCallIds = (state: EvaluationComparisonState) => {
  return Array.from(state.evaluationCallIdsOrdered);
};

export const getBaselineCallId = (state: EvaluationComparisonState) => {
  return getOrderedCallIds(state)[0];
};

/**
 * Sort call IDs to ensure consistent order for memoized query params
 */
const getCallIdsOrderedForQuery = (callIds: string[]) => {
  return Array.from(callIds).sort();
};

/**
 * Should use this over keys of `state.data.models` because it ensures the baseline model is first.
 */
export const getOrderedModelRefs = (state: EvaluationComparisonState) => {
  const baselineCallId = getBaselineCallId(state);
  const baselineRef = state.data.evaluationCalls[baselineCallId].modelRef;
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

export const getOrderedEvalsWithNewBaseline = (
  evaluationCallIds: string[],
  newBaselineCallId: string
) => {
  return moveItemToFront(evaluationCallIds, newBaselineCallId);
};

export const swapEvaluationCalls = (
  evaluationCallIds: string[],
  ndx1: number,
  ndx2: number
): string[] => {
  return swapArrayItems(evaluationCallIds, ndx1, ndx2);
};

const swapArrayItems = <T>(arr: T[], ndx1: number, ndx2: number): T[] => {
  if (ndx1 < 0 || ndx2 < 0 || ndx1 >= arr.length || ndx2 >= arr.length) {
    throw new Error('Index out of bounds');
  }
  const newArr = [...arr];
  const from = newArr[ndx1];
  newArr[ndx1] = newArr[ndx2];
  newArr[ndx2] = from;
  return newArr;
};
