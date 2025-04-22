/**
 * This file exports `useEvaluationComparisonData` which is used to fetch
 * evaluation comparison data. It is exclusively used by the
 * `CompareEvaluationsPage` component, and in particular,
 * `CompareEvaluationsPage/ecpState.ts:useEvaluationComparisonState`.
 * However, since we rely on the lower level `TraceServerClient` to directly
 * fetch the data, we are putting it with the other `tsDataModelHooks*` files.
 * In the future, this could be moved lower into the server itself. Furthermore,
 * we are bypassing the normal caching layer used by the other hooks. By
 * decoupling this part of the code, we can more pointedly improve performance
 * without changing the component interfaces.
 *
 *
 * Notes on the shape of Evaluation Data:
 * * Scorers here are not as well defined as they should be. Let's get a better
 *   understanding:
 * 1. Scorers can come in 2 flavors: Ops or Object Classes. Ops are pure
 *    functions whereas Object Classes have a `score` method and optionally a
 *    `summarize` method. If not provided, the summarization will recursively
 *    `auto_summarize` the outputs of the `score` method. Therefore we have the
 *    following scorer types:
 *    - Ops
 *    - Object Classes (auto_summarize)
 *    - Object Classes (summarize)
 * 2. The output of a scorer can be a boolean or a number (or a possibly-nested
 *    dictionary of such values)
 *    - For sake of processing, we call each leaf path of the `score` or
 *      `summarize` output a "metric"
 *            - Leaf paths of `score` method are: `ScoreMetric`
 *            - Leaf path of `summarize` method are: `SummaryMetric`
 * 3. Autosummarization works by operating on the leaf nodes of the output
 *    dictionary and applying a summarization function:
 *    - For binary values: {"true_count": X, "true_fraction": Y}
 *       - Note: we typically ignore "true_count" and only use "true_fraction"
 *         for binary values
 *    - For continuous values: {'mean': X}
 * 4. Custom summarization has no rules - it is yet again a primitive or
 *    possibly-nested dictionary of primitives.
 * 5. An evaluation can have any number of scorers.
 * 6. Scorers are versioned - meaning Scorers of the same name should be
 *    conceptually comparable, but might vary in implementation.
 *
 * Now, how do we walk through the data?
 * * EvaluationObj -> DatasetObjRef (via inputs.dataset)
 * * EvaluationObj -> ScoreOpRef[]  (via inputs.scorers)
 * * EvaluateCall -> ModelObjRef (via inputs.model)
 * * EvaluateCall -> EvaluationObjRef (via op_name)
 * * EvaluateCall -> {[scoreName: string]: SummaryMetric} (via output)
 * * EvaluateCall -> (derived metric special case) Model Latency (via output.model_latency)
 * * EvaluateCall -> (derived metric special case) Token Usage (via summary.usage) - flawed as it includes non-model tokens
 * * PredictAndScoreCall -> EvaluateCall (via parent_id callId)
 * * ModelPredictCall -> ModelRef (via inputs.self)
 * * ModelPredictCall -> DatasetRowRef (via inputs.example).
 * * DatasetRowRef -> DatasetObjRef (via string parsing) - fragile due to ref structure
 * * DatasetRowRef -> Digest (via string parsing) - fragile and happens to be the last part of the ref
 * * ModelPredictCall -> PredictAndScoreCall (via parent_id callId)
 * * ModelPredictCall -> Output (via output)
 * * ModelPredictCall -> (derived metric special case) Model Latency (via end_time - start_time)
 * * ModelPredictCall -> (derived metric special case) Token Usage (via summary.usage)
 * * ScoreCall -> PredictAndScoreCall (via parent_id callId)
 * * ScoreCall -> ScoreOpRef (via inputs.self)
 * * ScoreCall -> ScoreMetric (via output)
 * * ScoreOp (optional) -> ScorerObjRef (via inputs.self)
 * * DatasetObj -> DatasetRow[] (via api TableQuery)
 * * DatasetRow -> RowDigest (via digest)
 * * DatasetRow -> RowValue (via val)
 *
 * * Critical: DatasetRows have a Digest which can be used to associate the same data
 *  across different datasets.
 */

import _, {sum} from 'lodash';
import {useEffect, useMemo, useRef, useState} from 'react';

import {WB_RUN_COLORS} from '../../../../../../common/css/color.styles';
import {useDeepMemo} from '../../../../../../hookUtils';
import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {
  EvaluationComparisonResults,
  EvaluationComparisonSummary,
  MetricDefinition,
} from '../CompareEvaluationsPage/ecpTypes';
import {
  EVALUATION_NAME_DEFAULT,
  getScoreKeyNameFromScorerRef,
  metricDefinitionId,
} from '../CompareEvaluationsPage/ecpUtil';
import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {
  convertISOToDate,
  projectIdFromParts,
} from '../wfReactInterface/tsDataModelHooks';
import {Loadable} from '../wfReactInterface/wfDataModelHooksInterface';
import {TraceCallSchema} from './traceServerClientTypes';

/**
 * Primary react hook for fetching evaluation comparison data. This could be
 * moved into the Trace Server hooks at some point, hence the location of the file.
 */
