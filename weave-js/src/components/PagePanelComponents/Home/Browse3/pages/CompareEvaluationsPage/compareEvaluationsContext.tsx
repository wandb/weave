import {Box} from '@material-ui/core';
import React, {useMemo, useState} from 'react';

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
  addEvaluationCall: (newCallId: string) => void;
  removeEvaluationCall: (callId: string) => void;
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
  initialEvaluationCallIds: string[];
  onEvaluationCallIdsUpdate: (newEvaluationCallIds: string[]) => void;
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
  initialEvaluationCallIds,
  onEvaluationCallIdsUpdate,
  setBaselineEvaluationCallId,
  setComparisonDimensions,

  setSelectedInputDigest,

  baselineEvaluationCallId,
  comparisonDimensions,
  selectedInputDigest,
  children,
}) => {
  const [evaluationCallIds, setEvaluationCallIds] = useState(
    initialEvaluationCallIds
  );
  const initialState = useEvaluationComparisonState(
    entity,
    project,
    evaluationCallIds,
    baselineEvaluationCallId,
    comparisonDimensions,
    selectedInputDigest
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
      addEvaluationCall: (newCallId: string) => {
        const newEvaluationCallIds = [...evaluationCallIds, newCallId];
        setEvaluationCallIds(newEvaluationCallIds);
        onEvaluationCallIdsUpdate(newEvaluationCallIds);
      },
      removeEvaluationCall: (callId: string) => {
        const newEvaluationCallIds = evaluationCallIds.filter(
          id => id !== callId
        );
        setEvaluationCallIds(newEvaluationCallIds);
        onEvaluationCallIdsUpdate(newEvaluationCallIds);
      },
    };
  }, [
    initialState.loading,
    initialState.result,
    evaluationCallIds,
    onEvaluationCallIdsUpdate,
    setEvaluationCallIds,
    setBaselineEvaluationCallId,
    setComparisonDimensions,
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
