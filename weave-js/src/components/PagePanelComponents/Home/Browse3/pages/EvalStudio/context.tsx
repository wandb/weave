import React, { createContext, useContext, useState } from 'react';
import { EvalStudioContextState, EvalStudioContextValue } from './types';

const initialState: EvalStudioContextState = {
  selectedEvaluation: null,
  selectedDataset: null,
  selectedScorers: [],
  evaluationName: '',
  isCreatingNewEval: false,
  isCreatingNewDataset: false,
  isCreatingNewScorer: false,
  selectedResult: null,
};

const EvalStudioContext = createContext<EvalStudioContextValue | undefined>(undefined);

export const EvalStudioProvider: React.FC<{children: React.ReactNode}> = ({ children }) => {
  const [state, setState] = useState<EvalStudioContextState>(initialState);

  const value: EvalStudioContextValue = {
    ...state,
    setSelectedEvaluation: (evaluation) => 
      setState(prev => ({ ...prev, selectedEvaluation: evaluation })),
    setSelectedDataset: (dataset) => 
      setState(prev => ({ ...prev, selectedDataset: dataset })),
    setSelectedScorers: (scorers) => 
      setState(prev => ({ ...prev, selectedScorers: scorers })),
    setEvaluationName: (name) => 
      setState(prev => ({ ...prev, evaluationName: name })),
    setIsCreatingNewEval: (isCreating) => 
      setState(prev => ({ ...prev, isCreatingNewEval: isCreating })),
    setIsCreatingNewDataset: (isCreating) => 
      setState(prev => ({ ...prev, isCreatingNewDataset: isCreating })),
    setIsCreatingNewScorer: (isCreating) => 
      setState(prev => ({ ...prev, isCreatingNewScorer: isCreating })),
    setSelectedResult: (result) =>
      setState(prev => ({ ...prev, selectedResult: result })),
  };

  return (
    <EvalStudioContext.Provider value={value}>
      {children}
    </EvalStudioContext.Provider>
  );
};

export const useEvalStudio = () => {
  const context = useContext(EvalStudioContext);
  if (context === undefined) {
    throw new Error('useEvalStudio must be used within an EvalStudioProvider');
  }
  return context;
}; 