import * as TableType from '../PanelTable/tableType';

export const ProjectableType = {
  type: 'list' as const,
  objectType: {
    type: 'typedDict' as const,
    propertyTypes: {},
  },
};

export const inputType = {
  type: 'union' as const,
  members: [ProjectableType, TableType.ConvertibleToDataTableType],
};

type tsneAlgorithmOptionsType = {
  perplexity: number;
  learningRate: number;
  iterations: number;
};

type pcaAlgorithmOptionsType = {};

type umapAlgorithmOptionsType = {
  neighbors: number;
  minDist: number;
  spread: number;
};

export type PanelProjectionConverterConfigType = {
  // Hardcoding this to 2 dims for now
  // dimensions?: number;
  projectionAlgorithm: 'tsne' | 'pca' | 'umap';
  inputCardinality: 'single' | 'multiple';
  inputColumnNames: string[];
  algorithmOptions: {
    tsne: tsneAlgorithmOptionsType;
    pca: pcaAlgorithmOptionsType;
    umap: umapAlgorithmOptionsType;
  };
};
