import {makeRefObject} from '@wandb/weave/util/refs';

import {DirectTraceServerClient} from '../wfReactInterface/traceServerDirectClient';
import {StatusCodeType} from '../wfReactInterface/tsDataModelHooks';
import {
  Dataset,
  EvaluationDefinition as Evaluation,
  EvaluationResult,
  Model,
} from './types';

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
export const fetchDatasets = async (
  client: DirectTraceServerClient,
  entity: string,
  project: string
): Promise<Dataset[]> => {
  const res = await client.objsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      base_object_classes: ['Dataset'],
      latest_only: true,
    },
    metadata_only: true,
  });
  return res.objs.map(o => {
    return {
      entity,
      project,
      name: o.object_id,
      digest: o.digest,
      createdAt: new Date(o.created_at),
      objectRef: makeRefObject(
        entity,
        project,
        'object',
        o.object_id,
        o.digest,
        undefined
      ),
    };
  });
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
