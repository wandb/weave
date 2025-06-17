import { GridRowsProp } from '@mui/x-data-grid-pro';

// Page props
export interface EvaluationExplorerPageProps {
  entity: string;
  project: string;
}

// Data types
export interface Dataset {
  id: string;
  name: string;
}

export interface Model {
  id: string;
  name: string;
  description: string;
}

export interface Scorer {
  id: string;
  name: string;
  description?: string;
}

// Row data types
export interface DatasetRow {
  [key: string]: any;
  rowDigest?: string;
}

export interface OutputData {
  [modelId: string]: any[];
}

export interface ScoreData {
  [scorerId: string]: {
    [modelId: string]: {
      score: string;
      reason: string;
    }
  }
}

export interface EvaluationRow {
  id: string;
  dataset: DatasetRow;
  output: OutputData;
  scores: ScoreData;
}

// Configuration Bar props
export interface ConfigurationBarProps {
  selectedDatasetId?: string;
  isDatasetEdited?: boolean;
  onDatasetChange?: (datasetId: string) => void;
  selectedModelIds?: string[];
  onModelsChange?: (modelIds: string[]) => void;
  onModelDetailOpen?: (modelId: string | null) => void;
}

// Section component props
export interface DatasetSectionProps {
  selectedDatasetId?: string;
  isDatasetEdited?: boolean;
  onDatasetChange?: (datasetId: string) => void;
  datasets: Dataset[];
  isLoading: boolean;
}

export interface ModelsSectionProps {
  selectedModelIds?: string[];
  onModelsChange?: (modelIds: string[]) => void;
  models: Model[];
  isLoading: boolean;
  onModelDetailOpen?: (modelId: string) => void;
}

export interface ScorersSectionProps {
  selectedScorerIds?: string[];
  onScorersChange?: (scorerIds: string[]) => void;
  scorers?: Scorer[];
  isLoading?: boolean;
}

export interface ModelDetailPanelProps {
  modelId: string | null;
  onClose: () => void;
}

// Model configuration types
export type ModelType = 'weave-playground' | 'user-defined';

export interface WeavePlaygroundModel {
  id: string;
  name: string;
  description: string;
  foundationModel: string;
  systemTemplate: string;
  userTemplate: string;
}

export interface FoundationModel {
  id: string;
  name: string;
  provider: string;
}

export interface ModelConfiguration {
  type: ModelType;
  weavePlaygroundId?: string;
  name: string;
  description: string;
  foundationModel?: string;
  systemTemplate?: string;
  userTemplate?: string;
} 