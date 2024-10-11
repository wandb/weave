/**
 * This file implements a memoized version of getLeaderboardGroupableData for improved performance.
 */

import _ from 'lodash';

import {TraceServerClient} from '../../wfReactInterface/traceServerClient';
import {projectIdFromParts} from '../../wfReactInterface/tsDataModelHooks';
import {FilterAndGroupSpec} from '../types/leaderboardConfigType';
import {getLeaderboardGroupableData} from './leaderboardQuery';

export type VersionDetails = {digest: string; index: number};

const memoedGetLeaderboardGroupableData = _.memoize(
  async (
    client: TraceServerClient,
    entity: string,
    project: string,
    spec: FilterAndGroupSpec = {}
  ) => {
    return getLeaderboardGroupableData(client, entity, project, spec);
  },
  (client, entity, project, spec) => {
    // Create a cache key based on the function arguments
    return JSON.stringify({entity, project, spec});
  }
);

export const fetchEvaluationNames = async (
  client: TraceServerClient,
  entity: string,
  project: string
): Promise<string[]> => {
  return client
    .objsQuery({
      project_id: projectIdFromParts({entity, project}),
      filter: {
        base_object_classes: ['Evaluation'],
        is_op: false,
        latest_only: true,
      },
      metadata_only: true,
      sort_by: [{field: 'created_at', direction: 'desc'}],
    })
    .then(res => {
      return res.objs.map(obj => obj.object_id);
    });
};
export const fetchEvaluationVersionsForName = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  name: string
): Promise<VersionDetails[]> => {
  return client
    .objsQuery({
      project_id: projectIdFromParts({entity, project}),
      filter: {
        base_object_classes: ['Evaluation'],
        is_op: false,
        object_ids: [name],
      },
      metadata_only: true,
      sort_by: [{field: 'created_at', direction: 'desc'}],
    })
    .then(res => {
      return res.objs.map(obj => ({
        digest: obj.digest,
        index: obj.version_index,
      }));
    });
};
export const fetchDatasetNamesForSpec = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec
): Promise<string[]> => {
  // This is def a hacky/slow solution, just getting it working.
  const groupableData = await memoedGetLeaderboardGroupableData(
    client,
    entity,
    project,
    spec
  );
  return _.uniq(groupableData.map(g => g.row.datasetName));
};
export const fetchDatasetVersionsForSpecAndName = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec,
  name: string
): Promise<VersionDetails[]> => {
  const groupableData = await memoedGetLeaderboardGroupableData(
    client,
    entity,
    project,
    spec
  );

  return _.uniqBy(
    groupableData.map(g => ({digest: g.row.datasetVersion, index: -1})),
    o => `${o.digest}-${o.index}`
  );
};

export const fetchModelNamesForSpec = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec
): Promise<string[]> => {
  // This is def a hacky/slow solution, just getting it working.
  const groupableData = await memoedGetLeaderboardGroupableData(
    client,
    entity,
    project,
    spec
  );
  return _.uniq(groupableData.map(g => g.row.modelName));
};
export const fetchModelVersionsForSpecAndName = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec,
  name: string
): Promise<VersionDetails[]> => {
  // This is def a hacky/slow solution, just getting it working.
  const groupableData = await memoedGetLeaderboardGroupableData(
    client,
    entity,
    project,
    spec
  );
  return _.uniqBy(
    groupableData.map(g => ({digest: g.row.modelVersion, index: -1})),
    o => `${o.digest}-${o.index}`
  );
};
export const fetchScorerNamesForSpec = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec
): Promise<string[]> => {
  const groupableData = await memoedGetLeaderboardGroupableData(
    client,
    entity,
    project,
    spec
  );
  return _.uniq(groupableData.map(g => g.row.scorerName));
};
export const fetchScorerVersionsForSpecAndName = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec,
  name: string
): Promise<VersionDetails[]> => {
  const groupableData = await memoedGetLeaderboardGroupableData(
    client,
    entity,
    project,
    spec
  );
  return _.uniqBy(
    groupableData.map(g => ({digest: g.row.scorerVersion, index: -1})),
    o => `${o.digest}-${o.index}`
  );
};
export const fetchMetricPathsForSpec = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec
): Promise<string[]> => {
  const groupableData = await memoedGetLeaderboardGroupableData(
    client,
    entity,
    project,
    spec
  );
  return _.uniq(groupableData.map(g => g.row.metricPath));
};
