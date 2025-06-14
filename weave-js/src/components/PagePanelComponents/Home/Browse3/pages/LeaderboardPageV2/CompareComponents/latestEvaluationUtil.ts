import {parseRefMaybe} from '../../../../../../../react';
import {EvaluationCall, EvaluationObj} from './ecpTypes';

/**
 * Groups evaluation calls by model and returns only the latest evaluation for each model.
 * This is used to ensure consistency across different views (LeaderboardGrid, ResultExplorer, etc.)
 *
 * @param evaluationCalls - Array of evaluation calls to filter
 * @param evaluationTraceData - Map of call ID to trace data containing timestamps
 * @param groupByModelVersion - If true, groups by model:version. If false, groups by model name only.
 * @returns Map of model group key to the latest evaluation call for that model
 */
export function getLatestEvaluationsPerModel(
  evaluationCalls: EvaluationCall[],
  evaluationTraceData: {[callId: string]: {started_at: string}} = {},
  groupByModelVersion: boolean = true
): Map<string, EvaluationCall> {
  const modelGroups = new Map<string, EvaluationCall[]>();

  // Group evaluations by model
  evaluationCalls.forEach(evalCall => {
    if (!evalCall.modelRef) return;

    // Parse the model ref to get name and version
    const parsed = parseRefMaybe(evalCall.modelRef);
    if (!parsed || parsed.scheme !== 'weave') return;

    const modelName = parsed.artifactName;
    const modelVersion = parsed.artifactVersion || 'latest';

    const modelKey = groupByModelVersion
      ? `${modelName}:${modelVersion}`
      : modelName;

    if (!modelGroups.has(modelKey)) {
      modelGroups.set(modelKey, []);
    }
    modelGroups.get(modelKey)!.push(evalCall);
  });

  // For each model group, select the latest evaluation
  const latestEvaluations = new Map<string, EvaluationCall>();
  modelGroups.forEach((evals, modelKey) => {
    // Sort by started_at timestamp descending and take the first (most recent)
    const latest = evals.sort((a, b) => {
      const aTrace = evaluationTraceData[a.callId];
      const bTrace = evaluationTraceData[b.callId];

      // If we have trace data with timestamps, use that
      if (aTrace?.started_at && bTrace?.started_at) {
        return (
          new Date(bTrace.started_at).getTime() -
          new Date(aTrace.started_at).getTime()
        );
      }

      // Fallback: if evaluation calls have startedAt property, use that
      if ((a as any).startedAt && (b as any).startedAt) {
        return (
          new Date((b as any).startedAt).getTime() -
          new Date((a as any).startedAt).getTime()
        );
      }

      // Final fallback: use call ID lexicographical order (newer IDs tend to be later)
      return b.callId.localeCompare(a.callId);
    })[0];
    latestEvaluations.set(modelKey, latest);
  });

  return latestEvaluations;
}

/**
 * Groups evaluation calls by model AND dataset, returning the latest evaluation for each model-dataset combination.
 * This allows showing multiple evaluations per model when they use different datasets.
 *
 * @param evaluationCalls - Array of evaluation calls to filter
 * @param evaluations - Map of evaluation refs to evaluation objects (needed to get dataset info)
 * @param evaluationTraceData - Map of call ID to trace data containing timestamps
 * @param groupByModelVersion - If true, groups by model:version. If false, groups by model name only.
 * @returns Map of model-dataset group key to the latest evaluation call for that combination
 */
export function getLatestEvaluationsPerModelDataset(
  evaluationCalls: EvaluationCall[],
  evaluations: {[evaluationRef: string]: EvaluationObj},
  evaluationTraceData: {[callId: string]: {started_at: string}} = {},
  groupByModelVersion: boolean = true
): Map<string, EvaluationCall> {
  const modelDatasetGroups = new Map<string, EvaluationCall[]>();

  // Group evaluations by model AND dataset
  evaluationCalls.forEach(evalCall => {
    if (!evalCall.modelRef) return;

    // Parse the model ref to get name and version
    const parsed = parseRefMaybe(evalCall.modelRef);
    if (!parsed || parsed.scheme !== 'weave') return;

    const modelName = parsed.artifactName;
    const modelVersion = parsed.artifactVersion || 'latest';

    const modelKey = groupByModelVersion
      ? `${modelName}:${modelVersion}`
      : modelName;

    // Get the dataset ref from the evaluation object
    const evaluation = evaluations[evalCall.evaluationRef];
    if (!evaluation || !evaluation.datasetRef) return;

    // Parse the dataset ref to get name
    const datasetParsed = parseRefMaybe(evaluation.datasetRef);
    if (!datasetParsed || datasetParsed.scheme !== 'weave') return;

    const datasetName = datasetParsed.artifactName;

    // Create a composite key that includes both model and dataset
    const modelDatasetKey = `${modelKey}__${datasetName}`;

    if (!modelDatasetGroups.has(modelDatasetKey)) {
      modelDatasetGroups.set(modelDatasetKey, []);
    }
    modelDatasetGroups.get(modelDatasetKey)!.push(evalCall);
  });

  // For each model-dataset group, select the latest evaluation
  const latestEvaluations = new Map<string, EvaluationCall>();
  modelDatasetGroups.forEach((evals, modelDatasetKey) => {
    // Sort by started_at timestamp descending and take the first (most recent)
    const latest = evals.sort((a, b) => {
      const aTrace = evaluationTraceData[a.callId];
      const bTrace = evaluationTraceData[b.callId];

      // If we have trace data with timestamps, use that
      if (aTrace?.started_at && bTrace?.started_at) {
        return (
          new Date(bTrace.started_at).getTime() -
          new Date(aTrace.started_at).getTime()
        );
      }

      // Fallback: if evaluation calls have startedAt property, use that
      if ((a as any).startedAt && (b as any).startedAt) {
        return (
          new Date((b as any).startedAt).getTime() -
          new Date((a as any).startedAt).getTime()
        );
      }

      // Final fallback: use call ID lexicographical order (newer IDs tend to be later)
      return b.callId.localeCompare(a.callId);
    })[0];
    latestEvaluations.set(modelDatasetKey, latest);
  });

  return latestEvaluations;
}

