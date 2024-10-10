import {FilterAndGroupSpec} from '../types/leaderboardConfigType';

export const fetchEvaluationNames = async (): Promise<string[]> => {
  // TODO
  return Promise.resolve(['E1', 'E2', 'E3']);
};
export const fetchEvaluationVersionsForName = async (
  name: string
): Promise<string[]> => {
  // TODO
  return Promise.resolve(['EV1', 'EV2', 'EV3']);
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
