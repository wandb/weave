import {isWeaveObjectRef, parseRefMaybe} from '@wandb/weave/react';
import _ from 'lodash';

import {flattenObjectPreservingWeaveTypes} from '../../../flattenObject';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../../../pages/common/heuristics';
import {TraceServerClient} from '../../../pages/wfReactInterface/traceServerClient';
import {TraceObjSchema} from '../../../pages/wfReactInterface/traceServerClientTypes';
import {
  convertISOToDate,
  projectIdFromParts,
} from '../../../pages/wfReactInterface/tsDataModelHooks';
import {
  objectVersionKeyToRefUri,
  opVersionKeyToRefUri,
} from '../../../pages/wfReactInterface/utilities';
import {
  ALL_VALUE,
  FilterAndGroupSpec,
  LeaderboardObjectVal,
} from '../types/leaderboardConfigType';

export type LeaderboardValueRecord = {
  datasetName: string;
  datasetVersion: string;
  metricType:
    | 'scorerMetric'
    | 'modelLatency'
    | 'evaluationDate'
    | 'evaluationTrials'
    | 'modelCost'
    | 'modelTokens'
    | 'modelErrors';
  scorerName: string; // modelMetrics repeat the type here
  scorerVersion: string; // modelMetrics repeat the type here
  metricPath: string; // modelMetrics repeat the type here
  metricValue: number | string | boolean | null | Date;
  modelName: string;
  modelVersion: string;
  modelType: 'object' | 'op';
  trials: number;
  createdAt: Date;
  sourceEvaluationCallId: string;
  sourceEvaluationObjectRef: string;
  // A bit hacky to denormalize `shouldMinimize` here, but it's convenient
  // for the caller and not externally visible
  shouldMinimize?: boolean;
};

type GroupableLeaderboardValueRecord = {
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

export type GroupedLeaderboardModelGroup<
  T extends any = LeaderboardValueRecord[]
> = {
  datasetGroups: {
    [datasetGroup: string]: {
      scorerGroups: {
        [scorerGroup: string]: {
          metricPathGroups: {
            [metricPathGroup: string]: T;
          };
        };
      };
    };
  };
};

const getEvaluationObjectsForSpec = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec
) => {
  const atLeastOneStarName = spec.sourceEvaluations?.some(
    sourceEvaluation => sourceEvaluation.name === ALL_VALUE
  );
  const sourceEvals = atLeastOneStarName ? [] : spec.sourceEvaluations ?? [];
  const evalNames = sourceEvals.map(sourceEvaluation => sourceEvaluation.name);
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
          (obj.digest === sourceEval.version ||
            sourceEval.version === ALL_VALUE)
        );
      });
    });
  }

  return allEvaluationObjectsRes;
};

