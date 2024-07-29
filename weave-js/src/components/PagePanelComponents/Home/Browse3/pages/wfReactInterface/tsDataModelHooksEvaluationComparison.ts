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

import _ from 'lodash';
import {sum} from 'lodash';
import {useEffect, useMemo, useState} from 'react';

import {WB_RUN_COLORS} from '../../../../../../common/css/color.styles';
import {useDeepMemo} from '../../../../../../hookUtils';
import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {
  EvaluationComparisonData,
  MetricDefinition,
} from '../CompareEvaluationsPage/ecpTypes';
import {
  EVALUATION_NAME_DEFAULT,
  metricDefinitionId,
} from '../CompareEvaluationsPage/ecpUtil';
import {getScoreKeyNameFromScorerRef} from '../CompareEvaluationsPage/ecpUtil';
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
export const useEvaluationComparisonData = (
  entity: string,
  project: string,
  evaluationCallIds: string[]
): Loadable<EvaluationComparisonData> => {
  const getTraceServerClient = useGetTraceServerClientContext();
  const [data, setData] = useState<EvaluationComparisonData | null>(null);
  const evaluationCallIdsMemo = useDeepMemo(evaluationCallIds);
  useEffect(() => {
    setData(null);
    let mounted = true;
    fetchEvaluationComparisonData(
      getTraceServerClient(),
      entity,
      project,
      evaluationCallIdsMemo
    ).then(dataRes => {
      if (mounted) {
        setData(dataRes);
      }
    });
    return () => {
      mounted = false;
    };
  }, [entity, evaluationCallIdsMemo, project, getTraceServerClient]);

  return useMemo(() => {
    if (data == null) {
      return {loading: true, result: null};
    }
    return {loading: false, result: data};
  }, [data]);
};

/**
 * This function is responsible for building the data structure used to describe
 * the comparison of evaluations. It is a complex function that fetches data from
 * the trace server and builds a normalized data structure.
 */
const fetchEvaluationComparisonData = async (
  traceServerClient: TraceServerClient, // TODO: Bad that this is leaking into user-land
  entity: string,
  project: string,
  evaluationCallIds: string[]
): Promise<EvaluationComparisonData> => {
  const projectId = projectIdFromParts({entity, project});
  const result: EvaluationComparisonData = {
    entity,
    project,
    evaluationCalls: {},
    evaluations: {},
    inputs: {},
    models: {},
    resultRows: {},
    scoreMetrics: {},
    summaryMetrics: {},
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

  // Kick off the trace query to get the actual trace data
  const evalTraceIds = evalRes.calls.map(call => call.trace_id);
  const evalTraceResProm = traceServerClient.callsStreamQuery({
    project_id: projectId,
    filter: {trace_ids: evalTraceIds},
  });

  const evaluationCallCache: {[callId: string]: EvaluationEvaluateCallSchema} =
    Object.fromEntries(
      evalRes.calls.map(call => [call.id, call as EvaluationEvaluateCallSchema])
    );
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

    // Add the user-defined scores
    evalObj.scorerRefs.forEach(scorerRef => {
      const scorerKey = getScoreKeyNameFromScorerRef(scorerRef);
      const score = output[scorerKey];
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

    // Add the derived metrics
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

  // 3.5 Populate the inputs
  // We only ned 1 since we are going to effectively do an inner join on the rowDigest
  const datasetRef = Object.values(result.evaluations)[0].datasetRef as string;
  const datasetObjRes = await traceServerClient.readBatch({refs: [datasetRef]});
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

  // 4. Populate the predictions and scores
  const evalTraceRes = await evalTraceResProm;

  // Create a set of all of the scorer refs
  const scorerRefs = new Set(
    Object.values(result.evaluations).flatMap(
      evaluation => evaluation.scorerRefs
    )
  );

  // Create a map of all the predict_and_score_ops
  const predictAndScoreOps = Object.fromEntries(
    evalTraceRes.calls
      .filter(call =>
        call.op_name.includes(PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC)
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
    const evalCall = result.evaluationCalls[evalCallId];
    if (evalCall == null) {
      return;
    }
    Object.entries(evalCall.summaryMetrics).forEach(
      ([metricId, metricResult]) => {
        if (
          result.summaryMetrics[metricId].source === 'scorer' ||
          // Special case that the model latency is also a summary metric calc
          metricDefinitionId(modelLatencyMetricDimension) === metricId
        ) {
          metricResult.sourceCallId = summarizedOp.id;
        }
      }
    );
  });

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
      const modelRef = parentPredictAndScore.inputs.model;
      const evaluationCallId = parentPredictAndScore.parent_id!;

      const split = '/attr/rows/id/';
      if (typeof exampleRef === 'string' && exampleRef.includes(split)) {
        const parts = exampleRef.split(split);
        if (parts.length === 2) {
          const maybeDigest = parts[1];
          if (maybeDigest != null && !maybeDigest.includes('/')) {
            const rowDigest = maybeDigest;
            const possiblePredictNames = ['predict', 'infer', 'forward'];
            const isProbablyPredictCall =
              (_.some(possiblePredictNames, name =>
                traceCall.op_name.includes(`.${name}:`)
              ) &&
                modelRefs.includes(traceCall.inputs.self)) ||
              modelRefs.includes(traceCall.op_name);

            const isProbablyScoreCall = scorerRefs.has(traceCall.op_name);
            // WOW - super hacky. we have to do this b/c we support both instances and ops for scorers!
            const isProbablyBoundScoreCall = scorerRefs.has(
              traceCall.inputs.self
            );

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
              modelForDigestCollection.predictAndScores[
                parentPredictAndScore.id
              ] == null
            ) {
              modelForDigestCollection.predictAndScores[
                parentPredictAndScore.id
              ] = {
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
              modelForDigestCollection.predictAndScores[
                parentPredictAndScore.id
              ];

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
                  result.scoreMetrics[metricId] = metricDimension;
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
                  result.scoreMetrics[metricId] = metricDimension;

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
          }
        }
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
        const evalCall = result.evaluationCalls[evalCallId];
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
      return (
        Object.values(row.evaluations).length ===
        Object.values(result.evaluationCalls).length
      );
    })
  );

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
  metricSubPath: ['Total Tokens (avg)'],
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

type EvaluationEvaluateCallSchema = TraceCallSchema & {
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
type SummaryScore = BinarySummaryScore | ContinuousSummaryScore;