export const useEvaluationComparisonSummary = (
  entity: string,
  project: string,
  evaluationCallIds: string[]
): Loadable<EvaluationTraceComparisonSummary> => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [data, setData] = useState<EvaluationTraceComparisonSummary | null>(
    null
  );
  const evaluationCallIdsMemo = useDeepMemo(evaluationCallIds);
  const evaluationCallIdsRef = useRef(evaluationCallIdsMemo);

  useEffect(() => {
    setData(null);
    let mounted = true;
    fetchEvaluationSummaryData(
      getTraceServerClient(),
      entity,
      project,
      evaluationCallIdsMemo
    ).then(dataRes => {
      if (mounted) {
        evaluationCallIdsRef.current = evaluationCallIdsMemo;
        setData(dataRes);
      }
    });
    return () => {
      mounted = false;
    };
  }, [entity, evaluationCallIdsMemo, project, getTraceServerClient]);

  return useMemo(() => {
    if (
      data == null ||
      evaluationCallIdsRef.current !== evaluationCallIdsMemo
    ) {
      return {loading: true, result: null};
    }
    return {loading: false, result: data};
  }, [data, evaluationCallIdsMemo]);
};

/**
 * Primary react hook for fetching evaluation comparison data. This could be
 * moved into the Trace Server hooks at some point, hence the location of the file.
 */
export const useEvaluationComparisonResults = (
  entity: string,
  project: string,
  evaluationCallIds: string[],
  summaryData: EvaluationTraceComparisonSummary | null
): Loadable<EvaluationComparisonResults> => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [data, setData] = useState<EvaluationComparisonResults | null>(null);
  const evaluationCallIdsMemo = useDeepMemo(evaluationCallIds);
  const evaluationCallIdsRef = useRef(evaluationCallIdsMemo);

  useEffect(() => {
    setData(null);
    let mounted = true;
    if (summaryData == null) {
      return;
    }
    fetchEvaluationComparisonResults(
      getTraceServerClient(),
      entity,
      project,
      evaluationCallIdsMemo,
      summaryData,
      summaryData._evaluationCallCache
    ).then(dataRes => {
      if (mounted) {
        evaluationCallIdsRef.current = evaluationCallIdsMemo;
        setData(dataRes);
      }
    });
    return () => {
      mounted = false;
    };
  }, [
    entity,
    evaluationCallIdsMemo,
    project,
    getTraceServerClient,
    summaryData,
  ]);

  return useMemo(() => {
    if (
      data == null ||
      evaluationCallIdsRef.current !== evaluationCallIdsMemo
    ) {
      return {loading: true, result: null};
    }
    return {loading: false, result: data};
  }, [data, evaluationCallIdsMemo]);
};

const fetchEvaluationSummaryData = async (
  traceServerClient: TraceServerClient, // TODO: Bad that this is leaking into user-land
  entity: string,
  project: string,
  evaluationCallIds: string[]
): Promise<EvaluationTraceComparisonSummary> => {
  const projectId = projectIdFromParts({entity, project});
  const result: EvaluationTraceComparisonSummary = {
    entity,
    project,
    evaluationCalls: {},
    evaluations: {},
    models: {},
    scoreMetrics: {},
    summaryMetrics: {},
    _evaluationCallCache: {},
  };
  // 1. Fetch the evaluation calls
  // 2. For each evaluation:
  //   2.1: Fetch the scorers
  //   2.2: Fetch the model
  //   2.3: Fetch the dataset
  //        2.3.1: Fetch the rows. For each row:
  //            2.3.1.1: Fetch the prediction
  //            2.3.1.1: Fetch the scores
  // 1: populate the evaluationCalls
  const evalRes = await traceServerClient.callsStreamQuery({
    project_id: projectId,
    filter: {call_ids: evaluationCallIds},
  });

  const evaluationCallCache: {[callId: string]: EvaluationEvaluateCallSchema} =
    Object.fromEntries(
      evalRes.calls.map(call => [call.id, call as EvaluationEvaluateCallSchema])
    );

  // Store the evaluation call cache for later use
  result._evaluationCallCache = evaluationCallCache;

  result.evaluationCalls = Object.fromEntries(
    evalRes.calls.map((call, ndx) => [
      call.id,
      {
        callId: call.id,
        name: call.display_name ?? EVALUATION_NAME_DEFAULT,
        color: pickColor(ndx),
        evaluationRef: call.inputs.self,
        modelRef: call.inputs.model,
        summaryMetrics: {}, // These cannot be filled out yet since we don't know the IDs yet
        traceId: call.trace_id,
      },
    ])
  );

  const evalRefs = evalRes.calls.map(call => call.inputs.self);
  const modelRefs = evalRes.calls.map(call => call.inputs.model);
  const combinedEvalAndModelObjs = await traceServerClient.readBatch({
    refs: [...evalRefs, ...modelRefs],
  });
  const evalObjs = combinedEvalAndModelObjs.vals.slice(0, evalRefs.length);
  const modelObjs = combinedEvalAndModelObjs.vals.slice(evalRefs.length);

  // 2. populate the actual evaluation objects
  result.evaluations = Object.fromEntries(
    evalObjs.map((objVal, objNdx) => {
      const ref = evalRefs[objNdx];
      const parsed = parseRef(ref) as WeaveObjectRef;
      const objData = objVal;
      return [
        ref,
        {
          ref,
          datasetRef: objData.dataset,
          scorerRefs: objData.scorers,
          entity: parsed.entityName,
          project: parsed.projectName,
        },
      ];
    })
  );

  // Backfill the evaluationCalls with the summary metrics
  Object.entries(result.evaluationCalls).forEach(([evalCallId, evalCall]) => {
    const evalObj = result.evaluations[evalCall.evaluationRef];
    if (evalObj == null) {
      return;
    }
    const output = evaluationCallCache[evalCall.callId].output;
    if (output == null) {
      return;
    }

    // Check if this is an imperative evaluation
    // const isImperativeEvaluation = isImperative(
    //   evaluationCallCache[evalCall.callId]
    // );
    const isImperativeEvaluation = false;

    if (isImperativeEvaluation) {
      processImperativeEvaluationSummary(result, evalCall, evalCallId, output);
    } else {
      processEvaluationSummary(result, evalCall, evalCallId, evalObj, output);
    }

    // Add the derived metrics - common for both regular and imperative evals
    // Model latency
    if (output.model_latency != null) {
      const metricId = metricDefinitionId(modelLatencyMetricDimension);
      result.summaryMetrics[metricId] = {
        ...modelLatencyMetricDimension,
      };
      evalCall.summaryMetrics[metricId] = {
        value: output.model_latency.mean,
        sourceCallId: evalCallId,
      };
      result.scoreMetrics[metricId] = {
        ...modelLatencyMetricDimension,
      };
    }

    // Total Tokens
    // TODO: This "mean" is incorrect - really should average across all model
    // calls since this includes LLM scorers
    const summary = evaluationCallCache[evalCall.callId].summary;
    const totalTokens = summary
      ? sum(Object.values(summary.usage ?? {}).map(v => v.total_tokens))
      : null;
    if (totalTokens != null) {
      const metricId = metricDefinitionId(totalTokensMetricDimension);
      result.summaryMetrics[metricId] = {
        ...totalTokensMetricDimension,
      };
      evalCall.summaryMetrics[metricId] = {
        value: totalTokens,
        sourceCallId: evalCallId,
      };
      result.scoreMetrics[metricId] = {
        ...totalTokensMetricDimension,
      };
    }
  });

  // 3. populate the model objects
  result.models = Object.fromEntries(
    modelObjs.map((objVal, objNdx) => {
      const ref = modelRefs[objNdx];
      const parsed = parseRef(ref) as WeaveObjectRef;
      const objData = objVal;
      if (objData == null) {
        return [ref, null];
      }
      return [
        ref,
        {
          ref,
          properties: Object.fromEntries(
            Object.entries(objData as any).filter(
              ([key]) =>
                key !== 'predict' &&
                !key.startsWith('_') &&
                key !== 'name' &&
                key !== 'description'
            )
          ) as any,
          predictOpRef: objData.predict,
          entity: parsed.entityName,
          project: parsed.projectName,
        },
      ];
    })
  );

  return result;
};

