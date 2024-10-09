import {useMemo} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../../Browse2/browse2Util';
import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {useWFHooks} from '../wfReactInterface/context';
import {
  objectVersionKeyToRefUri,
  opVersionKeyToRefUri,
} from '../wfReactInterface/utilities';
import {useEvalCallsForConfig} from './leaderboardConfigQuery';
import {LeaderboardConfigType} from './LeaderboardConfigType';
import { ObjectRef } from '@wandb/weave/react';

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
      if (!finalData.models.includes(modelName)) {
        finalData.models.push(modelName);
        if (!finalData.scores[modelName]) {
          finalData.scores[modelName] = {};
        }
      }

      const datasetName = datasetRef.artifactName;
      const datasetVersion = datasetRef.artifactVersion;
      const scorerNameMap = Object.fromEntries(
        (evalObject.val.scorers ?? [])
          .map(parseRefMaybe)
          .filter(Boolean)
          .map((s: ObjectRef) => [s.artifactName, s.artifactVersion])
      );

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
  }, [evaluationRuns.loading, evaluationRuns.result, evaluationVersions]);

  return results;
};
