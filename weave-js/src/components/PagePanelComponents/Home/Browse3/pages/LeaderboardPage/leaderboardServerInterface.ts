
// type EvaluationMatrix = {
//     datasets: {
//         datasetName: string;
//         versions: {

import { isWeaveObjectRef } from "@wandb/weave/react";

import { flattenObjectPreservingWeaveTypes } from "../../../Browse2/browse2Util";
import { parseRefMaybe } from "../../../Browse2/SmallRef";
import { EVALUATE_OP_NAME_POST_PYDANTIC } from "../common/heuristics";
import { TraceServerClient } from "../wfReactInterface/traceServerClient";
import { TraceObjSchema } from "../wfReactInterface/traceServerClientTypes";
import { convertISOToDate, projectIdFromParts } from "../wfReactInterface/tsDataModelHooks";
import { opVersionKeyToRefUri } from "../wfReactInterface/utilities";
import _ from "lodash";

//         }

//     }
// };

// const getProjectEvaluationMatrix = () => { }


// type EvaluationResultRecord = {
//     datasetName: string;
//     datasetVersion: string;
//     scorerName: string;
//     scorerVersion: string;
//     metricPath: string;
//     metricValue: number | string | boolean | null;
//     modelName: string;
//     modelVersion: string;
//     modelType: 'object' | 'op';
//     trials: number;
//     sourceEvaluationCallId: string;
//     sourceEvaluationObjectRef: string;
// }

// type EvaluationDefinition = {
//     sourceEvaluationObjectRef: string;
//     datasetName: string;
//     datasetVersion: string;
//     scorers: Array<{
//         scorerName: string;
//         scorerVersion: string;
//     }>
// }

// type ScorerDefinition = {
//     scorerName: string;
//     scorerVersion: string;
//     type: 'object' | 'op'
//     sampleResult: { [key: string]: any }
// }

// // 

// type EvaluationObjectLeaderboardSpec = {
//     evaluationObjectVersionRefUri: string;
// }

// ----

type LeaderboardSpec = {
    columnGroups: LeaderboardDatasetColumnGroupSpec;
    modelSpec?: ExplicitModelSpec
}

type ExplicitModelSpec = {
    modelType: 'explicit';
    models: Array<{
        modelName: string;
        modelVersion?: string;
    }>
}


type LeaderboardDatasetColumnGroupSpec = {
    datasetName: string;
    datasetVersion?: string;
    metricSpecs: MetricSpec[];
    // TODO: min/max trials
}

type ScorerMetricSpec = {
    metricType: 'scorerMetric';
    scorerName: string;
    scorerVersion?: string;
    scorerType: 'object' | 'op';
    metrics: Array<{
        metricPath: string;
        shouldMinimize?: boolean;
    }>;
}

type ModelMetricSpec = {
    metricType: 'modelLatency' | 'modelCost' | 'modelTokens' | 'modelErrors';
}

type MetricSpec = ScorerMetricSpec | ModelMetricSpec;

type LeaderboardValueRecord = {
    datasetName: string;
    datasetVersion: string;
    metricType: 'scorerMetric' | 'modelLatency' | 'modelCost' | 'modelTokens' | 'modelErrors';
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
}

export type LeaderboardData2 = Array<LeaderboardValueRecord>;

export type FilterAndGroupSpec = {
    datasets?: Array<{
        name: string; // "*" means all
        version: string; // "*" means all
        splitByVersion?: boolean;
        scorers?: Array<{
            name: string; // "*" means all
            version: string; // "*" means all
            splitByVersion?: boolean;
            metrics?: Array<{
                path: string; // "*" means all
                shouldMinimize?: boolean;
            }>// null is all
        }>// null is all
    }> // null is all
    models?: Array<{
        name: string; // "*" means all
        version: string; // "*" means all
        splitByVersion?: boolean;
    }> // null is all
}

