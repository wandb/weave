import {
  Dataset,
  DetailedEvaluationResult,
  EvaluationDefinition,
  EvaluationResult,
  Model,
  Scorer,
} from './types';

// Mock data
const MOCK_DATASETS: Dataset[] = [
  {
    id: 'dataset-1',
    name: 'MNIST Test Set',
    createdAt: '2024-03-20T10:00:00Z',
    samples: [
      {id: 'sample-1', input: 'Image of digit 7'},
      {id: 'sample-2', input: 'Image of digit 3'},
      {id: 'sample-3', input: 'Image of digit 5'},
    ],
  },
  {
    id: 'dataset-2',
    name: 'ImageNet Validation',
    createdAt: '2024-03-19T15:30:00Z',
    samples: [
      {id: 'sample-4', input: 'Image of a cat'},
      {id: 'sample-5', input: 'Image of a dog'},
      {id: 'sample-6', input: 'Image of a bird'},
    ],
  },
];

const MOCK_SCORERS: Scorer[] = [
  {
    id: 'scorer-1',
    name: 'Accuracy Scorer',
    description: 'Basic classification accuracy',
  },
  {
    id: 'scorer-2',
    name: 'F1 Score',
    description: 'Balanced F1 metric',
  },
];

const MOCK_MODELS: Model[] = [
  {
    id: 'model-1',
    name: 'ResNet50',
    description: 'Standard ResNet50 architecture',
  },
  {
    id: 'model-2',
    name: 'ViT-B16',
    description: 'Vision Transformer Base',
  },
];

const MOCK_EVALUATIONS: EvaluationDefinition[] = [
  {
    id: 'eval-1',
    name: 'MNIST Classification Eval',
    dataset: MOCK_DATASETS[0],
    scorers: [MOCK_SCORERS[0]],
    createdAt: '2024-03-20T11:00:00Z',
    lastModified: '2024-03-20T11:00:00Z',
  },
];

const MOCK_EVALUATION_RESULTS: EvaluationResult[] = [
  {
    id: 'result-1',
    evaluationDefinition: MOCK_EVALUATIONS[0],
    model: MOCK_MODELS[0],
    metrics: {
      accuracy: 0.95,
      f1_score: 0.94,
    },
    status: 'completed',
    createdAt: '2024-03-20T12:00:00Z',
  },
];

const MOCK_DETAILED_RESULTS: Record<string, DetailedEvaluationResult> = {
  'result-1': {
    id: 'result-1',
    predictions: [
      {
        sampleId: 'sample-1',
        modelPrediction: '7',
        scores: {
          'scorer-1': 1.0, // Accuracy
          'scorer-2': 0.95, // F1 Score
        },
      },
      {
        sampleId: 'sample-2',
        modelPrediction: '3',
        scores: {
          'scorer-1': 1.0,
          'scorer-2': 0.97,
        },
      },
      {
        sampleId: 'sample-3',
        modelPrediction: '6', // Incorrect prediction
        scores: {
          'scorer-1': 0.0,
          'scorer-2': 0.85,
        },
      },
    ],
  },
};

// API functions
export const fetchEvaluations = async (): Promise<EvaluationDefinition[]> => {
  await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network delay
  return MOCK_EVALUATIONS;
};

export const fetchDatasets = async (): Promise<Dataset[]> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  return MOCK_DATASETS;
};

export const fetchScorers = async (): Promise<Scorer[]> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  return MOCK_SCORERS;
};

export const fetchModels = async (): Promise<Model[]> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  return MOCK_MODELS;
};

export const fetchEvaluationResults = async (
  evaluationId: string
): Promise<EvaluationResult[]> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  return MOCK_EVALUATION_RESULTS.filter(
    r => r.evaluationDefinition.id === evaluationId
  );
};

export const createEvaluation = async (
  name: string,
  datasetId: string,
  scorerIds: string[]
): Promise<EvaluationDefinition> => {
  await new Promise(resolve => setTimeout(resolve, 1000));
  const dataset = MOCK_DATASETS.find(d => d.id === datasetId);
  const scorers = MOCK_SCORERS.filter(s => scorerIds.includes(s.id));

  if (!dataset || scorers.length === 0) {
    throw new Error('Invalid dataset or scorers');
  }

  return {
    id: `eval-${Date.now()}`,
    name,
    dataset,
    scorers,
    createdAt: new Date().toISOString(),
    lastModified: new Date().toISOString(),
  };
};

export const runEvaluation = async (
  evaluationId: string,
  modelId: string
): Promise<EvaluationResult> => {
  await new Promise(resolve => setTimeout(resolve, 2000));
  const evaluation = MOCK_EVALUATIONS.find(e => e.id === evaluationId);
  const model = MOCK_MODELS.find(m => m.id === modelId);

  if (!evaluation || !model) {
    throw new Error('Invalid evaluation or model');
  }

  return {
    id: `result-${Date.now()}`,
    evaluationDefinition: evaluation,
    model,
    metrics: {
      accuracy: Math.random() * 0.2 + 0.8, // Random accuracy between 0.8 and 1.0
      f1_score: Math.random() * 0.2 + 0.8,
    },
    status: 'completed',
    createdAt: new Date().toISOString(),
  };
};

export const fetchDetailedResults = async (
  resultId: string
): Promise<DetailedEvaluationResult> => {
  await new Promise(resolve => setTimeout(resolve, 500));
  const result = MOCK_DETAILED_RESULTS[resultId];
  if (!result) {
    throw new Error('Detailed results not found');
  }
  return result;
};
