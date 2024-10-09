import {useMemo} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../../Browse2/browse2Util';
import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {useWFHooks} from '../wfReactInterface/context';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {LeaderboardConfigType, VersionSpec} from './LeaderboardConfigType';

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
    100
  );

  return useMemo(() => {
    const datasets = (evalQuery.result ?? [])
      .map(e => parseRefMaybe(e.val.dataset)?.artifactName)
      .filter(name => !!name)
      .sort()
      .filter((name, index, self) => self.indexOf(name) === index) as string[];
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
    return (
      (query.result ?? []).map(obj => ({
        version: obj.versionHash,
        versionIndex: obj.versionIndex,
      })) ?? []
    );
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
    const datasets = (evalQuery.result ?? [])
      .map(e => {
        const ref = parseRefMaybe(e.val.dataset);
        if (!ref) {
          return null;
        }
        if (ref.artifactName !== datasetName) {
          return null;
        }
        const match = allVersions.find(v => v.version === ref.artifactVersion);
        return match;
      })
      .filter(version => !!version) as Array<{
      version: string;
      versionIndex: number;
    }>;
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
    100
  );

  return useMemo(() => {
    const evalResults =
      evalQuery.result?.filter(obj => {
        const ref = parseRefMaybe(obj.val.dataset ?? '');
        if (!ref) {
          return false;
        }
        if (ref.artifactName !== datasetName) {
          return false;
        }
        if (datasetVersion === 'latest' || datasetVersion === 'all') {
          return true;
        }
        return ref.artifactVersion === datasetVersion;
      }) ?? [];
    const res = evalResults
      .map(obj => obj.val.scorers ?? [])
      .flat()
      .map(scorer => parseRefMaybe(scorer)?.artifactName)
      .filter(name => !!name)
      .sort() as string[]; // .filter((name, index, self) => self.indexOf(name) === index) as string[];

    return res;
  }, [datasetName, datasetVersion, evalQuery.result]);
};
export const useScorerVersionsForDatasetAndScorer = (
  entity: string,
  project: string,
  datasetName: string,
  datasetVersion: string,
  scorerName: string
): Array<{version: string; versionIndex: number}> => {
  const {useRootObjectVersions, useOpVersions} = useWFHooks();
  const query1 = useRootObjectVersions(
    entity,
    project,
    {
      objectIds: [scorerName],
    },
    100,
    true
  );

  const query2 = useOpVersions(
    entity,
    project,
    {
      opIds: [scorerName],
    },
    100,
    true
  );

  const allVersions = useMemo(() => {
    const versions1 =
      (query1.result ?? []).map(obj => ({
        version: obj.versionHash,
        versionIndex: obj.versionIndex,
      })) ?? [];
    const versions2 =
      (query2.result ?? []).map(obj => ({
        version: obj.versionHash,
        versionIndex: obj.versionIndex,
      })) ?? [];
    return versions1.concat(versions2);
  }, [query1, query2]);

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

  console.log(allVersions);

  return useMemo(() => {
    const scorers = (evalQuery.result ?? [])
      .map(e => {
        const ref = parseRefMaybe(e.val.dataset);
        if (!ref) {
          return [];
        }
        if (
          ref.artifactName !== datasetName ||
          ref.artifactVersion !== datasetVersion
        ) {
          return [];
        }
        return (e.val.scorers ?? []).map((scorer: string) => {
          const sRef = parseRefMaybe(scorer);
          if (!sRef) {
            return null;
          }
          const match = allVersions.find(
            v => v.version === sRef.artifactVersion
          );
          return match;
        });
      })
      .flat()
      .filter(version => !!version);
    return scorers;
  }, [allVersions, datasetName, datasetVersion, evalQuery.result]);
};

export const useMetricPathsForDatasetAndScorer = (
  entity: string,
  project: string,
  datasetName: string,
  datasetVersion: string,
  scorerName: string,
  scorerVersion: string
): string[] => {
  const {useRootObjectVersions, useCalls} = useWFHooks();
  const evalQuery = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Evaluation'],
    },
    // This 100 is very limited
    100
  );

  const evals = useMemo(() => {
    // Find the matching evals:
    console.log(evalQuery.result, scorerName, scorerVersion);
    return (evalQuery.result ?? []).filter(e => {
      const match = (e.val.scorers ?? []).find((s: string) => {
        const sRef = parseRefMaybe(s);
        if (!sRef) {
          return false;
        }
        console.log(sRef);
        return (
          sRef.artifactName === scorerName &&
          sRef.artifactVersion === scorerVersion
        );
      });
      return !!match;
    });
  }, [evalQuery.result, scorerName, scorerVersion]);

  const evalCalls = useCalls(
    entity,
    project,
    {
      inputObjectVersionRefs: evals.map(objectVersionKeyToRefUri),
    },
    10,
    undefined,
    undefined,
    undefined,
    undefined,
    undefined,
    {
      skip: evals.length === 0,
    }
  );

  return useMemo(() => {
    const foundCall = (evalCalls.result ?? []).find(
      (call: CallSchema) =>
        call.traceCall?.exception == null && call.traceCall?.ended_at != null
    );
    console.log(foundCall, evalCalls);
    const output = foundCall?.traceCall?.output;
    if (!output) {
      return [];
    }
    if (typeof output !== 'object') {
      return [];
    }
    return Object.keys(
      flattenObjectPreservingWeaveTypes(
        (output as {[key: string]: any})[scorerName] ?? {}
      )
    );
  }, [evalCalls, scorerName]);
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
