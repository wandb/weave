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

  const pageSize = 100;
  let page = 0;

  while (hasMoreRows) {
    const calls = await memoizedPredictAndScoresQuery(
      client,
      entity,
      project,
      evaluationCallId,
      {
        pageSize: pageSize,
        page: page,
      }
    );
    hasMoreRows = calls.length === pageSize;
    page += 1;
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

const findPredictAndScoreChildrenCalls = async (
  client: TraceServerClient,
  predictAndScoreCall: TraceCallSchema
): Promise<TraceCallSchema[]> => {
  const calls = await client.callsQuery({
    project_id: predictAndScoreCall.project_id,
    filter: {parent_ids: [predictAndScoreCall.id]},
    columns: ['id', 'op_name'],
    sort_by: [{field: 'started_at', direction: 'asc'}],
  });
  return calls.calls;
};

export const memoizedFindPredictAndScoreChildrenCalls = memoize(
  findPredictAndScoreChildrenCalls,
  (client, predictAndScoreCall) =>
    JSON.stringify({client, predictAndScoreCall}),
  100
);

/*
Further improvements:
    * No need to load all the comparison data first - can lazily load that when needed on screen!
    * Probably should just revise the table to be based on the baseline data
    * Should probably pre-fetch a few pages (requires more revisions)

Changes:
    (temp) Removed sorting / filtering of the table
    Show the scores and rows from baseline - instead of union

Known Bugs:
    * (existing) Single trial does not expand (and therefore no link to pas)

Hacks:
    * Tokens and Latency are calculated from the predict and score, not the predict call!
    * Clicking "previous" when already at the top and paged will go back by X results, not 1

Variations to test:
    Num Evals (1, 2, Many)
    Pivot Dimensions
    Logger vs Framework
    Trials
  */
