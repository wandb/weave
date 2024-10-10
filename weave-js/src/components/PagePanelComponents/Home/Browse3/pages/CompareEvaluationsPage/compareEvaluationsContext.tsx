import {Box} from '@material-ui/core';
import React, {useMemo, useState} from 'react';

import {WeaveLoader} from '../../../../../../common/components/WeaveLoader';
import {LinearProgress} from '../../../../../LinearProgress';
import {useEvaluationComparisonState} from './ecpState';
import {EvaluationComparisonState} from './ecpState';
import {ComparisonDimensionsType} from './ecpState';

const CompareEvaluationsContext = React.createContext<{
  state: EvaluationComparisonState;
  setSelectedCallIdsOrdered: React.Dispatch<React.SetStateAction<string[]>>;
  setComparisonDimensions: React.Dispatch<
    React.SetStateAction<ComparisonDimensionsType | null>
  >;
  setSelectedInputDigest: React.Dispatch<React.SetStateAction<string | null>>;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
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
  selectedCallIdsOrdered: string[];
  setSelectedCallIdsOrdered: React.Dispatch<React.SetStateAction<string[]>>;
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
  setSelectedCallIdsOrdered,
  selectedCallIdsOrdered,
  selectedMetrics,
  setSelectedMetrics,
  onEvaluationCallIdsUpdate,
  setComparisonDimensions,
  setSelectedInputDigest,
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
    selectedCallIdsOrdered,
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
      setSelectedCallIdsOrdered,
      setComparisonDimensions,
      setSelectedInputDigest,
      setSelectedMetrics,
      addEvaluationCall: (newCallId: string) => {
        const newEvaluationCallIds = [...evaluationCallIds, newCallId];
        setEvaluationCallIds(newEvaluationCallIds);
        setSelectedCallIdsOrdered(newEvaluationCallIds);
        onEvaluationCallIdsUpdate(newEvaluationCallIds);
      },
      removeEvaluationCall: (callId: string) => {
        const newEvaluationCallIds = evaluationCallIds.filter(
          id => id !== callId
        );
        setEvaluationCallIds(newEvaluationCallIds);
        setSelectedCallIdsOrdered(newEvaluationCallIds);
        onEvaluationCallIdsUpdate(newEvaluationCallIds);
      },
    };
  }, [
    initialState.loading,
    initialState.result,
    setEvaluationCallIds,
    setSelectedCallIdsOrdered,
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