/**
 * Filters an array of evaluation calls to keep only the latest evaluation for each model.
 *
 * @param evaluationCalls - Array of evaluation calls to filter
 * @param evaluationTraceData - Map of call ID to trace data containing timestamps
 * @param groupByModelVersion - If true, groups by model:version. If false, groups by model name only.
 * @returns Array of evaluation calls with only the latest for each model
 */
export function filterLatestEvaluationsPerModel(
  evaluationCalls: EvaluationCall[],
  evaluationTraceData: {[callId: string]: {started_at: string}} = {},
  groupByModelVersion: boolean = true
): EvaluationCall[] {
  const latestEvaluations = getLatestEvaluationsPerModel(
    evaluationCalls,
    evaluationTraceData,
    groupByModelVersion
  );
  return Array.from(latestEvaluations.values());
}

/**
 * Given a list of call IDs and evaluation calls, returns only the call IDs
 * that represent the latest evaluation for each model.
 *
 * @param callIds - Array of call IDs to filter
 * @param evaluationCalls - Map of call ID to evaluation call
 * @param evaluationTraceData - Map of call ID to trace data containing timestamps
 * @param groupByModelVersion - If true, groups by model:version. If false, groups by model name only.
 * @returns Array of call IDs representing latest evaluations per model
 */
export function filterLatestCallIdsPerModel(
  callIds: string[],
  evaluationCalls: {[callId: string]: EvaluationCall},
  evaluationTraceData: {[callId: string]: {started_at: string}} = {},
  groupByModelVersion: boolean = true
): string[] {
  const evalCallsArray = callIds
    .map(id => evaluationCalls[id])
    .filter(evalCall => evalCall != null);

  const latestEvaluations = filterLatestEvaluationsPerModel(
    evalCallsArray,
    evaluationTraceData,
    groupByModelVersion
  );
  const latestCallIds = new Set(latestEvaluations.map(e => e.callId));

  return callIds.filter(id => latestCallIds.has(id));
}

/**
 * Filters an array of evaluation calls to keep only the latest evaluation for each model-dataset combination.
 *
 * @param evaluationCalls - Array of evaluation calls to filter
 * @param evaluations - Map of evaluation refs to evaluation objects
 * @param evaluationTraceData - Map of call ID to trace data containing timestamps
 * @param groupByModelVersion - If true, groups by model:version. If false, groups by model name only.
 * @returns Array of evaluation calls with only the latest for each model-dataset combination
 */
export function filterLatestEvaluationsPerModelDataset(
  evaluationCalls: EvaluationCall[],
  evaluations: {[evaluationRef: string]: EvaluationObj},
  evaluationTraceData: {[callId: string]: {started_at: string}} = {},
  groupByModelVersion: boolean = true
): EvaluationCall[] {
  const latestEvaluations = getLatestEvaluationsPerModelDataset(
    evaluationCalls,
    evaluations,
    evaluationTraceData,
    groupByModelVersion
  );
  return Array.from(latestEvaluations.values());
}

/**
 * Given a list of call IDs and evaluation calls, returns only the call IDs
 * that represent the latest evaluation for each model-dataset combination.
 *
 * @param callIds - Array of call IDs to filter
 * @param evaluationCalls - Map of call ID to evaluation call
 * @param evaluations - Map of evaluation refs to evaluation objects
 * @param evaluationTraceData - Map of call ID to trace data containing timestamps
 * @param groupByModelVersion - If true, groups by model:version. If false, groups by model name only.
 * @returns Array of call IDs representing latest evaluations per model-dataset combination
 */
export function filterLatestCallIdsPerModelDataset(
  callIds: string[],
  evaluationCalls: {[callId: string]: EvaluationCall},
  evaluations: {[evaluationRef: string]: EvaluationObj},
  evaluationTraceData: {[callId: string]: {started_at: string}} = {},
  groupByModelVersion: boolean = true
): string[] {
  const evalCallsArray = callIds
    .map(id => evaluationCalls[id])
    .filter(evalCall => evalCall != null);

  const latestEvaluations = filterLatestEvaluationsPerModelDataset(
    evalCallsArray,
    evaluations,
    evaluationTraceData,
    groupByModelVersion
  );
  const latestCallIds = new Set(latestEvaluations.map(e => e.callId));

  return callIds.filter(id => latestCallIds.has(id));
}
