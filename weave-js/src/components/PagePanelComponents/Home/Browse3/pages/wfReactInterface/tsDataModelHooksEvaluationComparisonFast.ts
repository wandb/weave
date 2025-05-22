import {PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {PaginationModel} from '../CompareEvaluationsPage/ecpTypes';
import {memoize} from './memoize';
import {TraceServerClient} from './traceServerClient';
import {TraceCallSchema} from './traceServerClientTypes';
import {projectIdFromParts} from './tsDataModelHooks';
import {calculatePredictAndScoreCallExampleDigest} from './tsDataModelHooksEvaluationComparisonUtilities';

// Original query function
const predictAndScoresCountQuery = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  evaluationCallId: string
): Promise<number> => {
  const projectId = projectIdFromParts({entity: entity, project: project});
  const evalTraceResProm = client.callsQueryStats({
    project_id: projectId,
    filter: {
      parent_ids: [evaluationCallId],
      op_names: [
        `weave:///${entity}/${project}/op/${PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC}:*`,
      ],
    },
  });
  const res = await evalTraceResProm;
  return res.count;
};

export const memoizedPredictAndScoresCountQuery = memoize(
  predictAndScoresCountQuery,
  (client, entity, project, evaluationCallId) =>
    JSON.stringify({entity, project, evaluationCallId}),
  100
);

// Original query function
const pagedPredictAndScoresQuery = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  evaluationCallId: string,
  paginationModel: PaginationModel
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
    limit: paginationModel.pageSize,
    offset: paginationModel.page * paginationModel.pageSize,
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
  (client, entity, project, evaluationCallId, paginationModel) =>
    JSON.stringify({entity, project, evaluationCallId, paginationModel}),
  100
);

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
      {
        pageSize: limit,
        page: offset,
      }
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
inform user that we always show the baseline metrics & results
test trials
test imperative
make all the links work (summary, predict, scoring, etc..)
  */