const getLeaderboardGroupableData = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec = {}
): Promise<GroupableLeaderboardValueRecord[]> => {
  const allEvaluationObjectsRes = await getEvaluationObjectsForSpec(
    client,
    entity,
    project,
    spec
  );

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
          versionHash: ALL_VALUE,
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
        scorerName: 'Summary',
        scorerVersion: '',
        metricPath: 'Avg. Latency',
        metricValue: modelLatency,
      };
      data.push(modelLatencyRecord);
    }

    const evaluationDate = convertISOToDate(call.started_at);
    if (evaluationDate == null) {
      console.warn('Skipping model latency', call);
    } else {
      const evaluationDateRecord: LeaderboardValueRecord = {
        ...recordPartial,
        metricType: 'evaluationDate',
        scorerName: 'Summary',
        scorerVersion: '',
        metricPath: 'Run Date',
        metricValue: evaluationDate,
      };
      data.push(evaluationDateRecord);
    }

    if (trials == null) {
      console.warn('Skipping model latency', call);
    } else {
      const trialsRecord: LeaderboardValueRecord = {
        ...recordPartial,
        metricType: 'evaluationTrials',
        scorerName: 'Summary',
        scorerVersion: '',
        metricPath: 'Trials',
        metricValue: trials,
      };
      data.push(trialsRecord);
    }

    // TODO: add modelCost/tokens, modelErrors
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
            (model.version === ALL_VALUE || model.version === row.modelVersion)
        );
      modelSpec =
        modelSpec ||
        spec.models.find(
          model =>
            (model.name === ALL_VALUE || model.name === row.modelName) &&
            (model.version === ALL_VALUE || model.version === row.modelVersion)
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
          (dataset.version === ALL_VALUE ||
            dataset.version === row.datasetVersion)
      );
    datasetSpec =
      datasetSpec ||
      spec.datasets.find(
        dataset =>
          (dataset.name === ALL_VALUE || dataset.name === row.datasetName) &&
          (dataset.version === ALL_VALUE ||
            dataset.version === row.datasetVersion)
      );
    if (!datasetSpec) {
      return {include: false, groupableRow};
    }
    if (datasetSpec.groupAllVersions) {
      groupableRow.datasetGroup = `${row.datasetName}`;
    }
    if (datasetSpec.scorers && datasetSpec.scorers.length > 0) {
      let scorerSpec = datasetSpec.scorers.find(
        scorer =>
          scorer.name === row.scorerName && scorer.version === row.scorerVersion
      );
      scorerSpec =
        scorerSpec ||
        datasetSpec.scorers.find(
          scorer =>
            scorer.name === row.scorerName &&
            (scorer.version === ALL_VALUE ||
              scorer.version === row.scorerVersion)
        );
      scorerSpec =
        scorerSpec ||
        datasetSpec.scorers.find(
          scorer =>
            (scorer.name === ALL_VALUE || scorer.name === row.scorerName) &&
            (scorer.version === ALL_VALUE ||
              scorer.version === row.scorerVersion)
        );

      if (!scorerSpec) {
        return {include: false, groupableRow};
      }
      if (scorerSpec.groupAllVersions) {
        groupableRow.scorerGroup = `${row.scorerName}`;
      }
      if (scorerSpec.metrics && scorerSpec.metrics.length > 0) {
        const metricSpec = scorerSpec.metrics.find(
          metric => metric.path === ALL_VALUE || metric.path === row.metricPath
        );
        if (!metricSpec) {
          return {include: false, groupableRow};
        }
      }
    }

    return {include: true, groupableRow};
  });

  return filterableGroupableData
    .filter(entry => entry.include)
    .map(entry => entry.groupableRow);
};

export const getLeaderboardData = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  spec: FilterAndGroupSpec = {}
): Promise<GroupedLeaderboardData> => {
  const groupableData = await getLeaderboardGroupableData(
    client,
    entity,
    project,
    spec
  );
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

export const getPythonLeaderboardData = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  columns: LeaderboardObjectVal['columns']
): Promise<{
  finalData: GroupedLeaderboardData;
  evalData: LeaderboardObjectEvalData;
}> => {
  const {groupableData, evalData} = await getLeaderboardObjectGroupableData(
    client,
    entity,
    project,
    columns
  );

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

  return {finalData, evalData};
};

export type LeaderboardObjectEvalData = {
  [evalRefUri: string]: {
    datasetGroup: string;
    scorers: {
      [scorerName: string]: string;
    };
  };
};