/**
 * This function is responsible for building the data structure used to describe
 * the comparison of evaluations. It is a complex function that fetches data from
 * the trace server and builds a normalized data structure.
 */
const fetchEvaluationComparisonResults = async (
  traceServerClient: TraceServerClient, // TODO: Bad that this is leaking into user-land
  entity: string,
  project: string,
  evaluationCallIds: string[],
  summaryData: EvaluationComparisonSummary,
  evaluationCallCache?: {[callId: string]: EvaluationEvaluateCallSchema}
): Promise<EvaluationComparisonResults> => {
  const projectId = projectIdFromParts({entity, project});
  const result: EvaluationComparisonResults = {
    inputs: {},
    resultRows: {},
  };

  // Kick off the trace query to get the actual trace data
  // Note: we split this into 2 steps to ensure we only get level 2 children
  // of the evaluations. This avoids massive overhead of fetching gigantic traces
  // for every evaluation.
  const evalTraceIds = Object.values(summaryData.evaluationCalls).map(
    call => call.traceId
  );

  // First, get all the children of the evaluations (predictAndScoreCalls + summary)
  const evalTraceResProm = traceServerClient
    .callsStreamQuery({
      project_id: projectId,
      filter: {trace_ids: evalTraceIds, parent_ids: evaluationCallIds},
    })
    .then(predictAndScoreCallRes => {
      const predictAndScoreIds = predictAndScoreCallRes.calls.map(
        call => call.id
      );

      return Promise.all(
        _.chunk(predictAndScoreIds, 500).map(chunk => {
          return traceServerClient
            .callsStreamQuery({
              project_id: projectId,
              filter: {trace_ids: evalTraceIds, parent_ids: chunk},
            })
            .then(predictionsAndScoresCallsRes => {
              return predictionsAndScoresCallsRes.calls;
            });
        })
      ).then(predictionsAndScoresCallsResMany => {
        return {
          calls: [
            ...predictAndScoreCallRes.calls,
            ...predictionsAndScoresCallsResMany.flat(),
          ],
        };
      });
    });

  // 3.5 Populate the inputs
  // Check if we have imperative evaluations
  const hasImperativeEvals = evaluationCallCache
    ? Object.keys(summaryData.evaluationCalls).some(
        id => id in evaluationCallCache && isImperative(evaluationCallCache[id])
      )
    : false;

  // Store imperative calls for later use
  let imperativePredictAndScoreCalls: TraceCallSchema[] = [];

  if (hasImperativeEvals) {
    // For imperative evaluations, extract inputs from the predict_and_score calls
    // Wait for trace data to be fetched
    const evalTraceRes = await evalTraceResProm;

    // Find all imperative predict_and_score calls
    imperativePredictAndScoreCalls = evalTraceRes.calls.filter(call =>
      call.op_name.includes('Evaluation.predict_and_score:')
    );

    // Extract inputs from these calls
    imperativePredictAndScoreCalls.forEach(call => {
      if (!call || !call.inputs) {
        return;
      }

      try {
        const example = call.inputs.example;
        if (example && typeof example === 'object') {
          // Create a stable digest for the example object
          const digest = generateStableDigest(example);

          // Add to inputs if not already present
          if (!result.inputs[digest]) {
            result.inputs[digest] = {
              digest,
              val: example,
            };
          }
        }
      } catch (e) {
        console.warn('Error extracting input from imperative call:', e);
      }
    });
  } else {
    // Original logic for regular evaluations
    // We only need 1 since we are going to effectively do an inner join on the rowDigest
    const datasetRef = Object.values(summaryData.evaluations)[0]
      .datasetRef as string;
    const datasetObjRes = await traceServerClient.readBatch({
      refs: [datasetRef],
    });
    // If the dataset has not been deleted, fetch rows
    if (datasetObjRes.vals[0] != null) {
      const rowsRef = datasetObjRes.vals[0].rows;
      const parsedRowsRef = parseRef(rowsRef) as WeaveObjectRef;
      const rowsQuery = await traceServerClient.tableQuery({
        project_id: projectIdFromParts({
          entity: parsedRowsRef.entityName,
          project: parsedRowsRef.projectName,
        }),
        digest: parsedRowsRef.artifactVersion,
      });
      rowsQuery.rows.forEach(row => {
        result.inputs[row.digest] = {
          digest: row.digest,
          val: row.val,
        };
      });
    }
  }

  // 4. Populate the predictions and scores
  const evalTraceRes = await evalTraceResProm;

  // Create a set of all of the scorer refs
  const scorerRefs = new Set(
    Object.values(summaryData.evaluations).flatMap(
      evaluation => evaluation.scorerRefs
    )
  );

  // Create a map of all the predict_and_score_ops
  const predictAndScoreOps = Object.fromEntries(
    evalTraceRes.calls
      .filter(
        call =>
          call.op_name.includes(PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC) ||
          call.op_name.includes('Evaluation.predict_and_score:') // Include imperative predict_and_score calls
      )
      .map(call => [call.id, call])
  );

  const summaryOps = evalTraceRes.calls.filter(
    call =>
      call.op_name.includes('Evaluation.summarize:') &&
      call.parent_id &&
      evaluationCallIds.includes(call.parent_id)
  );

  // Fill in the autosummary source calls
  summaryOps.forEach(summarizedOp => {
    const evalCallId = summarizedOp.parent_id!;
    const evalCall = summaryData.evaluationCalls[evalCallId];
    if (evalCall == null) {
      return;
    }
    Object.entries(evalCall.summaryMetrics).forEach(
      ([metricId, metricResult]) => {
        if (
          summaryData.summaryMetrics[metricId].source === 'scorer' ||
          // Special case that the model latency is also a summary metric calc
          metricDefinitionId(modelLatencyMetricDimension) === metricId
        ) {
          metricResult.sourceCallId = summarizedOp.id;
        }
      }
    );
  });

  const modelRefs = Object.values(summaryData.evaluationCalls).map(
    evalCall => evalCall.modelRef
  );

  // Next, we need to build the predictions object
  evalTraceRes.calls.forEach(traceCall => {
    // We are looking for 2 types of calls:
    // 1. Predict calls
    // 2. Score calls.
    if (
      traceCall.parent_id != null &&
      predictAndScoreOps[traceCall.parent_id] != null
    ) {
      const parentPredictAndScore = predictAndScoreOps[traceCall.parent_id];
      const exampleRef = parentPredictAndScore.inputs.example;

      // Handle imperative evaluation predict and score calls
      const isImperativePredictAndScore =
        // parentPredictAndScore.op_name.includes('Evaluation.predict_and_score:');
        false;

      // For imperative evaluations, we need to handle different input structure
      let modelRef;
      let evaluationCallId;
      let rowDigest;

      if (isImperativePredictAndScore) {
        modelRef = parentPredictAndScore.inputs.model;
        evaluationCallId = parentPredictAndScore.parent_id!;

        // For imperative evaluations, the example is the direct input object
        // We need to create a stable digest for it
        try {
          if (exampleRef && typeof exampleRef === 'object') {
            rowDigest = generateStableDigest(exampleRef);
          } else {
            // Skip if we can't identify the example
            return;
          }
        } catch (e) {
          console.warn('Error generating digest for imperative example:', e);
          return;
        }
      } else {
        modelRef = parentPredictAndScore.inputs.model;
        evaluationCallId = parentPredictAndScore.parent_id!;

        // For regular evaluations, extract digest from dataset path
        const split = '/attr/rows/id/';
        if (typeof exampleRef === 'string' && exampleRef.includes(split)) {
          const parts = exampleRef.split(split);
          if (parts.length === 2) {
            const maybeDigest = parts[1];
            if (maybeDigest != null && !maybeDigest.includes('/')) {
              rowDigest = maybeDigest;
            } else {
              // Skip if we can't identify the row digest
              return;
            }
          } else {
            // Skip if we can't parse the dataset path
            return;
          }
        } else {
          // Skip if we can't identify the dataset path
          return;
        }
      }

      // Detect call types with different strategies for imperative vs regular
      let isProbablyPredictCall;
      let isProbablyScoreCall;
      let isProbablyBoundScoreCall;

      if (isImperativePredictAndScore) {
        // For imperative, check for Model.predict
        isProbablyPredictCall = traceCall.op_name.includes('Model.predict:');
        // For imperative, check different score patterns
        isProbablyScoreCall = traceCall.op_name.includes('.score:');
        isProbablyBoundScoreCall = false; // Typically not used in imperative mode
      } else {
        // Standard evaluation logic
        isProbablyPredictCall =
          modelRefs.includes(traceCall.inputs.self) ||
          modelRefs.includes(traceCall.op_name);

        isProbablyScoreCall = scorerRefs.has(traceCall.op_name);
        isProbablyBoundScoreCall = scorerRefs.has(traceCall.inputs.self);
      }

      if (result.resultRows[rowDigest] == null) {
        result.resultRows[rowDigest] = {
          evaluations: {},
        };
      }
      const digestCollection = result.resultRows[rowDigest];

      if (digestCollection.evaluations[evaluationCallId] == null) {
        digestCollection.evaluations[evaluationCallId] = {
          predictAndScores: {},
        };
      }

      const modelForDigestCollection =
        digestCollection.evaluations[evaluationCallId];

      if (
        modelForDigestCollection.predictAndScores[parentPredictAndScore.id] ==
        null
      ) {
        modelForDigestCollection.predictAndScores[parentPredictAndScore.id] = {
          callId: parentPredictAndScore.id,
          exampleRef,
          rowDigest,
          modelRef,
          evaluationCallId,
          scoreMetrics: {},
          _rawPredictAndScoreTraceData: parentPredictAndScore,
          _rawPredictTraceData: undefined,
        };
      }

      const predictAndScoreFinal =
        modelForDigestCollection.predictAndScores[parentPredictAndScore.id];

      if (isProbablyPredictCall) {
        predictAndScoreFinal._rawPredictTraceData = traceCall;

        // Add model latency and tokens
        const modelLatencyMetricId = metricDefinitionId(
          modelLatencyMetricDimension
        );
        predictAndScoreFinal.scoreMetrics[modelLatencyMetricId] = {
          value:
            (convertISOToDate(
              traceCall.ended_at ?? traceCall.started_at
            ).getTime() -
              convertISOToDate(traceCall.started_at).getTime()) /
            1000, // why is this different than the predictandscore model latency?
          sourceCallId: traceCall.id,
        };

        // Add total tokens
        const totalTokensmetricId = metricDefinitionId(
          totalTokensMetricDimension
        );
        const totalTokens = sum(
          Object.values(traceCall.summary?.usage ?? {}).map(
            (x: any) => x?.total_tokens ?? 0
          )
        );
        predictAndScoreFinal.scoreMetrics[totalTokensmetricId] = {
          value: totalTokens,
          sourceCallId: traceCall.id,
        };
      } else if (isProbablyScoreCall || isProbablyBoundScoreCall) {
        const results = traceCall.output as any;

        let scorerRef = traceCall.op_name;
        if (isProbablyBoundScoreCall) {
          scorerRef = traceCall.inputs.self;
        }

        const recursiveAddScore = (scoreVal: any, currPath: string[]) => {
          if (isBinaryScore(scoreVal)) {
            const metricDimension: MetricDefinition = {
              scoreType: 'binary',
              metricSubPath: currPath,
              source: 'scorer',
              scorerOpOrObjRef: scorerRef,
            };
            const metricId = metricDefinitionId(metricDimension);
            summaryData.scoreMetrics[metricId] = metricDimension;
            predictAndScoreFinal.scoreMetrics[metricId] = {
              sourceCallId: traceCall.id,
              value: scoreVal,
            };
          } else if (isContinuousScore(scoreVal)) {
            const metricDimension: MetricDefinition = {
              scoreType: 'continuous',
              metricSubPath: currPath,
              source: 'scorer',
              scorerOpOrObjRef: scorerRef,
            };
            const metricId = metricDefinitionId(metricDimension);
            summaryData.scoreMetrics[metricId] = metricDimension;

            predictAndScoreFinal.scoreMetrics[metricId] = {
              sourceCallId: traceCall.id,
              value: scoreVal,
            };
          } else if (
            scoreVal != null &&
            typeof scoreVal === 'object' &&
            !Array.isArray(scoreVal)
          ) {
            Object.entries(scoreVal).forEach(([key, val]) => {
              recursiveAddScore(val, [...currPath, key]);
            });
          }
        };

        recursiveAddScore(results, []);
      } else {
        // pass
      }
    } else {
      const maybeParentSummaryOp = summaryOps.find(
        op => op.id === traceCall.parent_id
      );
      const isSummaryChild = maybeParentSummaryOp != null;
      const isProbablyBoundScoreCall = scorerRefs.has(
        traceCall.inputs.self ?? ''
      );
      const isSummaryOp = traceCall.op_name.includes('summarize:');
      if (isSummaryChild && isProbablyBoundScoreCall && isSummaryOp) {
        // Now fill in the source of the eval score
        const evalCallId = maybeParentSummaryOp!.parent_id!;
        const evalCall = summaryData.evaluationCalls[evalCallId];
        if (evalCall == null) {
          return;
        }
        Object.entries(evalCall.summaryMetrics).forEach(
          ([metricId, metricResult]) => {
            if (metricId.startsWith(traceCall.inputs.self)) {
              metricResult.sourceCallId = traceCall.id;
            }
          }
        );
      }
    }
  });

  // Filter out non-intersecting rows
  result.resultRows = Object.fromEntries(
    Object.entries(result.resultRows).filter(([digest, row]) => {
      // Check if we have imperative evaluations
      // const hasImperativeEvals = evaluationCallCache
      //   ? Object.keys(summaryData.evaluationCalls).some(
      //       id =>
      //         id in evaluationCallCache && isImperative(evaluationCallCache[id])
      //     )
      //   : false;

      // // For imperative evaluations, we're more lenient
      // if (hasImperativeEvals) {
      //   // For imperative evaluations:
      //   // 1. Make sure the row digest exists in our inputs
      //   // 2. Make sure at least one evaluation has results for this row
      //   return (
      //     digest in result.inputs && Object.keys(row.evaluations).length > 0
      //   );
      // }
      console.log('row.evaluations', row.evaluations);
      console.log('summaryData.evaluationCalls', summaryData.evaluationCalls);

      // For standard evaluations, we want exact matches across all evaluations
      return (
        Object.values(row.evaluations).length ===
        Object.values(summaryData.evaluationCalls).length
      );
    })
  );

  // Additional debug check to ensure we have examples
  if (Object.keys(result.resultRows).length === 0) {
    console.log('Warning: No example rows found for evaluation comparison.');
    // If inputs exist but no resultRows, let's try to be more permissive
    if (Object.keys(result.inputs).length > 0) {
      // Add a simple placeholder entry for each input
      Object.entries(result.inputs).forEach(([digest, input]) => {
        // For each input that has an evaluation result, add it to resultRows
        if (
          Object.values(summaryData.evaluationCalls).some(
            call => result.resultRows[digest]?.evaluations[call.callId]
          )
        ) {
          result.resultRows[digest] = result.resultRows[digest] || {
            evaluations: Object.fromEntries(
              Object.values(summaryData.evaluationCalls).map(call => [
                call.callId,
                {predictAndScores: {}},
              ])
            ),
          };
        }
      });
    }
  }

  // If we still don't have matching results in resultRows for our inputs, try direct matching
  if (
    Object.keys(result.resultRows).length === 0 &&
    imperativePredictAndScoreCalls.length > 0
  ) {
    // This means we have imperative evaluations but couldn't match inputs to resultRows
    // Let's try to manually build result entries from predict_and_score calls directly
    imperativePredictAndScoreCalls.forEach(
      (predictAndScoreCall: TraceCallSchema) => {
        try {
          if (!predictAndScoreCall || !predictAndScoreCall.inputs) {
            return;
          }

          const example = predictAndScoreCall.inputs.example;
          const modelRef = predictAndScoreCall.inputs.model;
          const evaluationCallId = predictAndScoreCall.parent_id;

          if (!evaluationCallId) {
            return;
          }

          if (example && typeof example === 'object') {
            // Generate stable digest for the example
            const digest = generateStableDigest(example);

            // Ensure input exists
            if (!result.inputs[digest]) {
              result.inputs[digest] = {
                digest,
                val: example,
              };
            }

            // Create result entry if it doesn't exist
            if (!result.resultRows[digest]) {
              result.resultRows[digest] = {
                evaluations: {},
              };
            }

            // Add evaluation entry if it doesn't exist
            if (!result.resultRows[digest].evaluations[evaluationCallId]) {
              result.resultRows[digest].evaluations[evaluationCallId] = {
                predictAndScores: {},
              };
            }

            // Add predict_and_score entry
            result.resultRows[digest].evaluations[
              evaluationCallId
            ].predictAndScores[predictAndScoreCall.id] = {
              callId: predictAndScoreCall.id,
              exampleRef: example,
              rowDigest: digest,
              modelRef,
              evaluationCallId,
              scoreMetrics: {},
              _rawPredictAndScoreTraceData: predictAndScoreCall,
              _rawPredictTraceData: evalTraceRes.calls.find(
                call =>
                  call &&
                  call.parent_id === predictAndScoreCall.id &&
                  call.op_name &&
                  call.op_name.includes('Model.predict:')
              ),
            };

            // Find and add score calls
            const scoreCalls = evalTraceRes.calls.filter(
              call =>
                call &&
                call.parent_id === predictAndScoreCall.id &&
                call.op_name &&
                call.op_name.includes('.score:')
            );

            scoreCalls.forEach(scoreCall => {
              if (!scoreCall || !scoreCall.op_name) {
                return;
              }

              const scorerRef = scoreCall.op_name;
              const results = scoreCall.output as any;

              if (results) {
                const metricId = `${scorerRef}-score`;
                const metricDimension: MetricDefinition = {
                  scoreType:
                    typeof results === 'boolean' ? 'binary' : 'continuous',
                  metricSubPath: [],
                  source: 'scorer',
                  scorerOpOrObjRef: scorerRef,
                };

                summaryData.scoreMetrics[metricId] = metricDimension;
                result.resultRows[digest].evaluations[
                  evaluationCallId
                ].predictAndScores[predictAndScoreCall.id].scoreMetrics[
                  metricId
                ] = {
                  sourceCallId: scoreCall.id,
                  value: results,
                };
              }
            });
          }
        } catch (e) {
          console.warn('Error during direct matching of imperative call:', e);
        }
      }
    );
  }

  return result;
};

