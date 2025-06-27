import {EvaluationExplorationConfig} from './types';

export const initializeEmptyConfig = (): EvaluationExplorationConfig => {
  return {
    evaluationDefinition: {
      originalSourceRef: null,
      properties: {
        name: 'Baseline Evaluation',
        description: '',
        dataset: {
          originalSourceRef: null,
        },
        scorers: [
          {
            originalSourceRef: null,
          },
        ],
      },
    },
    models: [
      {
        originalSourceRef: null,
      },
    ],
  };
};

export const defaultModelConfigPayload = {
  name: 'Simple Model',
  llmModelId: '',
  systemPrompt: 'You are a helpful assistant.',
};

export const defaultScorerConfigPayload = {
  name: 'Correctness',
  scoreType: 'boolean' as const,
  llmModelId: '',
  prompt: `Given a user input, expected output, and model output, determine how correct the model output is. Exact match is not required. 
User Input: {user_input}
---
Expected Output: {expected_output}
---
Model Output: {output}
---
Is the model output correct?`,
};
