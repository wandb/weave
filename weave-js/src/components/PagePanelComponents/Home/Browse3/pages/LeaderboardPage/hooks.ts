import {ObjectRef} from '@wandb/weave/react';
import {useEffect, useMemo, useState} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../../Browse2/browse2Util';
import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {useEvalCallsForConfig} from './leaderboardConfigQuery';
import {LeaderboardConfigType} from './LeaderboardConfigType';
import {
  getLeaderboardData,
  GroupedLeaderboardData2,
} from './leaderboardServerInterface';

export type LeaderboardData = {
  metrics: {
    [metricId: string]: {
      // evaluationName: string;
      datasetName: string;
      datasetVersion: string;
      scorerName: string;
      scorerVersion: string;
      metricPath: string;
    };
  };
  models: string[];
  scores: {
    [modelId: string]: {
      [metricId: string]: {value: number; sourceEvalCallId: string};
    };
  };
};

export const useLeaderboardData = (
  entity: string,
  project: string,
  config: LeaderboardConfigType
): {loading: boolean; data: LeaderboardData} => {
  // console.log('Fetching leaderboard data', config);
  // const {useRootObjectVersions, useCalls} = useWFHooks();

  // // Get the last 100 (latest) evaluation versions
  // const evaluationVersions = useRootObjectVersions(
  //   entity,
  //   project,
  //   {
  //     baseObjectClasses: ['Evaluation'],
  //     // latestOnly: true,
  //   },
  //   100,
  //   true
  // );

  // // Unfortunately, the eval framework does not build models automatically!!
  // // const modelVersions = useRootObjectVersions(entity, project, {
  // //     baseObjectClasses: ['Model'],
  // //     latestOnly: true,
  // // }, 100, true)

  // // Get the runs for these evaluation versions.
  // const evaluationVersionsResult = evaluationVersions?.result;
  // const evaluationRuns = useCalls(
  //   entity,
  //   project,
  //   {
  //     opVersionRefs: [
  //       opVersionKeyToRefUri({
  //         entity,
  //         project,
  //         opId: EVALUATE_OP_NAME_POST_PYDANTIC,
  //         versionHash: '*',
  //       }),
  //     ],
  //     traceRootsOnly: true,
  //     inputObjectVersionRefs: (evaluationVersionsResult ?? []).map(version =>
  //       objectVersionKeyToRefUri(version)
  //     ),
  //   },
  //   100,
  //   undefined,
  //   undefined,
  //   undefined,
  //   undefined,
  //   undefined,
  //   {skip: !evaluationVersionsResult}
  // );
  const {calls: evaluationRuns, evals: evaluationVersions} =
    useEvalCallsForConfig(entity, project, config);

  // Build the dataset

  const results: {loading: boolean; data: LeaderboardData} = useMemo(() => {
    const finalData: LeaderboardData = {
      metrics: {},
      models: [],
      scores: {},
    };
    if (evaluationRuns.loading) {
      return {
        loading: true,
        data: finalData,
      };
    } else if (!evaluationRuns.result) {
      // || !evaluationVersionsResult) {
      return {
        loading: false,
        data: finalData,
      };
    }

    const runs = evaluationRuns.result;
    // const versions = evaluationVersionsResult
    runs.forEach(r => {
      const modelName = r.traceCall?.inputs.model;
      if (!modelName) {
        return;
      }
      const evaluationVersion = r.traceCall?.inputs.self;
      if (!evaluationVersion) {
        return;
      }
      const evalVersion = parseRefMaybe(evaluationVersion)?.artifactVersion;
      if (!evalVersion) {
        return;
      }
      const evalObject = evaluationVersions.find(
        e => e.versionHash === evalVersion
      );
      if (!evalObject) {
        return;
      }
      const outputSummary = r.traceCall?.output;
      if (!outputSummary) {
        return;
      }

      const datasetRef = parseRefMaybe(evalObject.val.dataset);
      if (!datasetRef) {
        return;
      }

      const datasetName = datasetRef.artifactName;
      const datasetVersion = datasetRef.artifactVersion;
      const scorerNameMap = Object.fromEntries(
        (evalObject.val.scorers ?? [])
          .map(parseRefMaybe)
          .filter(Boolean)
          .map((s: ObjectRef) => [s.artifactName, s.artifactVersion])
          .filter(([name, version]: [string, string]) => {
            return (
              config.config.datasets.length === 0 ||
              config.config.datasets.some(dc => {
                return (
                  (dc.dataset.name === '' || dc.dataset.name === datasetName) &&
                  (dc.dataset.version === 'all' ||
                    dc.dataset.version === 'latest' ||
                    dc.dataset.version === datasetVersion) &&
                  (dc.scores.length === 0 ||
                    dc.scores.some(s => {
                      return (
                        (s.scorer.name === '' || s.scorer.name === name) &&
                        (s.scorer.version === 'all' ||
                          s.scorer.version === 'latest' ||
                          s.scorer.version === version)
                      );
                    }))
                );
              })
            );
          })
      );

      if (!finalData.models.includes(modelName)) {
        finalData.models.push(modelName);
        if (!finalData.scores[modelName]) {
          finalData.scores[modelName] = {};
        }
      }

      Object.entries(outputSummary ?? {}).forEach(
        ([scorerName, scorerMetricsVal]) => {
          const scorerVersion = scorerNameMap[scorerName];
          if (!scorerVersion) {
            return;
          }
          if (
            scorerMetricsVal == null ||
            typeof scorerMetricsVal !== 'object'
          ) {
            return;
          }
          const flattened = flattenObjectPreservingWeaveTypes(scorerMetricsVal);
          Object.entries(flattened).forEach(([metricPath, metricValue]) => {
            const metricId = `${datasetName}:${datasetVersion}.${scorerName}:${scorerVersion}.${metricPath}`;
            if (!finalData.metrics[metricId]) {
              finalData.metrics[metricId] = {
                datasetName,
                datasetVersion,
                scorerName,
                scorerVersion,
                metricPath,
              };
            }
            finalData.scores[modelName][metricId] = {
              value: metricValue,
              sourceEvalCallId: r.callId,
            };
          });
        }
      );
    });

    return {
      loading: false,
      data: finalData,
    };
  }, [
    config.config.datasets,
    evaluationRuns.loading,
    evaluationRuns.result,
    evaluationVersions,
  ]);

  return results;
};

export const useLeaderboardData2 = (entity: string, project: string) => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [state, setState] = useState<{
    loading: boolean;
    data: GroupedLeaderboardData2;
  }>({loading: true, data: []});
  useEffect(() => {
    let mounted = true;
    getLeaderboardData(getTraceServerClient(), entity, project, {
      datasets: [
        {
          name: 'SWEBenchVerified-shuffle808-50',
          version: '*',
        },
      ],
      models: [
        {
          name: '*',
          version: '*',
          splitByVersion: false,
        },
        {
          name: 'reproProblem',
          version: '*',
          splitByVersion: true,
        },
      ],
    }).then(data => {
      if (mounted) {
        setState({loading: false, data});
      }
    });
    return () => {
      mounted = false;
    };
  }, [entity, project, getTraceServerClient]);
  return state;
};
