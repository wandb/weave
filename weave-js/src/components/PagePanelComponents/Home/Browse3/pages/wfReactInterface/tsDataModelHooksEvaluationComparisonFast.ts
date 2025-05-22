import {PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {memoize} from './memoize';
import {TraceServerClient} from './traceServerClient';
import {TraceCallSchema} from './traceServerClientTypes';
import {projectIdFromParts} from './tsDataModelHooks';
import {
  generateStableDigest,
  maybeExtractDatasetRowRefDigest,
} from './tsDataModelHooksEvaluationComparisonUtilities';

// Original query function
const pagedPredictAndScoresQuery = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  evaluationCallId: string,
  limit: number,
  offset: number
): Promise<TraceCallSchema[]> => {
  const projectId = projectIdFromParts({entity: entity, project: project});
  const evalTraceResProm = client.callsStreamQuery({
    project_id: projectId,
    filter: {
      parent_ids: [evaluationCallId],
      op_names: [
        `weave:///${entity}/${project}/op/${PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC}:*`,
      ],
    },
    limit: limit,
    offset: offset,
    sort_by: [
      {
        field: 'started_at',
        direction: 'asc',
      },
    ],
  });
  const res = await evalTraceResProm;
  return res.calls;
};

// Create memoized version
export const memoizedPredictAndScoresQuery = memoize(
  pagedPredictAndScoresQuery,
  (client, entity, project, evaluationCallId, limit, offset) =>
    JSON.stringify({entity, project, evaluationCallId, limit, offset}),
  100
);

const calculatePredictAndScoreCallExampleDigest = (
  call: TraceCallSchema
): string => {
  const example = call.inputs.example;
  const maybeDigest = maybeExtractDatasetRowRefDigest(example);
  if (maybeDigest !== null) {
    return maybeDigest;
  }
  return generateStableDigest(example);
};

const lookupPredictAndScoreMatch = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  evaluationCallId: string,
  sourceCall: TraceCallSchema
): Promise<TraceCallSchema | null> => {
  let hasMoreRows = true;
  const sourceExampleDigest =
    calculatePredictAndScoreCallExampleDigest(sourceCall);

  const limit = 100;
  let offset = 0;

  while (hasMoreRows) {
    const calls = await memoizedPredictAndScoresQuery(
      client,
      entity,
      project,
      evaluationCallId,
      limit,
      offset
    );
    hasMoreRows = calls.length === limit;
    offset += calls.length;
    for (const call of calls) {
      const exampleDigest = calculatePredictAndScoreCallExampleDigest(call);
      if (exampleDigest === sourceExampleDigest) {
        return call;
      }
    }
  }

  return null;
};

const memoizedLookupPredictAndScoreMatch = memoize(
  lookupPredictAndScoreMatch,
  (client, entity, project, evaluationCallId, peerExampleDigest) =>
    JSON.stringify({entity, project, evaluationCallId, peerExampleDigest}),
  100
);

const lookupPredictAndScoreMatchMany = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  evaluationCallId: string,
  sourceCalls: TraceCallSchema[]
): Promise<
  {sourceCall: TraceCallSchema; matchedCall: TraceCallSchema | null}[]
> => {
  const proms = sourceCalls.map(async sourceCall => {
    const matchedCall = await memoizedLookupPredictAndScoreMatch(
      client,
      entity,
      project,
      evaluationCallId,
      sourceCall
    );
    return {
      sourceCall,
      matchedCall,
    };
  });
  const results = await Promise.all(proms);
  return results;
};

export const memoizedLookupPredictAndScoreMatchMany = memoize(
  lookupPredictAndScoreMatchMany,
  (client, entity, project, evaluationCallId, sourceCalls) =>
    JSON.stringify({entity, project, evaluationCallId, sourceCalls}),
  100
);

/*
  /// TODO:
  remove sorting of table

  */
