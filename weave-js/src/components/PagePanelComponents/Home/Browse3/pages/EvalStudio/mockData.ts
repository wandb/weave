import {StatusCodeType} from '../wfReactInterface/tsDataModelHooks';
import {
  Dataset,
  DatasetSample,
  EvaluationDefinition as Evaluation,
  EvaluationResult,
  Model,
} from './types';

// Mock data
const mockDatasetSamples: DatasetSample[] = [
  {id: '1', input: 'What is machine learning?'},
  {id: '2', input: 'Explain neural networks'},
  {id: '3', input: 'How does backpropagation work?'},
];

export const mockDatasets: Dataset[] = [
  {
    id: '1',
    name: 'ML Questions Dataset',
    createdAt: new Date().toISOString(),
    samples: mockDatasetSamples,
  },
  {
    id: '2',
    name: 'NLP Dataset',
    createdAt: new Date().toISOString(),
    samples: mockDatasetSamples,
  },
];

export const mockModels: Model[] = [
  {
    id: '1',
    name: 'GPT-4',
    description: 'Latest GPT model',
  },
  {
    id: '2',
    name: 'Claude',
    description: "Anthropic's model",
  },
];

export const mockEvaluations: Evaluation[] = [
  {
    entity: 'wandb',
    project: 'eval-studio',
    objectId: '1',
    objectDigest: 'abc123',
    evaluationRef: 'eval1',
    displayName: 'ML Questions Evaluation',
    createdAt: new Date(),
    datasetRef: '1',
    scorerRefs: ['scorer1', 'scorer2'],
  },
  {
    entity: 'wandb',
    project: 'eval-studio',
    objectId: '2',
    objectDigest: 'def456',
    evaluationRef: 'eval2',
    displayName: 'NLP Evaluation',
    createdAt: new Date(),
    datasetRef: '2',
    scorerRefs: ['scorer1'],
  },
];

export const mockResults: EvaluationResult[] = [
  {
    entity: 'wandb',
    project: 'eval-studio',
    callId: '1',
    evaluationRef: 'eval1',
    modelRef: '1',
    createdAt: new Date('2024-03-15'),
    metrics: {
      accuracy: 0.95,
      f1Score: 0.94,
      latency: 120.0,
    },
    status: 'SUCCESS' as StatusCodeType,
  },
  {
    entity: 'wandb',
    project: 'eval-studio',
    callId: '2',
    evaluationRef: 'eval1',
    modelRef: '2',
    createdAt: new Date('2024-03-15'),
    metrics: {
      accuracy: 0.92,
      f1Score: 0.91,
      latency: 150.0,
    },
    status: 'SUCCESS' as StatusCodeType,
  },
  {
    entity: 'wandb',
    project: 'eval-studio',
    callId: '3',
    evaluationRef: 'eval1',
    modelRef: '1',
    createdAt: new Date('2024-03-14'),
    metrics: {
      accuracy: 0.955,
      f1Score: 0.945,
      latency: 118.0,
    },
    status: 'SUCCESS' as StatusCodeType,
  },
  {
    entity: 'wandb',
    project: 'eval-studio',
    callId: '4',
    evaluationRef: 'eval2',
    modelRef: '1',
    createdAt: new Date('2024-03-14'),
    metrics: {
      accuracy: 0.94,
      f1Score: 0.93,
      latency: 122.0,
    },
    status: 'SUCCESS' as StatusCodeType,
  },
];

// Mock API functions
export const fetchDatasets = async (): Promise<Dataset[]> => {
  await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network delay
  return mockDatasets;
};

export const fetchEvaluations = async (
  datasetId: string
): Promise<Evaluation[]> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  return mockEvaluations.filter(e => e.datasetRef === datasetId);
};

export const fetchModels = async (evaluationId: string): Promise<Model[]> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  return mockModels;
};

export const fetchModelResults = async (
  evaluationId: string,
  modelId: string
): Promise<EvaluationResult[]> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  return mockResults.filter(
    r => r.evaluationRef === evaluationId && r.modelRef === modelId
  );
};
