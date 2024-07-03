import {Box, LinearProgress} from '@material-ui/core';
import React, {useMemo} from 'react';

import {WeaveLoader} from '../../../../../../common/components/WeaveLoader';
import {useEvaluationComparisonState} from './ecpState';
import {RangeSelection} from './ecpTypes';
import {EvaluationMetricDimension} from './ecpTypes';
import {EvaluationComparisonState} from './ecpTypes';

const CompareEvaluationsContext = React.createContext<{
  state: EvaluationComparisonState;
  setBaselineEvaluationCallId: React.Dispatch<
    React.SetStateAction<string | null>
  >;
  setComparisonDimension: React.Dispatch<
    React.SetStateAction<EvaluationMetricDimension | null>
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
    React.SetStateAction<EvaluationMetricDimension | null>
  >;
  setRangeSelection: React.Dispatch<React.SetStateAction<RangeSelection>>;
  setSelectedInputDigest: React.Dispatch<React.SetStateAction<string | null>>;
  rangeSelection?: RangeSelection;
  baselineEvaluationCallId?: string;
  comparisonDimension?: EvaluationMetricDimension;
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
  const initialState = useEvaluationComparisonState(
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
    return (
      <Box>
        <WeaveLoader />
        <LinearProgress variant="indeterminate" />
      </Box>
    );
  }

  return (
    <CompareEvaluationsContext.Provider value={value}>
      {children}
    </CompareEvaluationsContext.Provider>
  );
};