/// Non exported helpers below

const modelLatencyMetricDimension: MetricDefinition = {
  source: 'derived',
  scoreType: 'continuous',
  metricSubPath: ['Model Latency (avg)'],
  shouldMinimize: true,
  unit: 's',
};

const totalTokensMetricDimension: MetricDefinition = {
  source: 'derived',
  scoreType: 'continuous',
  metricSubPath: ['Total Tokens'],
  shouldMinimize: true,
  unit: '',
};
const pickColor = (ndx: number) => {
  return WB_RUN_COLORS[ndx % WB_RUN_COLORS.length];
};

const isBinaryScore = (score: any): score is boolean => {
  return typeof score === 'boolean';
};

const isBinarySummaryScore = (score: any): score is BinarySummaryScore => {
  return (
    typeof score === 'object' &&
    score != null &&
    'true_count' in score &&
    'true_fraction' in score
  );
};

const isContinuousSummaryScore = (
  score: any
): score is ContinuousSummaryScore => {
  return typeof score === 'object' && score != null && 'mean' in score;
};

const isContinuousScore = (score: any): score is number => {
  return typeof score === 'number';
};

type BinarySummaryScore = {
  true_count: number;
  true_fraction: number;
};

type ContinuousSummaryScore = {
  mean: number;
};

