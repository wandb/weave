import {Box} from '@material-ui/core';
import {useDeepMemo} from '@wandb/weave/hookUtils';
import React, {useEffect, useMemo, useRef, useState} from 'react';

import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {useEvaluationComparisonState} from './ecpState';
import {EvaluationComparisonState} from './ecpState';
import {ComparisonDimensionsType} from './ecpState';

export type CompareEvaluationContext = {
  state: EvaluationComparisonState;
  setComparisonDimensions: React.Dispatch<
    React.SetStateAction<ComparisonDimensionsType | null>
  >;
  setSelectedInputDigest: React.Dispatch<React.SetStateAction<string | null>>;
  setSelectedMetrics: (newModel: Record<string, boolean>) => void;
  addEvaluationCall: (newCallId: string) => void;
  removeEvaluationCall: (callId: string) => void;
  setEvaluationCallOrder: (newCallIdOrder: string[]) => void;
  hiddenEvaluationIds: Set<string>;
  toggleHideEvaluation: (callId: string) => void;

  getCachedRowData: (digest: string) => any;
  setCachedRowData: (digest: string, data: any) => void;

  // Flag to indicate if we should filter to latest evaluations per model (leaderboard mode)
  filterToLatestEvaluationsPerModel?: boolean;
};

const CompareEvaluationsContext =
  React.createContext<CompareEvaluationContext | null>(null);

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
  filterToLatestEvaluationsPerModel?: boolean;
  colorByModel?: boolean;
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
  filterToLatestEvaluationsPerModel = false,
  colorByModel = false,
  children,
}) => {
  const initialEvaluationCallIdsMemo = useDeepMemo(initialEvaluationCallIds);
  const [evaluationCallIds, setEvaluationCallIds] = useState(
    initialEvaluationCallIdsMemo
  );
  const [hiddenEvaluationIds, setHiddenEvaluationIds] = useState<Set<string>>(
    new Set()
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
    selectedMetrics ?? undefined,
    colorByModel
  );

  // Here we use a ref instead of a state to avoid re-rendering the component when the cache is updated
  const resultRowCache = useRef<Record<string, any>>({});

  const value = useMemo(() => {
    if (initialState.loading || initialState.result == null) {
      return null;
    }
    const setCachedRowData = (digest: string, data: any) => {
      resultRowCache.current[digest] = data;
    };
    const getCachedRowData = (digest: string) => {
      return (
        resultRowCache.current[digest] ??
        initialState.result?.loadableComparisonResults?.result?.resultRows?.[
          digest
        ]?.rawDataRow
      );
    };
    const toggleHideEvaluation = (callId: string) => {
      setHiddenEvaluationIds(prev => {
        const next = new Set(prev);
        if (next.has(callId)) {
          next.delete(callId);
        } else {
          next.add(callId);
        }
        return next;
      });
    };
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
      hiddenEvaluationIds,
      toggleHideEvaluation,
      getCachedRowData,
      setCachedRowData,
      filterToLatestEvaluationsPerModel,
    };
  }, [
    initialState.loading,
    initialState.result,
    setComparisonDimensions,
    setSelectedInputDigest,
    setSelectedMetrics,
    evaluationCallIds,
    hiddenEvaluationIds,
    onEvaluationCallIdsUpdate,
    filterToLatestEvaluationsPerModel,
  ]);

  if (!value) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2,
          py: 4,
        }}>
        <LoadingDots />
      </Box>
    );
  }

  return (
    <CompareEvaluationsContext.Provider value={value}>
      {children}
    </CompareEvaluationsContext.Provider>
  );
};