import {isWeaveObjectRef} from '@wandb/weave/react';
import _ from 'lodash';

import {flattenObjectPreservingWeaveTypes} from '../../../../Browse2/browse2Util';
import {parseRefMaybe} from '../../../../Browse2/SmallRef';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../../common/heuristics';
import {TraceServerClient} from '../../wfReactInterface/traceServerClient';
import {TraceObjSchema} from '../../wfReactInterface/traceServerClientTypes';
import {
  convertISOToDate,
  projectIdFromParts,
} from '../../wfReactInterface/tsDataModelHooks';
import {
  objectVersionKeyToRefUri,
  opVersionKeyToRefUri,
} from '../../wfReactInterface/utilities';
import {FilterAndGroupSpec} from '../types/leaderboardConfigType';

export type LeaderboardValueRecord = {
  datasetName: string;
  datasetVersion: string;
  metricType:
    | 'scorerMetric'
    | 'modelLatency'
    | 'modelCost'
    | 'modelTokens'
    | 'modelErrors';
  scorerName: string; // modelMetrics repeat the type here
  scorerVersion: string; // modelMetrics repeat the type here
  metricPath: string; // modelMetrics repeat the type here
  metricValue: number | string | boolean | null;
  modelName: string;
  modelVersion: string;
  modelType: 'object' | 'op';
  trials: number;
  createdAt: Date;
  sourceEvaluationCallId: string;
  sourceEvaluationObjectRef: string;
};

export type GroupableLeaderboardValueRecord = {
  modelGroup: string;
  datasetGroup: string;
  scorerGroup: string;
  metricPathGroup: string;
  sortKey: number;
  row: LeaderboardValueRecord;
};

export type GroupedLeaderboardData = {
  modelGroups: {
    [modelGroup: string]: GroupedLeaderboardModelGroup;
  };
};

export type GroupedLeaderboardModelGroup = {
  datasetGroups: {
    [datasetGroup: string]: {
      scorerGroups: {
        [scorerGroup: string]: {
          metricPathGroups: {
            [metricPathGroup: string]: LeaderboardValueRecord[];
          };
        };
      };
    };
  };
};