export type EvaluationEvaluateCallSchema = TraceCallSchema & {
  inputs: TraceCallSchema['inputs'] & {
    self: string;
    model: string;
  };
  output: TraceCallSchema['output'] & {
    [scorer: string]: {
      [score: string]: SummaryScore;
    };
  } & {
    model_latency: ContinuousSummaryScore;
  };
  summary: TraceCallSchema['summary'] & {
    usage?: {
      [model: string]: {
        requests?: number;
        completion_tokens?: number;
        prompt_tokens?: number;
        total_tokens?: number;
      };
    };
  };
};
type EvaluationTraceComparisonSummary = EvaluationComparisonSummary & {
  _evaluationCallCache?: {[callId: string]: EvaluationEvaluateCallSchema};
};

type SummaryScore = BinarySummaryScore | ContinuousSummaryScore;

function fuzzyMatchScorerName(
  scoreNames: string[],
  possibleScorerName: string
) {
  // anytime we see a '-' in possibleScorerName, it can be any illegal character
  // in score names. Use a regex to find matches, and return the first match.
  const regex = new RegExp(possibleScorerName.replace(/-/g, '.'));
  return scoreNames.find(name => regex.test(name));
}

/**
 * Determines if an evaluation call is an imperative evaluation
 */
const isImperative = (evalCall: EvaluationEvaluateCallSchema): boolean => {
  // Check for characteristics that identify imperative evaluations
  // 1. Check op_name for Evaluation.summarize (imperative uses this op)
  // 2. Check for a direct summary structure in the output
  return (
    evalCall.op_name.includes('Evaluation.summarize:') ||
    (evalCall.output != null &&
      typeof evalCall.output === 'object' &&
      !Array.isArray(evalCall.output) &&
      Object.keys(evalCall.output).length > 0)
  );
};

