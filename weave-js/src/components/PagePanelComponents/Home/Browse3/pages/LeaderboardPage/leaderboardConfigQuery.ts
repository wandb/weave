import {useMemo} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {LeaderboardConfigType} from './LeaderboardConfigType';

export const useCurrentLeaderboardConfig = (): LeaderboardConfigType => {
  // TODO: Implement this
  console.log('Fetching current leaderboard config');
  return useMemo(() => {
    return {
      version: 1,
      config: {
        description: '',
        columns: [],
        models: [],
      },
    };
  }, []);
};
export const persistLeaderboardConfig = (config: LeaderboardConfigType) => {
  // TODO: Implement this
  console.log('Persisting leaderboard config:', config);
};

export const useDatasetNames = (entity: string, project: string): string[] => {
  const {useRootObjectVersions} = useWFHooks();
  const query = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Dataset'],
      latestOnly: true,
    },
    100,
    true
  );
  return useMemo(() => {
    return query.result?.map(obj => obj.objectId) ?? [];
  }, [query]);
};
export const useDatasetVersionsForDatasetName = (
  entity: string,
  project: string,
  datasetName: string
): Array<{version: string; versionIndex: number}> => {
  const {useRootObjectVersions} = useWFHooks();
  const query = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Dataset'],
      objectIds: [datasetName],
    },
    100,
    true
  );

  return useMemo(() => {
    return query.result?.map(obj => ({version: obj.versionHash, versionIndex: obj.versionIndex})) ?? [];
  }, [query]);
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
