import {useMemo} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {LeaderboardConfigType, VersionSpec} from './LeaderboardConfigType';
import { parseRefMaybe } from '../../../Browse2/SmallRef';

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
  const evalQuery = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Evaluation'],
    },
    // This 100 is very limited
    100,
  );

  return useMemo(() => {
    const datasets = (evalQuery.result ?? []).map(e => parseRefMaybe(e.val.dataset)?.artifactName).filter(name => !!name).sort().filter((name, index, self) => self.indexOf(name) === index) as string[];
    return datasets;
  }, [evalQuery.result]);
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

  const allVersions = useMemo(() => {
    return (query.result ?? []).map(obj => ({version: obj.versionHash, versionIndex: obj.versionIndex})) ?? [];
  }, [query]);

  const evalQuery = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Evaluation'],
    },
    // This 100 is very limited
    100,
    false,
    {skip: allVersions.length === 0}
  );

  return useMemo(() => {
    
    const datasets = (evalQuery.result ?? []).map(e => {
      const ref = parseRefMaybe(e.val.dataset)
      if (!ref) {
        return null;
      }
      if (ref.artifactName !== datasetName) {
        return null;
      }
      const match = allVersions.find(v => v.version === ref.artifactVersion)
      return match
    }).filter(version => !!version)
    return datasets;
  }, [allVersions, datasetName, evalQuery.result]);
};
export const useScorerNamesForDataset = (
  entity: string,
  project: string,
  datasetName: string,
  datasetVersion: VersionSpec
): string[] => {
  // This one is a bit more involved:
  // 1. Lookup all the evaluations that contain this dataset
  // 2. Of each evaluation, get the scorer names

  const {useRootObjectVersions} = useWFHooks();
  const evalQuery = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Evaluation'],
    },
    // This 100 is very limited
    100,
  );

  return useMemo(() => {
    const eval_results = evalQuery.result?.filter(obj => {
      const ref = parseRefMaybe(obj.val.dataset ?? "")
      if (!ref) {
        return false;
      }
      if (ref.artifactName !== datasetName) {
        return false;
      }
      if (datasetVersion === "latest" || datasetVersion === "all") {
        return true;
      }
      return ref.artifactVersion === datasetVersion;
    }) ?? [];
    const res = eval_results.map(obj => obj.val.scorers ?? []).flat().map(scorer => parseRefMaybe(scorer)?.artifactName).filter(name => !!name).sort() // .filter((name, index, self) => self.indexOf(name) === index) as string[];

    return res;
  }, [datasetName, datasetVersion, evalQuery.result])
  


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