export const getLeaderboardData = async (client: TraceServerClient, entity: string, project: string, spec: FilterAndGroupSpec = {}): Promise<LeaderboardData2> => {
    // get all the evaluations
    const allEvaluationObjectsProm = client.objsQuery(
        {
            project_id: projectIdFromParts({ entity, project }),
            filter: {
                base_object_classes: ["Evaluation"],
                is_op: false,
            }
        }
    )
    const allEvaluationCallsProm = client.callsStreamQuery(
        {
            project_id: projectIdFromParts({ entity, project }),
            filter: {
                op_names: [opVersionKeyToRefUri({
                    entity,
                    project,
                    opId: EVALUATE_OP_NAME_POST_PYDANTIC,
                    versionHash: '*',
                }),]
            }
        }
    )

    const allEvaluationObjectsRes = await allEvaluationObjectsProm;
    const evaluationObjectDigestMap = new Map<string, { versions: Map<string, TraceObjSchema>, versionOrder: string[] }>();
    allEvaluationObjectsRes.objs.forEach(obj => {
        const outerKey = obj.object_id;
        const innerKey = obj.digest;
        if (!evaluationObjectDigestMap.has(outerKey)) {
            evaluationObjectDigestMap.set(outerKey, { versions: new Map(), versionOrder: [] });
        }
        evaluationObjectDigestMap.get(outerKey)!.versions.set(innerKey, obj);
    });
    evaluationObjectDigestMap.forEach((value, key) => {
        value.versionOrder = Array.from(value.versions.entries()).sort((a, b) => a[1].version_index - b[1].version_index).map(entry => entry[0]);
    });

    const allEvaluationCallsRes = await allEvaluationCallsProm;
    const data: LeaderboardData2 = [];
    allEvaluationCallsRes.calls.forEach(call => {
        const evalObjectRefUri = call.inputs.self;
        const evalObjectRef = parseRefMaybe(evalObjectRefUri ?? "");
        const modelObjectOrOpRef = parseRefMaybe(call.inputs.model ?? "");

        if (!evalObjectRef || !modelObjectOrOpRef) {
            console.warn("Skipping evaluation call with missing eval object ref", call);
            return;
        }

        const evalObjectName = evalObjectRef.artifactName
        const evalObjectVersion = evalObjectRef.artifactVersion
        const evalObject = evaluationObjectDigestMap.get(evalObjectName)?.versions.get(evalObjectVersion);
        if (!evalObject) {
            console.warn("Skipping evaluation call with missing eval object", call);
            return;
        }

        const datasetRef = parseRefMaybe(evalObject.val.dataset ?? "");
        if (!datasetRef) {
            console.warn("Skipping evaluation call with missing dataset ref", call);
            return;
        }
        const datasetName = datasetRef.artifactName;
        const datasetVersion = datasetRef.artifactVersion;

        const modelName = modelObjectOrOpRef.artifactName;
        const modelVersion = modelObjectOrOpRef.artifactVersion;
        if (!isWeaveObjectRef(modelObjectOrOpRef)) {
            console.warn("Skipping evaluation call with invalid model ref", call);
            return;
        }
        const modelType = modelObjectOrOpRef.weaveKind === 'op' ? 'op' : 'object';
        const trials = (evalObject.val.trials ?? call.inputs.trials) ?? 1;

        const recordPartial: Omit<LeaderboardValueRecord, 'metricType' | 'scorerName' | 'scorerVersion' | 'metricPath' | 'metricValue'> = {
            datasetName,
            datasetVersion,
            modelName,
            modelVersion,
            modelType,
            trials,
            createdAt: convertISOToDate(call.started_at),
            sourceEvaluationCallId: call.id,
            sourceEvaluationObjectRef: evalObjectRefUri
        }

        const modelLatency = (call.output as any)?.model_latency?.mean;
        if (modelLatency == null) {
            console.warn("Skipping model latency", call);
        } else {
            const modelLatencyRecord: LeaderboardValueRecord = {
                ...recordPartial,
                metricType: 'modelLatency',
                scorerName: 'modelLatency',
                scorerVersion: 'modelLatency',
                metricPath: 'model_latency.mean',
                metricValue: modelLatency,
            }
            data.push(modelLatencyRecord);
        }

        // TODO: add modelCost, modelTokens, modelErrors

        const scorerRefUris = (evalObject.val.scorers ?? []) as Array<string>
        scorerRefUris.forEach(scorerRefUri => {
            const scorerRef = parseRefMaybe(scorerRefUri);
            if (!scorerRef || !isWeaveObjectRef(scorerRef)) {
                console.warn("Skipping scorer ref", scorerRefUri);
                return;
            }
            const scorerName = scorerRef.artifactName;
            const scorerVersion = scorerRef.artifactVersion;
            // const scorerType = scorerRef.weaveKind === 'op' ? 'op' : 'object';
            const scorePayload = (call.output as any)?.[scorerName];
            if (typeof scorePayload !== 'object' || scorePayload == null) {
                console.warn("Skipping scorer call with invalid score payload", scorerName, scorerVersion, call);
                return;
            }
            const flatScorePayload = flattenObjectPreservingWeaveTypes(scorePayload);
            Object.entries(flatScorePayload).forEach(([metricPath, metricValue]) => {
                const scoreRecord: LeaderboardValueRecord = {
                    ...recordPartial,
                    metricType: 'scorerMetric',
                    scorerName,
                    scorerVersion,
                    metricPath: metricPath,
                    metricValue,
                }
                data.push(scoreRecord);
            })
        })
    });

    // console.table(data);


    // First, apply the filters. Filter can work by:
    // Datasets:
    //    Take All
    //       Option; should split by version
    //    Allow-list of Names
    //       Option (per name); should split by version
    //    Allow-list of Names + Versions
    // Scorers (specified per dataset spec)
    //    Take All
    //       Option; should split by version
    //    Allow-list of Names
    //       Option (per name); should split by version
    //    Allow-list of Names + Versions
    // Metrics (specified per scorer spec)
    //    Take All
    //    Allow-list of Metric Paths
    // Models
    //    Take All
    //       Option; should split by version
    //    Allow-list of Names
    //       Option (per name); should split by version
    //    Allow-list of Names + Versions

    const filterableGroupableData = data.map(row => {
        const groupableRow = {
            datasetGroup: row.datasetName,
            scorerGroup: row.scorerName,
            modelGroup: row.modelName,
            metricPathGroup: row.metricPath,
            sortKey: -row.createdAt.getTime(),
            row,
        }

        if (!spec.datasets) {
            return { include: true, groupableRow }
        }
        if (spec.datasets.length === 0) {
            return { include: true, groupableRow }
        }
        if (spec.datasets.some(dataset => dataset.name === '*')) {
            return { include: true, groupableRow }
        }

        let datasetSpec = spec.datasets.find(dataset => (dataset.name === row.datasetName) && (dataset.version === row.datasetVersion));
        datasetSpec = datasetSpec || spec.datasets.find(dataset => (dataset.name === row.datasetName) && (dataset.version === '*' || dataset.version === row.datasetVersion));
        datasetSpec = datasetSpec || spec.datasets.find(dataset => (dataset.name === '*' || dataset.name === row.datasetName) && (dataset.version === '*' || dataset.version === row.datasetVersion));
        if (!datasetSpec) {
            return { include: false, groupableRow };
        }
        if (datasetSpec.splitByVersion) {
            groupableRow.datasetGroup += `${row.datasetName}:${row.datasetVersion}`;
        }
        if (datasetSpec.scorers) {

            let scorerSpec = datasetSpec.scorers.find(scorer => (scorer.name === row.scorerName) && (scorer.version === row.scorerVersion));
            scorerSpec = scorerSpec || datasetSpec.scorers.find(scorer => (scorer.name === row.scorerName) && (scorer.version === '*' || scorer.version === row.scorerVersion));
            scorerSpec = scorerSpec || datasetSpec.scorers.find(scorer => (scorer.name === '*' || scorer.name === row.scorerName) && (scorer.version === '*' || scorer.version === row.scorerVersion));
            if (!scorerSpec) {
                return { include: false, groupableRow };
            }
            if (scorerSpec.splitByVersion) {
                groupableRow.scorerGroup += `${row.scorerName}:${row.scorerVersion}`;
            }
            if (scorerSpec.metrics) {
                const metricSpec = scorerSpec.metrics.find(metric => (metric.path === '*' || metric.path === row.metricPath));
                if (!metricSpec) {
                    return { include: false, groupableRow };
                }
            }
        }
        if (spec.models) {
            let modelSpec = spec.models.find(model => (model.name === row.modelName) && (model.version === row.modelVersion));
            modelSpec = modelSpec || spec.models.find(model => (model.name === row.modelName) && (model.version === '*' || model.version === row.modelVersion));
            modelSpec = modelSpec || spec.models.find(model => (model.name === '*' || model.name === row.modelName) && (model.version === '*' || model.version === row.modelVersion));
            if (!modelSpec) {
                return { include: false, groupableRow };
            }
            if (modelSpec.splitByVersion) {
                groupableRow.modelGroup += `${row.modelName}:${row.modelVersion}`;
            }
        }
        return { include: true, groupableRow };
    })

    const groupableData = filterableGroupableData.filter(entry => entry.include).map(entry => entry.groupableRow);

    const finalData = [];
    const groupData = (data: { [key: string]: any } & { sortKey: number }[], fields: string[]): any => {
        if (fields.length === 0) {
            // Sort by created at descending and return the most recent record
            // Would be better to use some form of latest.
            const res = data.sort((a, b) => a.sortKey - b.sortKey)[0];
            finalData.push(res);
            return res;
        }

        const [currentField, ...remainingFields] = fields;
        return _.mapValues(_.groupBy(data, currentField), (groupedData) =>
            groupData(groupedData, remainingFields)
        );
    };

    const groupedData = groupData(groupableData, ['datasetGroup', 'scorerGroup', 'metricPathGroup', 'modelGroup']);
    console.log(groupedData);
    console.table(finalData)

    return data;
}



