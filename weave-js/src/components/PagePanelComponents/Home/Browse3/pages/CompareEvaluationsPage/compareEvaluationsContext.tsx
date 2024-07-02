import React, {useMemo} from 'react';

import {EvaluationComparisonData} from './evaluationResults';
import {ScoreDimension} from './evaluations';
import {RangeSelection, useInitialState} from './initialize';

const CompareEvaluationsContext = React.createContext<{
  state: EvaluationComparisonState;
  setBaselineEvaluationCallId: React.Dispatch<
    React.SetStateAction<string | null>
  >;
  setComparisonDimension: React.Dispatch<
    React.SetStateAction<ScoreDimension | null>
  >;
  setRangeSelection: React.Dispatch<React.SetStateAction<RangeSelection>>;
} | null>(null);

export type EvaluationComparisonState = {
  data: EvaluationComparisonData;
  baselineEvaluationCallId: string;
  comparisonDimension: ScoreDimension;
  rangeSelection: RangeSelection;
};

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
  rangeSelection?: RangeSelection;
  baselineEvaluationCallId?: string;
  comparisonDimension?: ScoreDimension;
}> = ({
  entity,
  project,
  evaluationCallIds,
  setBaselineEvaluationCallId,
  setComparisonDimension,
  setRangeSelection,
  rangeSelection,
  baselineEvaluationCallId,
  comparisonDimension,
  children,
}) => {
  const initialState = useInitialState(
    entity,
    project,
    evaluationCallIds,
    baselineEvaluationCallId,
    comparisonDimension,
    rangeSelection
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
    };
  }, [
    initialState.loading,
    initialState.result,
    setBaselineEvaluationCallId,
    setComparisonDimension,
    setRangeSelection,
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