/**
 * Process summary data specifically for imperative evaluations
 */
const processImperativeEvaluationSummary = (
  result: EvaluationTraceComparisonSummary,
  evalCall: any,
  evalCallId: string,
  output: any
): void => {
  // In imperative evaluations, the metrics can appear directly in the output object
  // We need to recursively process them to extract all metrics
  const recursiveAddMetric = (metricVal: any, currPath: string[]) => {
    if (typeof metricVal === 'boolean') {
      const metricDimension: MetricDefinition = {
        scoreType: 'binary',
        metricSubPath: currPath,
        source: 'derived', // Using 'derived' since we don't have a direct scorer reference
      };
      const metricId = metricDefinitionId(metricDimension);
      result.summaryMetrics[metricId] = metricDimension;
      evalCall.summaryMetrics[metricId] = {
        value: metricVal,
        sourceCallId: evalCallId,
      };
    } else if (typeof metricVal === 'number') {
      const metricDimension: MetricDefinition = {
        scoreType: 'continuous',
        metricSubPath: currPath,
        source: 'derived',
      };
      const metricId = metricDefinitionId(metricDimension);
      result.summaryMetrics[metricId] = metricDimension;
      evalCall.summaryMetrics[metricId] = {
        value: metricVal,
        sourceCallId: evalCallId,
      };
    } else if (
      metricVal != null &&
      typeof metricVal === 'object' &&
      !Array.isArray(metricVal)
    ) {
      // Special case for auto-summarized binary scores
      if (isBinarySummaryScore(metricVal)) {
        const metricDimension: MetricDefinition = {
          scoreType: 'binary',
          metricSubPath: currPath,
          source: 'derived',
        };
        const metricId = metricDefinitionId(metricDimension);
        result.summaryMetrics[metricId] = metricDimension;
        evalCall.summaryMetrics[metricId] = {
          value: metricVal.true_fraction,
          sourceCallId: evalCallId,
        };
      }
      // Special case for auto-summarized continuous scores
      else if (isContinuousSummaryScore(metricVal)) {
        const metricDimension: MetricDefinition = {
          scoreType: 'continuous',
          metricSubPath: currPath,
          source: 'derived',
        };
        const metricId = metricDefinitionId(metricDimension);
        result.summaryMetrics[metricId] = metricDimension;
        evalCall.summaryMetrics[metricId] = {
          value: metricVal.mean,
          sourceCallId: evalCallId,
        };
      }
      // Otherwise, process nested objects
      else {
        Object.entries(metricVal).forEach(([key, val]) => {
          recursiveAddMetric(val, [...currPath, key]);
        });
      }
    }
  };

  // Start processing from the root of the output
  Object.entries(output).forEach(([key, val]) => {
    recursiveAddMetric(val, [key]);
  });
};

