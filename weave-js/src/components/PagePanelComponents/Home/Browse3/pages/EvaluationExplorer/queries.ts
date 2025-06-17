import { Dataset, Model, Scorer } from './types';

// Placeholder hook for available datasets
export const useAvailableDatasets = () => {
  // TODO: Replace with actual API call
  return {
    datasets: [
      { id: 'dataset-1', name: 'Customer Service v1' },
      { id: 'dataset-2', name: 'Customer Service v2' },
      { id: 'dataset-3', name: 'Product Reviews' },
      { id: 'dataset-4', name: 'Support Tickets' },
    ] as Dataset[],
    isLoading: false
  };
};

// Placeholder hook for available models
export const useAvailableModels = () => {
  // TODO: Replace with actual API call
  return {
    models: [
      { id: 'gpt-4', name: 'GPT-4', description: 'OpenAI GPT-4' },
      { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', description: 'OpenAI GPT-3.5 Turbo' },
      { id: 'claude-2', name: 'Claude 2', description: 'Anthropic Claude 2' },
      { id: 'llama-2-70b', name: 'Llama 2 70B', description: 'Meta Llama 2' },
      { id: 'custom-model-1', name: 'Custom Fine-tuned Model', description: 'Your custom model' },
    ] as Model[],
    isLoading: false
  };
};

// Placeholder hook for available scorers
export const useAvailableScorers = () => {
  // TODO: Replace with actual API call
  return {
    scorers: [
      { id: 'accuracy', name: 'Accuracy Scorer', description: 'Measures response accuracy' },
      { id: 'relevance', name: 'Relevance Scorer', description: 'Measures response relevance' },
      { id: 'tone', name: 'Tone Scorer', description: 'Evaluates response tone' },
    ] as Scorer[],
    isLoading: false
  };
}; 