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
      leaf_object_classes: ['PlaygroundModel'],
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
