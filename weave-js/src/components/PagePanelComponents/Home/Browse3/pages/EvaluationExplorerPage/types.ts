export type EvaluationExplorationConfig = {
  // The definition of the evaluation to run
  evaluationDefinition: {
    // The Weave Ref pointing to the evaluation definition
    originalSourceRef: string | null;
    // Whether the properties deviated from the referenced source
    dirtied: boolean;
    properties: {
      // The name of the evaluation
      name: string;
      // The description of the evaluation
      description: string;
      // The definition of the dataset to use
      dataset: {
        // The Weave Ref pointing to the dataset definition
        originalSourceRef: string | null;
      };
      // The array of scorer functions to evaluate model outputs
      scorers: Array<{
        // The Weave Ref pointing to the scorer definition
        originalSourceRef: string | null;
      }>;
    };
  };
  // The array of models to evaluate
  models: Array<{
    // The Weave Ref pointing to the model definition
    originalSourceRef: string | null;
  }>;
};

export type SimplifiedLLMAsAJudgeScorer = {
  name: string;
  scoreType: 'boolean' | 'number';
  llmModelId: string;
  prompt: string;
};

export type SimplifiedLLMStructuredCompletionModel = {
  name: string;
  llmModelId: string;
  systemPrompt: string;
};
