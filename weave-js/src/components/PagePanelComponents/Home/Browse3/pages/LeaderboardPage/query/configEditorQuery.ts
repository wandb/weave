/**
 * This file is not performant yet.
 */

import { TraceServerClient } from '../../wfReactInterface/traceServerClient';
import { projectIdFromParts } from '../../wfReactInterface/tsDataModelHooks';
import {FilterAndGroupSpec} from '../types/leaderboardConfigType';

export const fetchEvaluationNames = async (
  client: TraceServerClient,
  entity: string,
  project: string,
): Promise<string[]> => {
  return client.objsQuery({
    project_id: projectIdFromParts({entity, project}),
    filter: {
      base_object_classes: ['Evaluation'],
      is_op: false,
      latest_only: true
    },
    metadata_only: true,
    sort_by: [{field: 'created_at', direction: 'desc'}],
  }).then(res => {
    return res.objs.map(obj => obj.object_id);
  });
};
export const fetchEvaluationVersionsForName = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  name: string
): Promise<{digest: string, index: number}[]> => {
  return client.objsQuery({
    project_id: projectIdFromParts({entity, project}),
    filter: {
      base_object_classes: ['Evaluation'],
      is_op: false,
      object_ids: [name]
    },
    metadata_only: true,
    sort_by: [{field: 'created_at', direction: 'desc'}],
  }).then(res => {
    return res.objs.map(obj => ({digest: obj.digest, index: obj.version_index}));
  });
};
export const fetchDatasetNamesForSpec = async (
  spec: FilterAndGroupSpec
): Promise<string[]> => {
  // TODO
  return Promise.resolve(['D1', 'D2', 'D3']);
};
export const fetchDatasetVersionsForSpecAndName = async (
  spec: FilterAndGroupSpec,
  name: string
): Promise<string[]> => {
  // TODO
  return Promise.resolve(['DV1', 'DV2', 'DV3']);
};
export const fetchModelNamesForSpec = async (
  spec: FilterAndGroupSpec
): Promise<string[]> => {
  // TODO
  return Promise.resolve(['M1', 'M2', 'M3']);
};
export const fetchModelVersionsForSpecndName = async (
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
