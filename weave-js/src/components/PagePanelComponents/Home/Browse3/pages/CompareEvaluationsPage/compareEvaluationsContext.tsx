import React, {useMemo} from 'react';

import {ScoreDimension} from './evaluations';
import {RangeSelection, useInitialState} from './initialize';
import {EvaluationComparisonState} from './types';

const CompareEvaluationsContext = React.createContext<{
  state: EvaluationComparisonState;
  setBaselineEvaluationCallId: React.Dispatch<
    React.SetStateAction<string | null>
  >;
  setComparisonDimension: React.Dispatch<
    React.SetStateAction<ScoreDimension | null>
  >;
  setRangeSelection: React.Dispatch<React.SetStateAction<RangeSelection>>;
  setSelectedInputDigest: React.Dispatch<React.SetStateAction<string | null>>;
} | null>(null);

export const useCompareEvaluationsState = () => {
  const ctx = React.useContext(CompareEvaluationsContext);
  if (ctx === null) {
    throw new Error('No CompareEvaluationsProvider');
  }
  return ctx;
};

export const CompareEvaluationsProvider: React.FC<{
  entity: string;
  project: string;
  evaluationCallIds: string[];
  setBaselineEvaluationCallId: React.Dispatch<
    React.SetStateAction<string | null>
  >;
  setComparisonDimension: React.Dispatch<
    React.SetStateAction<ScoreDimension | null>
  >;
  setRangeSelection: React.Dispatch<React.SetStateAction<RangeSelection>>;
  setSelectedInputDigest: React.Dispatch<React.SetStateAction<string | null>>;
  rangeSelection?: RangeSelection;
  baselineEvaluationCallId?: string;
  comparisonDimension?: ScoreDimension;
  selectedInputDigest?: string;
}> = ({
  entity,
  project,
  evaluationCallIds,
  setBaselineEvaluationCallId,
  setComparisonDimension,
  setRangeSelection,
  setSelectedInputDigest,
  rangeSelection,
  baselineEvaluationCallId,
  comparisonDimension,
  selectedInputDigest,
  children,
}) => {
  const initialState = useInitialState(
    entity,
    project,
    evaluationCallIds,
    baselineEvaluationCallId,
    comparisonDimension,
    rangeSelection,
    selectedInputDigest
  );

  const value = useMemo(() => {
    if (initialState.loading || initialState.result == null) {
      return null;
    }
    return {
      state: initialState.result,
      setBaselineEvaluationCallId,
      setComparisonDimension,
      setRangeSelection,
      setSelectedInputDigest,
    };
  }, [
    initialState.loading,
    initialState.result,
    setBaselineEvaluationCallId,
    setComparisonDimension,
    setRangeSelection,
    setSelectedInputDigest,
  ]);

  if (!value) {
    return <div>Loading...</div>;
  }

  return (
    <CompareEvaluationsContext.Provider value={value}>
      {children}
    </CompareEvaluationsContext.Provider>
  );
};