export const getLeaderboardData = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec = {}
): Promise<GroupedLeaderboardData> => {
  const sourceEvals = spec.sourceEvaluations ?? [];
  const evalNames = sourceEvals.map(sourceEvaluation => sourceEvaluation.name);
  // const fullyQualifiedEvalRefs = sourceEvals.map(sourceEvaluation => {
  //   return objectVersionKeyToRefUri({
  //     scheme: 'weave',
  //     weaveKind: 'object',
  //     entity,
  //     project,
  //     objectId: sourceEvaluation.name,
  //     versionHash: sourceEvaluation.version,
  //     path: '',
  //   });
  // });
  // get all the evaluations
  const allEvaluationObjectsProm = client.objsQuery({
    project_id: projectIdFromParts({entity, project}),
    filter: {
      base_object_classes: ['Evaluation'],
      is_op: false,
      // Sad :( we can't actually filter by version here!
      object_ids: evalNames,
    },
    sort_by: [{field: 'created_at', direction: 'desc'}],
  });

  const allEvaluationObjectsRes = await allEvaluationObjectsProm;

  // This hack to get around the fact that we can't filter by version in the query
  if (sourceEvals.length > 0) {
    allEvaluationObjectsRes.objs = allEvaluationObjectsRes.objs.filter(obj => {
      return sourceEvals.some(sourceEval => {
        return (
          obj.object_id === sourceEval.name &&
          (obj.digest === sourceEval.version || sourceEval.version === '*')
        );
      });
    });
  }

  const evaluationObjectDigestMap = new Map<
    string,
    {versions: Map<string, TraceObjSchema>; versionOrder: string[]}
  >();
  allEvaluationObjectsRes.objs.forEach(obj => {
    const outerKey = obj.object_id;
    const innerKey = obj.digest;
    if (!evaluationObjectDigestMap.has(outerKey)) {
      evaluationObjectDigestMap.set(outerKey, {
        versions: new Map(),
        versionOrder: [],
      });
    }
    evaluationObjectDigestMap.get(outerKey)!.versions.set(innerKey, obj);
  });
  evaluationObjectDigestMap.forEach((value, key) => {
    value.versionOrder = Array.from(value.versions.entries())
      .sort((a, b) => a[1].version_index - b[1].version_index)
      .map(entry => entry[0]);
  });

  const fullyQualifiedEvalRefs = allEvaluationObjectsRes.objs.map(obj => {
    return objectVersionKeyToRefUri({
      scheme: 'weave',
      weaveKind: 'object',
      entity,
      project,
      objectId: obj.object_id,
      versionHash: obj.digest,
      path: '',
    });
  });

  // SAD: if `input_refs` supported `*` wildcard, then we could do the queries in parallel
  const allEvaluationCallsProm = client.callsStreamQuery({
    project_id: projectIdFromParts({entity, project}),
    sort_by: [{field: 'ended_at', direction: 'desc'}],
    filter: {
      op_names: [
        opVersionKeyToRefUri({
          entity,
          project,
          opId: EVALUATE_OP_NAME_POST_PYDANTIC,
          versionHash: '*',
        }),
      ],
      input_refs: fullyQualifiedEvalRefs,
    },
  });

  const allEvaluationCallsRes = await allEvaluationCallsProm;

  const data: LeaderboardValueRecord[] = [];
  allEvaluationCallsRes.calls.forEach(call => {
    const evalObjectRefUri = call.inputs.self;
    const evalObjectRef = parseRefMaybe(evalObjectRefUri ?? '');
    const modelObjectOrOpRef = parseRefMaybe(call.inputs.model ?? '');

    if (!evalObjectRef || !modelObjectOrOpRef) {
      console.warn(
        'Skipping evaluation call with missing eval object ref',
        call
      );
      return;
    }

    const evalObjectName = evalObjectRef.artifactName;
    const evalObjectVersion = evalObjectRef.artifactVersion;
    const evalObject = evaluationObjectDigestMap
      .get(evalObjectName)
      ?.versions.get(evalObjectVersion);
    if (!evalObject) {
      console.warn('Skipping evaluation call with missing eval object', call);
      return;
    }

    const datasetRef = parseRefMaybe(evalObject.val.dataset ?? '');
    if (!datasetRef) {
      console.warn('Skipping evaluation call with missing dataset ref', call);
      return;
    }
    const datasetName = datasetRef.artifactName;
    const datasetVersion = datasetRef.artifactVersion;

    const modelName = modelObjectOrOpRef.artifactName;
    const modelVersion = modelObjectOrOpRef.artifactVersion;
    if (!isWeaveObjectRef(modelObjectOrOpRef)) {
      console.warn('Skipping evaluation call with invalid model ref', call);
      return;
    }
    const modelType = modelObjectOrOpRef.weaveKind === 'op' ? 'op' : 'object';
    const trials = evalObject.val.trials ?? call.inputs.trials ?? 1;

    const recordPartial: Omit<
      LeaderboardValueRecord,
      | 'metricType'
      | 'scorerName'
      | 'scorerVersion'
      | 'metricPath'
      | 'metricValue'
    > = {
      datasetName,
      datasetVersion,
      modelName,
      modelVersion,
      modelType,
      trials,
      createdAt: convertISOToDate(call.started_at),
      sourceEvaluationCallId: call.id,
      sourceEvaluationObjectRef: evalObjectRefUri,
    };

    const scorerRefUris = (evalObject.val.scorers ?? []) as string[];
    scorerRefUris.forEach(scorerRefUri => {
      const scorerRef = parseRefMaybe(scorerRefUri);
      if (!scorerRef || !isWeaveObjectRef(scorerRef)) {
        console.warn('Skipping scorer ref', scorerRefUri);
        return;
      }
      const scorerName = scorerRef.artifactName;
      const scorerVersion = scorerRef.artifactVersion;
      // const scorerType = scorerRef.weaveKind === 'op' ? 'op' : 'object';
      const scorePayload = (call.output as any)?.[scorerName];
      if (typeof scorePayload !== 'object' || scorePayload == null) {
        console.warn(
          'Skipping scorer call with invalid score payload',
          scorerName,
          scorerVersion,
          call
        );
        return;
      }
      const flatScorePayload = flattenObjectPreservingWeaveTypes(scorePayload);
      Object.entries(flatScorePayload).forEach(([metricPath, metricValue]) => {
        const scoreRecord: LeaderboardValueRecord = {
          ...recordPartial,
          metricType: 'scorerMetric',
          scorerName,
          scorerVersion,
          metricPath,
          metricValue,
        };
        data.push(scoreRecord);
      });
    });

    const modelLatency = (call.output as any)?.model_latency?.mean;
    if (modelLatency == null) {
      console.warn('Skipping model latency', call);
    } else {
      const modelLatencyRecord: LeaderboardValueRecord = {
        ...recordPartial,
        metricType: 'modelLatency',
        scorerName: 'modelLatency',
        scorerVersion: 'modelLatency',
        metricPath: 'model_latency.mean',
        metricValue: modelLatency,
      };
      data.push(modelLatencyRecord);
    }

    // TODO: add modelCost, modelTokens, modelErrors
  });

  const filterableGroupableData = data.map(row => {
    const groupableRow: GroupableLeaderboardValueRecord = {
      datasetGroup: `${row.datasetName}:${row.datasetVersion}`,
      scorerGroup:
        row.metricType === 'scorerMetric'
          ? `${row.scorerName}:${row.scorerVersion}`
          : row.scorerName,
      modelGroup: `${row.modelName}:${row.modelVersion}`,
      metricPathGroup: row.metricPath,
      sortKey: -row.createdAt.getTime(),
      row,
    };

    if (spec.models) {
      let modelSpec = spec.models.find(
        model =>
          model.name === row.modelName && model.version === row.modelVersion
      );
      modelSpec =
        modelSpec ||
        spec.models.find(
          model =>
            model.name === row.modelName &&
            (model.version === '*' || model.version === row.modelVersion)
        );
      modelSpec =
        modelSpec ||
        spec.models.find(
          model =>
            (model.name === '*' || model.name === row.modelName) &&
            (model.version === '*' || model.version === row.modelVersion)
        );
      if (!modelSpec) {
        return {include: false, groupableRow};
      }
      if (modelSpec.groupAllVersions) {
        groupableRow.modelGroup = `${row.modelName}`;
      }
    }

    if (!spec.datasets) {
      return {include: true, groupableRow};
    }
    if (spec.datasets.length === 0) {
      return {include: true, groupableRow};
    }
    if (spec.datasets.some(dataset => dataset.name === '*')) {
      return {include: true, groupableRow};
    }

    let datasetSpec = spec.datasets.find(
      dataset =>
        dataset.name === row.datasetName &&
        dataset.version === row.datasetVersion
    );
    datasetSpec =
      datasetSpec ||
      spec.datasets.find(
        dataset =>
          dataset.name === row.datasetName &&
          (dataset.version === '*' || dataset.version === row.datasetVersion)
      );
    datasetSpec =
      datasetSpec ||
      spec.datasets.find(
        dataset =>
          (dataset.name === '*' || dataset.name === row.datasetName) &&
          (dataset.version === '*' || dataset.version === row.datasetVersion)
      );
    if (!datasetSpec) {
      return {include: false, groupableRow};
    }
    if (datasetSpec.groupAllVersions) {
      groupableRow.datasetGroup = `${row.datasetName}`;
    }
    if (datasetSpec.scorers) {
      let scorerSpec = datasetSpec.scorers.find(
        scorer =>
          scorer.name === row.scorerName && scorer.version === row.scorerVersion
      );
      scorerSpec =
        scorerSpec ||
        datasetSpec.scorers.find(
          scorer =>
            scorer.name === row.scorerName &&
            (scorer.version === '*' || scorer.version === row.scorerVersion)
        );
      scorerSpec =
        scorerSpec ||
        datasetSpec.scorers.find(
          scorer =>
            (scorer.name === '*' || scorer.name === row.scorerName) &&
            (scorer.version === '*' || scorer.version === row.scorerVersion)
        );
      if (!scorerSpec) {
        return {include: false, groupableRow};
      }
      if (scorerSpec.groupAllVersions) {
        groupableRow.scorerGroup = `${row.scorerName}`;
      }
      if (scorerSpec.metrics) {
        const metricSpec = scorerSpec.metrics.find(
          metric => metric.path === '*' || metric.path === row.metricPath
        );
        if (!metricSpec) {
          return {include: false, groupableRow};
        }
      }
    }

    return {include: true, groupableRow};
  });

  const groupableData = filterableGroupableData
    .filter(entry => entry.include)
    .map(entry => entry.groupableRow);

  const finalData: GroupedLeaderboardData = {
    modelGroups: _.mapValues(
      _.groupBy(groupableData, 'modelGroup'),
      modelGroup => {
        return {
          datasetGroups: _.mapValues(
            _.groupBy(modelGroup, 'datasetGroup'),
            datasetGroup => {
              return {
                scorerGroups: _.mapValues(
                  _.groupBy(datasetGroup, 'scorerGroup'),
                  scorerGroup => {
                    return {
                      metricPathGroups: _.mapValues(
                        _.groupBy(scorerGroup, 'metricPathGroup'),
                        metricPathGroup => {
                          return metricPathGroup.map(row => row.row);
                          //   .sort(
                          //     (a, b) => a.sortKey - b.sortKey
                          //   )[0].row;
                        }
                      ),
                    };
                  }
                ),
              };
            }
          ),
        };
      }
    ),
  };

  return finalData;
};
