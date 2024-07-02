import React, {useMemo} from 'react';

import {EvaluationComparisonData} from './evaluationResults';
import {useInitialState} from './initialize';

const CompareEvaluationsContext = React.createContext<{
  state: EvaluationComparisonState;
  setBaselineEvaluationCallId: React.Dispatch<
    React.SetStateAction<string | null>
  >;
  setComparisonDimension: React.Dispatch<React.SetStateAction<string | null>>;
} | null>(null);

export type EvaluationComparisonState = {
  data: EvaluationComparisonData;
  baselineEvaluationCallId: string;
  comparisonDimension: string;
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
  setComparisonDimension: React.Dispatch<React.SetStateAction<string | null>>;
  baselineEvaluationCallId?: string;
  comparisonDimension?: string;
}> = ({
  entity,
  project,
  evaluationCallIds,
  setBaselineEvaluationCallId,
  setComparisonDimension,
  baselineEvaluationCallId,
  comparisonDimension,
  children,
}) => {
  const initialState = useInitialState(
    entity,
    project,
    evaluationCallIds,
    baselineEvaluationCallId,
    comparisonDimension
  );

  const value = useMemo(() => {
    if (initialState.loading || initialState.result == null) {
      return null;
    }
    return {
      state: initialState.result,
      setBaselineEvaluationCallId,
      setComparisonDimension,
    };
  }, [initialState, setBaselineEvaluationCallId, setComparisonDimension]);

  if (!value) {
    return <div>Loading...</div>;
  }

  return (
    <CompareEvaluationsContext.Provider value={value}>
      {children}
    </CompareEvaluationsContext.Provider>
  );
};
