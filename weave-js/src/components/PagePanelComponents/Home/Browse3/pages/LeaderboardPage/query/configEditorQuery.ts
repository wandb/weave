/**
 * This file is not performant yet.
 */

import {ObjectRef} from '@wandb/weave/react';
import _ from 'lodash';

import {parseRefMaybe} from '../../../../Browse2/SmallRef';
import {TraceServerClient} from '../../wfReactInterface/traceServerClient';
import {projectIdFromParts} from '../../wfReactInterface/tsDataModelHooks';
import {FilterAndGroupSpec} from '../types/leaderboardConfigType';
import {
  getEvaluationObjectsForSpec,
  getLeaderboardData,
  getLeaderboardGroupableData,
} from './leaderboardQuery';

export type VersionDetails = {digest: string; index: number};

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
  const groupableData = await getLeaderboardGroupableData(
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
  const groupableData = await getLeaderboardGroupableData(
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
  spec: FilterAndGroupSpec
): Promise<string[]> => {
  // TODO
  return Promise.resolve(['M1', 'M2', 'M3']);
};
export const fetchModelVersionsForSpecAndName = async (
  spec: FilterAndGroupSpec,
  name: string
): Promise<string[]> => {
  // TODO
  return Promise.resolve(['MV1', 'MV2', 'MV3']);
};
export const fetchScorerNamesForSpec = async (
  spec: FilterAndGroupSpec
): Promise<string[]> => {
  // TODO
  return Promise.resolve(['S1', 'S2', 'S3']);
};
export const fetchScorerVersionsForSpecAndName = async (
  spec: FilterAndGroupSpec,
  name: string
): Promise<string[]> => {
  // TODO
  return Promise.resolve(['SV1', 'SV2', 'SV3']);
};
export const fetchMetricPathsForSpec = async (
  spec: FilterAndGroupSpec
): Promise<string[]> => {
  // TODO
  return Promise.resolve(['MP1', 'MP2', 'MP3']);
};
