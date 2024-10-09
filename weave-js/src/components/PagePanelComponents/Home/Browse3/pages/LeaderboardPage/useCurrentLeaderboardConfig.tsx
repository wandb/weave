import {useMemo} from 'react';

import {LeaderboardConfigType} from './LeaderboardConfigType';

export const useCurrentLeaderboardConfig = (): LeaderboardConfigType => {
  // TODO: Implement this
  return useMemo(() => {
    return {
      version: 1,
      config: {
        columns: [],
        models: [],
      },
    };
  }, []);
};
export const useDatasetNames = (): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return [
      'leaderboard-test-dataset',
      'leaderboard-test-dataset-2',
      'leaderboard-test-dataset-3',
    ];
  }, []);
};
export const useDatasetVersionsForDatasetName = (
  datasetName: string
): Array<{version: string; versionIndex: number}> => {
  // TODO: Implement this
  return useMemo(() => {
    return [
      {version: 'dug657ioy8j1', versionIndex: 0},
      {version: 'dnkjubyhvasd', versionIndex: 1},
      {version: 'dadsgf3f451d', versionIndex: 2},
    ];
  }, []);
};
export const useScorerNamesForDataset = (
  datasetName: string,
  datasetVersion: string
): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return ['scorer-1', 'scorer-2', 'scorer-3'];
  }, []);
};
export const useScorerVersionsForDatasetAndScorer = (
  datasetName: string,
  datasetVersion: string,
  scorerName: string
): Array<{version: string; versionIndex: number}> => {
  // TODO: Implement this
  return useMemo(() => {
    return [
      {version: 'sug657ioy8j1', versionIndex: 0},
      {version: 'snkjubyhvasd', versionIndex: 1},
      {version: 'sadsgf3f451d', versionIndex: 2},
    ];
  }, []);
};
export const useMetricPathsForDatasetAndScorer = (
  datasetName: string,
  datasetVersion: string,
  scorerName: string,
  scorerVersion: string
): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return ['accuracy', 'f1.macro', 'precision.micro', 'recall.micro.data'];
  }, []);
};
export const useModelNames = (): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return ['model-1', 'model-2', 'model-3'];
  }, []);
};
export const useModelVersionsForModelName = (
  modelName: string
): Array<{version: string; versionIndex: number}> => {
  // TODO: Implement this
  return useMemo(() => {
    return [
      {version: 'mug657ioy8j1', versionIndex: 0},
      {version: 'mnkjubyhvasd', versionIndex: 1},
      {version: 'madsgf3f451d', versionIndex: 2},
    ];
  }, []);
};
