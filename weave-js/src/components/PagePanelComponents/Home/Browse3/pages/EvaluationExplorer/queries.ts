import { Dataset, Model, Scorer, WeavePlaygroundModel, FoundationModel } from './types';

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

// Placeholder hook for pre-configured Weave Playground models
export const useWeavePlaygroundModels = () => {
  // TODO: Replace with actual API call
  return {
    models: [
      { 
        id: 'customer-support-agent', 
        name: 'Customer Support Agent',
        description: 'Friendly and helpful customer service responses',
        foundationModel: 'gpt-4',
        systemTemplate: 'You are a helpful and friendly customer support agent. Always be polite and try to solve the customer\'s problem.',
        userTemplate: 'Customer Query: {{query}}\n\nPlease provide a helpful response.'
      },
      {
        id: 'code-reviewer',
        name: 'Code Reviewer',
        description: 'Technical code review assistant',
        foundationModel: 'claude-2',
        systemTemplate: 'You are an expert code reviewer. Provide constructive feedback on code quality, best practices, and potential improvements.',
        userTemplate: 'Code to review:\n```\n{{code}}\n```\n\nProvide your review:'
      },
      {
        id: 'summarizer',
        name: 'Text Summarizer',
        description: 'Concise text summarization',
        foundationModel: 'gpt-3.5-turbo',
        systemTemplate: 'You are a text summarization expert. Create clear, concise summaries that capture the key points.',
        userTemplate: 'Text to summarize:\n{{text}}\n\nProvide a summary:'
      }
    ] as WeavePlaygroundModel[],
    isLoading: false
  };
};

// Placeholder hook for available foundation models
export const useFoundationModels = () => {
  // TODO: Replace with actual API call
  return {
    models: [
      { id: 'gpt-4', name: 'GPT-4', provider: 'OpenAI' },
      { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', provider: 'OpenAI' },
      { id: 'claude-2', name: 'Claude 2', provider: 'Anthropic' },
      { id: 'claude-instant', name: 'Claude Instant', provider: 'Anthropic' },
      { id: 'llama-2-70b', name: 'Llama 2 70B', provider: 'Meta' },
      { id: 'llama-2-13b', name: 'Llama 2 13B', provider: 'Meta' },
      { id: 'palm-2', name: 'PaLM 2', provider: 'Google' },
    ] as FoundationModel[],
    isLoading: false
  };
}; 