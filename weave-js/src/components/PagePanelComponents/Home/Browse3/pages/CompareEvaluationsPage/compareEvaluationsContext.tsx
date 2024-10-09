import {Box} from '@material-ui/core';
import React, {useMemo} from 'react';

import {WeaveLoader} from '../../../../../../common/components/WeaveLoader';
import {LinearProgress} from '../../../../../LinearProgress';
import {useEvaluationComparisonState} from './ecpState';
import {EvaluationComparisonState} from './ecpState';
import {ComparisonDimensionsType} from './ecpState';

const CompareEvaluationsContext = React.createContext<{
  state: EvaluationComparisonState;
  setBaselineEvaluationCallId: React.Dispatch<
    React.SetStateAction<string | null>
  >;
  setComparisonDimensions: React.Dispatch<
    React.SetStateAction<ComparisonDimensionsType | null>
  >;
  setSelectedInputDigest: React.Dispatch<React.SetStateAction<string | null>>;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
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
  selectedMetrics: Record<string, boolean>;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;

  setBaselineEvaluationCallId: React.Dispatch<
    React.SetStateAction<string | null>
  >;
  setComparisonDimensions: React.Dispatch<
    React.SetStateAction<ComparisonDimensionsType | null>
  >;
  setSelectedInputDigest: React.Dispatch<React.SetStateAction<string | null>>;
  baselineEvaluationCallId?: string;
  comparisonDimensions?: ComparisonDimensionsType;
  selectedInputDigest?: string;
}> = ({
  entity,
  project,
  evaluationCallIds,
  selectedMetrics,
  setSelectedMetrics,

  setBaselineEvaluationCallId,
  setComparisonDimensions,

  setSelectedInputDigest,
  baselineEvaluationCallId,
  comparisonDimensions,
  selectedInputDigest,
  children,
}) => {
  const initialState = useEvaluationComparisonState(
    entity,
    project,
    evaluationCallIds,
    baselineEvaluationCallId,
    comparisonDimensions,
    selectedInputDigest,
    selectedMetrics
  );

  const value = useMemo(() => {
    if (initialState.loading || initialState.result == null) {
      return null;
    }
    return {
      state: initialState.result,
      setBaselineEvaluationCallId,
      setComparisonDimensions,
      setSelectedInputDigest,
      setSelectedMetrics,
    };
  }, [
    initialState.loading,
    initialState.result,
    setBaselineEvaluationCallId,
    setComparisonDimensions,
    setSelectedInputDigest,
    setSelectedMetrics,
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