const getLeaderboardObjectGroupableData = async (
  client: TraceServerClient,
  entity: string,
  project: string,
  columns: LeaderboardObjectVal['columns']
): Promise<{
  groupableData: GroupableLeaderboardValueRecord[];
  evalData: LeaderboardObjectEvalData;
}> => {
  const evalObjectRefs = _.uniq(
    columns.map(col => col.evaluation_object_ref)
  ).filter(ref => parseRefMaybe(ref)?.scheme === 'weave');

  if (evalObjectRefs.length === 0) {
    return {groupableData: [], evalData: {}};
  }

  const evalObjectRefsValsProm = client.readBatch({refs: evalObjectRefs});

  const allEvaluationCallsProm = client.callsStreamQuery({
    project_id: projectIdFromParts({entity, project}),
    sort_by: [{field: 'ended_at', direction: 'desc'}],
    filter: {
      op_names: [
        opVersionKeyToRefUri({
          entity,
          project,
          opId: EVALUATE_OP_NAME_POST_PYDANTIC,
          versionHash: ALL_VALUE,
        }),
      ],
      input_refs: evalObjectRefs,
    },
  });

  const evalObjectRefsVals = await evalObjectRefsValsProm;
  const evalMap = _.zipObject(evalObjectRefs, evalObjectRefsVals.vals);

  const allEvaluationCallsRes = await allEvaluationCallsProm;

  const data: GroupableLeaderboardValueRecord[] = [];
  const evalData: LeaderboardObjectEvalData = {};
  allEvaluationCallsRes.calls.forEach(call => {
    columns.forEach(col => {
      const evalObjRefUri = call.inputs.self;
      if (col.evaluation_object_ref === evalObjRefUri) {
        const evalVal = evalMap[evalObjRefUri];
        if (evalVal == null) {
          return;
        }
        const modelRefUri = call.inputs.model ?? '';
        const modelRef = parseRefMaybe(modelRefUri);
        const datasetRefUri = evalVal.dataset ?? '';
        const datasetRef = parseRefMaybe(datasetRefUri);
        if (modelRef?.scheme !== 'weave' || datasetRef?.scheme !== 'weave') {
          return;
        }
        const scorerRefUri = evalVal.scorers.find(
          (scorer: string) =>
            parseRefMaybe(scorer ?? '')?.artifactName === col.scorer_name
        );
        const scorerRef = parseRefMaybe(scorerRefUri ?? '');
        if (scorerRef?.scheme !== 'weave') {
          return;
        }
        let value = call.output;
        if (typeof value !== 'object' || value == null) {
          value = null;
        } else {
          value = (value as any)[col.scorer_name];
        }
        col.summary_metric_path.split('.').forEach(part => {
          if (value == null) {
            return;
          }
          if (_.isArray(value)) {
            try {
              const index = parseInt(part, 10);
              value = value[index];
            } catch (e) {
              console.warn('Skipping model latency', call, e);
              value = null;
            }
          } else {
            value = (value as any)[part];
          }
        });
        const modelGroup = `${modelRef.artifactName}:${modelRef.artifactVersion}`;
        const datasetGroup = `${datasetRef.artifactName}:${datasetRef.artifactVersion}`;
        const scorerGroup = `${scorerRef.artifactName}:${scorerRef.artifactVersion}`;
        const row: GroupableLeaderboardValueRecord = {
          modelGroup,
          datasetGroup,
          scorerGroup,
          metricPathGroup: col.summary_metric_path,
          sortKey: -convertISOToDate(call.started_at).getTime(),
          row: {
            datasetName: datasetRef.artifactName,
            datasetVersion: datasetRef.artifactVersion,
            metricType: 'scorerMetric',
            scorerName: scorerRef.artifactName,
            scorerVersion: scorerRef.artifactVersion,
            metricPath: col.summary_metric_path,
            metricValue: value as any,
            modelName: modelRef.artifactName,
            modelVersion: modelRef.artifactVersion,
            modelType: modelRef.weaveKind === 'op' ? 'op' : 'object',
            trials: evalVal.trials,
            createdAt: convertISOToDate(call.started_at),
            sourceEvaluationCallId: call.id,
            sourceEvaluationObjectRef: col.evaluation_object_ref,
            shouldMinimize: col.should_minimize ?? false,
          },
        };
        data.push(row);
        if (!(col.evaluation_object_ref in evalData)) {
          evalData[col.evaluation_object_ref] = {
            datasetGroup,
            scorers: {},
          };
        }
        evalData[col.evaluation_object_ref].scorers[scorerRef.artifactName] =
          scorerGroup;
      }
    });
  });

  return {groupableData: data, evalData};
};
