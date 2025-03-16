import {makeRefObject} from '@wandb/weave/util/refs';

import {DirectTraceServerClient} from '../wfReactInterface/traceServerDirectClient';
import {
  Dataset,
  DetailedEvaluationResult,
  EvaluationDefinition,
  EvaluationResult,
  Model,
  Scorer,
} from './types';

// Mock data
const MOCK_DATASETS: Dataset[] = [];
const MOCK_SCORERS: Scorer[] = [];
const MOCK_MODELS: Model[] = [];
const MOCK_EVALUATIONS: EvaluationDefinition[] = [];
const MOCK_EVALUATION_RESULTS: EvaluationResult[] = [];
const MOCK_DETAILED_RESULTS: Record<string, DetailedEvaluationResult> = {};

// API functions
export const fetchEvaluations = async (
  client: DirectTraceServerClient,
  entity: string,
  project: string
): Promise<EvaluationDefinition[]> => {
  const res = await client.objsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      base_object_classes: ['Evaluation'],
    },
  });
  return res.objs.map(obj => {
    return {
      entity,
      project,
      objectId: obj.object_id,
      objectDigest: obj.digest,
      evaluationRef: makeRefObject(
        entity,
        project,
        'object',
        obj.object_id,
        obj.digest,
        undefined
      ),
      displayName: obj.val.name ?? obj.object_id,
      createdAt: new Date(obj.created_at),
      datasetRef: obj.val.dataset,
      scorerRefs: obj.val.scorers,
    };
  });
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
  return [];
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

  return {};
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
