import {EvaluationExplorationConfig} from './types';

export const initializeEmptyConfig = (): EvaluationExplorationConfig => {
  return {
    evaluationDefinition: {
      originalSourceRef: null,
      dirtied: false,
      properties: {
        name: '',
        description: '',
        dataset: {
          originalSourceRef: null,
        },
        scorers: [],
      },
    },
    models: [],
  };
};
