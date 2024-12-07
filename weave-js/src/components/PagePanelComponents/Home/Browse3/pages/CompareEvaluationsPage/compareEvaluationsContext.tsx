import {Box} from '@material-ui/core';
import {useDeepMemo} from '@wandb/weave/hookUtils';
import React, {useEffect, useMemo, useState} from 'react';

import {WeaveLoader} from '../../../../../../common/components/WeaveLoader';
import {LinearProgress} from '../../../../../LinearProgress';
import {useEvaluationComparisonState} from './ecpState';
import {EvaluationComparisonState} from './ecpState';
import {ComparisonDimensionsType} from './ecpState';

const CompareEvaluationsContext = React.createContext<{
  state: EvaluationComparisonState;
  setComparisonDimensions: React.Dispatch<
    React.SetStateAction<ComparisonDimensionsType | null>
  >;
  setSelectedInputDigest: React.Dispatch<React.SetStateAction<string | null>>;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
  addEvaluationCall: (newCallId: string) => void;
  removeEvaluationCall: (callId: string) => void;
  setEvaluationCallOrder: (newCallIdOrder: string[]) => void;
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
  selectedMetrics: Record<string, boolean> | null;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;

  onEvaluationCallIdsUpdate: (newEvaluationCallIds: string[]) => void;
  setComparisonDimensions: React.Dispatch<
    React.SetStateAction<ComparisonDimensionsType | null>
  >;
  setSelectedInputDigest: React.Dispatch<React.SetStateAction<string | null>>;
  comparisonDimensions?: ComparisonDimensionsType;
  selectedInputDigest?: string;
}> = ({
  entity,
  project,
  initialEvaluationCallIds,
  selectedMetrics,
  setSelectedMetrics,
  onEvaluationCallIdsUpdate,
  setComparisonDimensions,
  setSelectedInputDigest,
  comparisonDimensions,
  selectedInputDigest,
  children,
}) => {
  const initialEvaluationCallIdsMemo = useDeepMemo(initialEvaluationCallIds);
  const [evaluationCallIds, setEvaluationCallIds] = useState(
    initialEvaluationCallIdsMemo
  );
  useEffect(() => {
    setEvaluationCallIds(initialEvaluationCallIdsMemo);
  }, [initialEvaluationCallIdsMemo]);

  const initialState = useEvaluationComparisonState(
    entity,
    project,
    evaluationCallIds,
    comparisonDimensions,
    selectedInputDigest,
    selectedMetrics ?? undefined
  );

  const value = useMemo(() => {
    if (initialState.loading || initialState.result == null) {
      return null;
    }
    return {
      state: initialState.result,
      setComparisonDimensions,
      setSelectedInputDigest,
      setSelectedMetrics,
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
      setEvaluationCallOrder: (newCallIdOrder: string[]) => {
        setEvaluationCallIds(newCallIdOrder);
        onEvaluationCallIdsUpdate(newCallIdOrder);
      },
    };
  }, [
    initialState.loading,
    initialState.result,
    setEvaluationCallIds,
    evaluationCallIds,
    onEvaluationCallIdsUpdate,
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