/**
 * Process summary data specifically for regular (non-imperative) evaluations
 */
const processEvaluationSummary = (
  result: EvaluationTraceComparisonSummary,
  evalCall: any,
  evalCallId: string,
  evalObj: any,
  output: any
): void => {
  // Add the user-defined scores
  evalObj.scorerRefs.forEach((scorerRef: string) => {
    const scorerKey = getScoreKeyNameFromScorerRef(scorerRef);
    // TODO: REMOVE when sanitized scorer names have been released
    // this is a hack to support previous unsanitized scorer names
    // that have spaces.
    let score = output[scorerKey];
    if (score == null && scorerKey.includes('-')) {
      // no score found, '-' means we probably sanitized an illegal character
      const foundScorerNameMaybe = fuzzyMatchScorerName(
        Object.keys(output),
        scorerKey
      );
      if (foundScorerNameMaybe != null) {
        score = output[foundScorerNameMaybe];
      }
    }
    const recursiveAddScore = (scoreVal: any, currPath: string[]) => {
      if (isBinarySummaryScore(scoreVal)) {
        const metricDimension: MetricDefinition = {
          scoreType: 'binary',
          metricSubPath: currPath,
          source: 'scorer',
          scorerOpOrObjRef: scorerRef,
        };
        const metricId = metricDefinitionId(metricDimension);
        result.summaryMetrics[metricId] = metricDimension;
        evalCall.summaryMetrics[metricId] = {
          value: scoreVal.true_fraction,
          // Later on this will be updated to the Summary or CustomScorer's Summary Call
          sourceCallId: evalCallId,
        };
      } else if (isContinuousSummaryScore(scoreVal)) {
        const metricDimension: MetricDefinition = {
          scoreType: 'continuous',
          metricSubPath: currPath,
          source: 'scorer',
          scorerOpOrObjRef: scorerRef,
        };
        const metricId = metricDefinitionId(metricDimension);
        result.summaryMetrics[metricId] = metricDimension;
        evalCall.summaryMetrics[metricId] = {
          value: scoreVal.mean,
          // Later on this will be updated to the Summary or CustomScorer's Summary Call
          sourceCallId: evalCallId,
        };
      } else if (typeof scoreVal === 'boolean') {
        const metricDimension: MetricDefinition = {
          scoreType: 'binary',
          metricSubPath: currPath,
          source: 'scorer',
          scorerOpOrObjRef: scorerRef,
        };
        const metricId = metricDefinitionId(metricDimension);
        result.summaryMetrics[metricId] = metricDimension;
        evalCall.summaryMetrics[metricId] = {
          value: scoreVal,
          // Later on this will be updated to the Summary or CustomScorer's Summary Call
          sourceCallId: evalCallId,
        };
      } else if (typeof scoreVal === 'number') {
        const metricDimension: MetricDefinition = {
          scoreType: 'continuous',
          metricSubPath: currPath,
          source: 'scorer',
          scorerOpOrObjRef: scorerRef,
        };
        const metricId = metricDefinitionId(metricDimension);
        result.summaryMetrics[metricId] = metricDimension;
        evalCall.summaryMetrics[metricId] = {
          value: scoreVal,
          // Later on this will be updated to the Summary or CustomScorer's Summary Call
          sourceCallId: evalCallId,
        };
      } else if (
        scoreVal != null &&
        typeof scoreVal === 'object' &&
        !Array.isArray(scoreVal)
      ) {
        Object.entries(scoreVal).forEach(([key, val]) => {
          recursiveAddScore(val, [...currPath, key]);
        });
      }
    };

    recursiveAddScore(score, []);
  });
};

// Improve the generateStableDigest function to handle edge cases
const generateStableDigest = (obj: any): string => {
  if (obj === undefined || obj === null) {
    return 'null'; // Return consistent string for null/undefined
  }

  try {
    // Sort keys to ensure stable stringification
    const sortObjectKeys = (val: any): any => {
      if (val === null || val === undefined) {
        return null;
      }

      if (typeof val !== 'object' || Array.isArray(val)) {
        return val;
      }

      return Object.keys(val)
        .sort()
        .reduce((result: any, key) => {
          result[key] = sortObjectKeys(val[key]);
          return result;
        }, {});
    };

    return JSON.stringify(sortObjectKeys(obj));
  } catch (e) {
    // In case of any JSON serialization errors, return a fallback value
    console.warn('Error generating stable digest:', e);
    return `digest_${Date.now()}`;
  }
};
