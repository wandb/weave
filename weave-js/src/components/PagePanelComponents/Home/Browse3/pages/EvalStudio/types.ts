import {StatusCodeType} from '../wfReactInterface/tsDataModelHooks';

export interface DatasetSample {
  id: string;
  input: string; // This could be more specific based on your needs
}

export interface Dataset {
  entity: string;
  project: string;
  name: string;
  digest: string;
  objectRef: string;
  createdAt: Date;
  // // Adding sample data field for demonstration
  // samples: DatasetSample[];
}

export interface Scorer {
  id: string;
  name: string;
  description?: string;
}

export interface Model {
  id: string;
  name: string;
  description?: string;
}

export interface EvaluationDefinition {
  entity: string;
  project: string;
  objectId: string;
  objectDigest: string;
  evaluationRef: string;
  displayName: string;
  createdAt: Date;
  datasetRef: string;
  scorerRefs: string[];
}

export interface PredictionResult {
  sampleId: string;
  modelPrediction: string; // This could be more specific based on your needs
  scores: Record<string, number>; // Keyed by scorer ID
}

export interface DetailedEvaluationResult {
  id: string;
  predictions: PredictionResult[];
}

export interface EvaluationResult {
  entity: string;
  project: string;
  callId: string;
  evaluationRef: string;
  modelRef: string;
  createdAt: Date;
  metrics: Record<string, unknown>;
  status: StatusCodeType;
}

// Context types for managing evaluation creation flow
export interface EvalStudioContextState {
  selectedEvaluation: EvaluationDefinition | null;
  selectedDataset: Dataset | null;
  selectedScorers: Scorer[];
  evaluationName: string;
  isCreatingNewEval: boolean;
  isCreatingNewDataset: boolean;
  isCreatingNewScorer: boolean;
  selectedResult: EvaluationResult | null;
}

export interface EvalStudioContextValue extends EvalStudioContextState {
  setSelectedEvaluation: (evaluation: EvaluationDefinition | null) => void;
  setSelectedDataset: (dataset: Dataset | null) => void;
  setSelectedScorers: (scorers: Scorer[]) => void;
  setEvaluationName: (name: string) => void;
  setIsCreatingNewEval: (isCreating: boolean) => void;
  setIsCreatingNewDataset: (isCreating: boolean) => void;
  setIsCreatingNewScorer: (isCreating: boolean) => void;
  setSelectedResult: (result: EvaluationResult | null) => void;
}