// type LeaderboardSpec = {
//     columnGroups: LeaderboardDatasetColumnGroupSpec;
//     modelSpec?: ExplicitModelSpec
// }

// type ExplicitModelSpec = {
//     modelType: 'explicit';
//     models: Array<{
//         modelName: string;
//         modelVersion?: string;
//     }>
// }


// type LeaderboardDatasetColumnGroupSpec = {
//     datasetName: string;
//     datasetVersion?: string;
//     metricSpecs: MetricSpec[];
//     // TODO: min/max trials
// }

// type ScorerMetricSpec = {
//     metricType: 'scorerMetric';
//     scorerName: string;
//     scorerVersion?: string;
//     scorerType: 'object' | 'op';
//     metrics: Array<{
//         metricPath: string;
//         shouldMinimize?: boolean;
//     }>;
// }

// const groupedData = _.mapValues(_.groupBy(data, 'datasetName'), (data) => {
//     return _.mapValues(_.groupBy(data, 'datasetVersion'), (data) => {
//         return _.mapValues(_.groupBy(data, 'scorerName'), (data) => {
//             return _.mapValues(_.groupBy(data, 'scorerVersion'), (data) => {
//                 return _.mapValues(_.groupBy(data, 'metricPath'), (data) => {
//                     return _.mapValues(_.groupBy(data, 'modelName'), (data) => {
//                         return _.mapValues(_.groupBy(data, 'modelVersion'), (data) => {
//                             // sort by created at descending
//                             // Opportunity to aggregate based on the metricType (ex. avg)
//                             return data.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime())[0]
//                         });
//                     });
//                 });
//             });
//         });
//     });
// });