import {parseWeaveRef} from '@wandb/weave/react';
import {makeRefObject} from '@wandb/weave/util/refs';

import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {convertTraceServerObjectVersionToSchema} from '../wfReactInterface/tsDataModelHooks';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';

export const getLatestEvaluationRefs = async (
  client: TraceServerClient,
  entity: string,
  project: string
): Promise<string[]> => {
  const res = await client.objsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      base_object_classes: ['Evaluation'],
      latest_only: true,
    },
    // TODO: Add pagination or smarter filtering.
    limit: 1000,
    metadata_only: true,
  });
  return res.objs.map(o =>
    makeRefObject(entity, project, 'object', o.object_id, o.digest, undefined)
  );
};

export const getLatestDatasetRefs = async (
  client: TraceServerClient,
  entity: string,
  project: string
): Promise<string[]> => {
  const res = await client.objsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      base_object_classes: ['Dataset'],
      latest_only: true,
    },
    // TODO: Add pagination or smarter filtering.
    limit: 1000,
    metadata_only: true,
  });
  return res.objs.map(o =>
    makeRefObject(entity, project, 'object', o.object_id, o.digest, undefined)
  );
};

export const getLatestScorerRefs = async (
  client: TraceServerClient,
  entity: string,
  project: string
): Promise<string[]> => {
  const res = await client.objsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      leaf_object_classes: ['LLMAsAJudgeScorer'],
      latest_only: true,
    },
    // TODO: Add pagination or smarter filtering.
    limit: 1000,
    metadata_only: true,
  });
  return res.objs.map(o =>
    makeRefObject(entity, project, 'object', o.object_id, o.digest, undefined)
  );
};

export const getLatestModelRefs = async (
  client: TraceServerClient,
  entity: string,
  project: string
): Promise<string[]> => {
  const res = await client.objsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      leaf_object_classes: ['LLMStructuredCompletionModel'],
      latest_only: true,
    },
    // TODO: Add pagination or smarter filtering.
    limit: 1000,
    metadata_only: true,
  });
  return res.objs.map(o =>
    makeRefObject(entity, project, 'object', o.object_id, o.digest, undefined)
  );
};

export const getObjByRef = async (
  client: TraceServerClient,
  ref?: string | null
): Promise<ObjectVersionSchema | null> => {
  if (!ref) {
    return null;
  }

  const parsedRef = parseWeaveRef(ref);

  if (parsedRef.weaveKind !== 'object') {
    return null;
  }

  const res = await client.objRead({
    project_id: `${parsedRef.entityName}/${parsedRef.projectName}`,
    object_id: parsedRef.artifactName,
    digest: parsedRef.artifactVersion,
  });

  return convertTraceServerObjectVersionToSchema(res.obj);
};

type CreateEvaluationSpec = {
  name: string;
  description: string;
  datasetRef: string;
  scorerRefs: string[];
};

export const createEvaluation = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: CreateEvaluationSpec
): Promise<string> => {
  // TODO: Sanitize name
  const objectId = spec.name;
  const evaluationObjectVal = {
    _type: 'Evaluation',
    name: spec.name,
    description: spec.description,
    dataset: spec.datasetRef,
    scorers: spec.scorerRefs,
    _class_name: 'Evaluation',
    _bases: ['Object', 'BaseModel'],
  };

  const newEvaluationResp = await client.objCreate({
    obj: {
      project_id: `${entity}/${project}`,
      // TODO: Sanitize name
      object_id: objectId,
      val: evaluationObjectVal,
      // builtin_object_class?: string;
    },
  });

  const digest = newEvaluationResp.digest;

  const evaluationRef = makeRefObject(
    entity,
    project,
    'object',
    objectId,
    digest,
    undefined
  );

  return evaluationRef;
};

export const runEvaluation = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  evaluationRef: string,
  modelRefs: string[]
): Promise<string[]> => {
  const res = await client.runEvaluation({
    project_id: `${entity}/${project}`,
    evaluation_ref: evaluationRef,
    model_refs: modelRefs,
  });
  return res.eval_call_ids;
};


export const getAllVersionsOfObject = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  objectId: string
): Promise<string[]> => {
  const res = await client.objsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      object_ids: [objectId],
    },
    sort_by: [{field: 'created_at', direction: 'desc'}],
    limit: 1000,
    metadata_only: true,
  });
  return res.objs.map(o => makeRefObject(entity, project, 'object', o.object_id, o.digest, undefined));
};