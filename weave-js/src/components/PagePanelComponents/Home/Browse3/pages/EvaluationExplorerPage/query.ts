import {
  isWeaveObjectRef,
  parseRefMaybe,
  parseWeaveRef,
} from '@wandb/weave/react';
import {makeRefObject} from '@wandb/weave/util/refs';

import {LlmStructuredCompletionModel} from '../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {createBuiltinObjectInstance} from '../wfReactInterface/objectClassQuery';
import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {sanitizeObjectId} from '../wfReactInterface/traceServerDirectClient';
import {convertTraceServerObjectVersionToSchema} from '../wfReactInterface/tsDataModelHooks';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {SimplifiedLLMAsAJudgeScorer} from './types';

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
  return res.objs.map(o =>
    makeRefObject(entity, project, 'object', o.object_id, o.digest, undefined)
  );
};

export const publishSimplifiedLLMAsAJudgeScorer = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  simplifiedScorer: SimplifiedLLMAsAJudgeScorer
) => {
  // Step 1: Create the inner model object
  const numberInstruction = 'a float between 0 and 1';
  const booleanInstruction = 'a boolean';
  const systemPrompt = `You are a judge of model performance. Repond in JSON with the following fields:
  * score: (${
    simplifiedScorer.scoreType === 'boolean'
      ? booleanInstruction
      : numberInstruction
  }) a 
  * reason: (string) a short explanation of the score
  `;
  const innerModelName = simplifiedScorer.name + ' model';
  const innerModelObjectId = sanitizeObjectId(innerModelName);
  const innerModelObjectVal: LlmStructuredCompletionModel = {
    default_params: {
      messages_template: [{role: 'system', content: systemPrompt}],
      response_format: 'json_object',
    },
    llm_model_id: simplifiedScorer.llmModelId,
    name: innerModelName,
  };

  const innerModelDigest = (
    await createBuiltinObjectInstance(client, 'LLMStructuredCompletionModel', {
      obj: {
        project_id: `${entity}/${project}`,
        object_id: innerModelObjectId,
        val: innerModelObjectVal,
      },
    })
  ).digest;

  const innerModelRef = makeRefObject(
    entity,
    project,
    'object',
    innerModelObjectId,
    innerModelDigest,
    undefined
  );

  // Step 2: Create the scorer object
  const scorerName = simplifiedScorer.name;
  const scorerObjectId = sanitizeObjectId(scorerName);
  const scorerObjectVal = {
    _type: 'LLMAsAJudgeScorer',
    _class_name: 'LLMAsAJudgeScorer',
    _bases: ['Scorer', 'Object', 'BaseModel'],
    name: scorerName,
    scoring_prompt: simplifiedScorer.prompt,
    model: innerModelRef,
  };
  const res = await client.objCreate({
    obj: {
      project_id: `${entity}/${project}`,
      object_id: scorerObjectId,
      val: scorerObjectVal,
    },
  });
  const digest = res.digest;
  const scorerRef = makeRefObject(
    entity,
    project,
    'object',
    scorerObjectId,
    digest,
    undefined
  );
  return scorerRef;
};

export const getSimplifiedLLMAsAJudgeScorer = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  scorerRef: string
): Promise<SimplifiedLLMAsAJudgeScorer | null> => {
  const scorer = await getObjByRef(client, scorerRef);
  if (!scorer) {
    return null;
  }
  const innerModelRef = scorer.val?.model;
  if (!innerModelRef) {
    return null;
  }
  const parsedInnerModelRef = parseRefMaybe(innerModelRef);
  if (!parsedInnerModelRef || !isWeaveObjectRef(parsedInnerModelRef)) {
    return null;
  }

  const innerModel = await getObjByRef(client, innerModelRef);
  if (!innerModel) {
    return null;
  }

  if (innerModel.val?.default_params?.response_format !== 'json_object') {
    return null;
  }

  if ((innerModel.val?.default_params?.messages_template ?? []).length !== 1) {
    return null;
  }

  const llmModelId = innerModel.val?.llm_model_id;
  let scoreTypeGuess: 'number' | 'boolean' | null = null;
  if (
    !innerModel.val.default_params.messages_template[0].content.includes('JSON')
  ) {
    return null;
  }
  if (
    innerModel.val.default_params.messages_template[0].content.includes(
      '(number)'
    )
  ) {
    scoreTypeGuess = 'number';
  } else if (
    innerModel.val.default_params.messages_template[0].content.includes(
      '(boolean)'
    )
  ) {
    scoreTypeGuess = 'boolean';
  } else {
    return null;
  }
  const prompt = scorer.val?.scoring_prompt;
  const name = scorer.val?.name ?? '';
  console.log({scorer, innerModel});
  return {
    name,
    scoreType: scoreTypeGuess,
    llmModelId: llmModelId ?? '',
    prompt: prompt ?? '',
  };
};
