import { sum } from 'lodash';
import _ from 'lodash';
import {useEffect, useMemo, useState} from 'react';

import { WB_RUN_COLORS } from '../../../../../../common/css/color.styles';
import {useDeepMemo} from '../../../../../../hookUtils';
import {parseRef, WeaveObjectRef} from '../../../../../../react';
import { PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC } from '../common/heuristics';
import { TraceServerClient } from '../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import { convertISOToDate,projectIdFromParts } from '../wfReactInterface/tsDataModelHooks';
import {Loadable} from '../wfReactInterface/wfDataModelHooksInterface';
import {
  DerivedMetricDefinition,
  EvaluationCall,
  EvaluationComparisonData,
  EvaluationEvaluateCallSchema,
  isBinaryScore,
  isBinarySummaryScore,
  isContinuousScore,
  isContinuousSummaryScore,
  ScorerDefinition,
  ScorerMetricDimension,
} from './ecpTypes';
import {ComparisonDimensionsType} from './ecpTypes';
import {EvaluationComparisonState} from './ecpTypes';
import { dimensionId } from './ecpUtil';

export const useEvaluationComparisonState = (
  entity: string,
  project: string,
  evaluationCallIds: string[],
  baselineEvaluationCallId?: string,
  comparisonDimensions?: ComparisonDimensionsType,
  selectedInputDigest?: string
): Loadable<EvaluationComparisonState> => {
  const data = useEvaluationComparisonData(
    entity,
    project,
    evaluationCallIds
  )

  const value = useMemo(() => {
    if (data.result == null || data.loading) {
      return {loading: true, result: null};
    }

    const scorerDimensions = Object.values(data.result.scorerMetricDimensions);
    const derivedDimensions = Object.values(data.result.derivedMetricDimensions);

    let newComparisonDimensions = comparisonDimensions;
    if (newComparisonDimensions == null) {
      newComparisonDimensions = [];
      if (scorerDimensions.length > 0) {
        newComparisonDimensions.push({
          dimension: scorerDimensions[0]
        }); 
        if (derivedDimensions.length > 0) {
          newComparisonDimensions.push({
            dimension: derivedDimensions[0]
          });
        }
      } else {
        if (derivedDimensions.length > 0) {
          newComparisonDimensions.push({
            dimension: derivedDimensions[0]
          });
        }
        if (derivedDimensions.length > 1) {
          newComparisonDimensions.push({
            dimension: derivedDimensions[1]
          });
        }
      }
    }

    return {
      loading: false,
      result: {
        data: data.result,
        baselineEvaluationCallId:
          baselineEvaluationCallId ?? evaluationCallIds[0],
        comparisonDimensions: newComparisonDimensions,
        selectedInputDigest,
      } 
    };
  }, [data.result, data.loading, baselineEvaluationCallId, evaluationCallIds, comparisonDimensions, selectedInputDigest]);

  return value;
};

// const evaluationCallDimensions = (
//   data: EvaluationComparisonData
// ): EvaluationMetricDimension[] => {
//   // const availableScorers = Object.values(evaluationCalls)
//   //   .map(evalCall =>
//   //     Object.entries(evalCall.scores)
//   //       .map(([k, v]) => Object.keys(v).map(innerKey => k + '.' + innerKey))
//   //       .flat()
//   //   )
//   //   .flat();
//   const availableScorersMap: {[ref: string]: {[path: string]: EvaluationMetricDimension}} =
//     {};
//   const recordScorer = (scoreDim: EvaluationMetricDimension) => {
//     if (!availableScorersMap[scoreDim.scorerOpOrObjRef]) {
//       availableScorersMap[scoreDim.scorerOpOrObjRef] = {};
//     }
//     availableScorersMap[scoreDim.scorerOpOrObjRef][scoreDim.scoreKeyPath] = scoreDim;
//   };

//   const addScore = (score: any, scoreRef: string, scoreKeyPath: string) => {
//     // Two types of scores: single value and dict
//     if (isBinarySummaryScore(score)) {
//       recordScorer({
//         scorerOpOrObjRef: scoreRef,
//         scoreKeyPath,
//         scoreType: 'binary',
//         minimize: false,
//       });
//     } else if (isContinuousSummaryScore(score)) {
//       recordScorer({
//         scorerOpOrObjRef: scoreRef,
//         scoreKeyPath,
//         scoreType: 'continuous',
//         minimize: false,
//       });
//     } else if (
//       score != null &&
//       typeof score === 'object' &&
//       !Array.isArray(score)
//     ) {
//       Object.entries(score).forEach(([key, value]) => {
//         addScore(value, scoreRef, scoreKeyPath + '.' + key);
//       });
//     }
//   };

//   Object.values(data.evaluationCalls).forEach(evalCall => {
//     const evalObject = data.evaluations[evalCall.evaluationRef];
//     evalObject.scorerRefs.forEach(scoreRef => {
//       const scorerKey = (parseRef(scoreRef) as WeaveObjectRef).artifactName;
//       // TODO(Metric Refactor): Should put scores at the top level using the ref, not name as the key!
//       const score = evalCall._rawEvaluationTraceData.output[scorerKey];
//       addScore(score, scoreRef, scorerKey);
//     });
//   });

//   // recordScorer({
//   //   scorerRef: ,
//   //   scoreKeyPath: scoreKeyPath,
//   //   scoreType: 'continuous',
//   //   minimize: false,
//   // })

//   return [
//     ...Object.values(availableScorersMap).map(Object.values).flat(),
//     // 'model_latency',
//     // 'total_tokens',
//   ];
// };


const pickColor = (ndx: number) => {
  return WB_RUN_COLORS[ndx % WB_RUN_COLORS.length];
};

const useEvaluationComparisonData = (
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
}

const fetchEvaluationComparisonData = async (
  traceServerClient: TraceServerClient, // TODO: Bad that this is leaking into user-land
  entity: string,
  project: string,
  evaluationCallIds: string[]
): Promise<EvaluationComparisonData> => {
  //   const [result, setResult] = useState<EvaluationComparisonState | null>(null);
  const projectId = projectIdFromParts({ entity, project });
  const result: EvaluationComparisonData = {
    entity,
    project,
    evaluationCalls: {},
    evaluations: {},
    inputs: {},
    models: {},
    resultRows: {},
    derivedMetricDimensions: {},
    scorerMetricDimensions: {},
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
  const evalRes = await traceServerClient.callsQuery({
    project_id: projectId,
    filter: { call_ids: evaluationCallIds },
  });
  result.evaluationCalls = Object.fromEntries(
    evalRes.calls.map((call, ndx) => [
      call.id,
      {
        callId: call.id,
        // TODO: Get user-defined name for the evaluation
        name: 'Evaluation',
        color: pickColor(ndx),
        // color: generateColorFromId(call.id),
        evaluationRef: call.inputs.self,
        modelRef: call.inputs.model,
        summaryMetrics: {}, // These cannot be filled out yet since we don't know the IDs yet
        _rawEvaluationTraceData: call as EvaluationEvaluateCallSchema,
      } as EvaluationCall,
    ])
  );

  // UGG! Move to backend
  const objReadMany = (refs: string[]) => {
    const proms = refs.map(ref => {
      const parsed = parseRef(ref) as WeaveObjectRef;
      return traceServerClient.objRead({
        project_id: projectIdFromParts({
          entity: parsed.entityName,
          project: parsed.projectName,
        }),
        object_id: parsed.artifactName,
        digest: parsed.artifactVersion,
      });
    });
    return Promise.all(proms);
  };

  // 2. populate the actual evaluation objects
  const evalRefs = evalRes.calls.map(call => call.inputs.self);
  const evalObjRes = await objReadMany(evalRefs);
  result.evaluations = Object.fromEntries(
    evalObjRes.map((objRes, objNdx) => {
      const ref = evalRefs[objNdx];
      const parsed = parseRef(ref) as WeaveObjectRef;
      const objData = objRes.obj.val;
      return [
        ref,
        {
          ref,
          datasetRef: objData.dataset,
          scorerRefs: objData.scorers,
          entity: parsed.entityName,
          project: parsed.projectName,
          _rawEvaluationObject: objRes.obj,
        },
      ];
    })
  );

  // Backfill the evaluationCalls with the summary metrics
  Object.entries(result.evaluationCalls).forEach(([evalCallId, evalCall]) => {
    const evalObj = result.evaluations[evalCall.evaluationRef]
    if (evalObj == null) {
      return;
    }

    // Add the user-defined scores
    evalObj.scorerRefs.forEach(scorerRef => {
      const scorerKey = getScoreKeyNameFromScorerRef(scorerRef);
      const score = evalCall._rawEvaluationTraceData.output[scorerKey];
      const scorerDef: ScorerDefinition = {
        scorerOpOrObjRef: scorerRef,
        likelyTopLevelKeyName: scorerKey,
      }

        const recursiveAddScore = (scoreVal: any, currPath: string[]) => {
          if (isBinarySummaryScore(scoreVal)) {
            const metricDimension: ScorerMetricDimension = {
              dimensionType: 'scorerMetric',
              scorerDef: {...scorerDef},
              metricSubPath: currPath,
              scoreType: 'binary',
            }
            const metricDimensionId = dimensionId(metricDimension);
            result.scorerMetricDimensions[metricDimensionId] = metricDimension;
            evalCall.summaryMetrics[metricDimensionId] = scoreVal;
          } else if (isContinuousSummaryScore(scoreVal)) {
            const metricDimension: ScorerMetricDimension = {
              dimensionType: 'scorerMetric',
              scorerDef: {...scorerDef},
              metricSubPath: currPath,
              scoreType: 'continuous',
            }
            const metricDimensionId = dimensionId(metricDimension);
            result.scorerMetricDimensions[metricDimensionId] = metricDimension;
            evalCall.summaryMetrics[metricDimensionId] = scoreVal;
          } else if (scoreVal != null && typeof scoreVal === 'object' && !Array.isArray(scoreVal)) {
            Object.entries(scoreVal).forEach(([key, val]) => {
              recursiveAddScore(val, [...currPath, key]);
            })
          }
        }

        recursiveAddScore(score, []);
    })

    // Add the derived metrics
    // Model latency
    const model_latency = evalCall._rawEvaluationTraceData.output.model_latency;
    if (model_latency != null) {
      const metricDimensionId = dimensionId(modelLatencyMetricDimension);
      result.derivedMetricDimensions[metricDimensionId] = {...modelLatencyMetricDimension};
      evalCall.summaryMetrics[metricDimensionId] = model_latency;
    }

    // Total Tokens
    // TODO: This "mean" is incorrect - really should average across all model 
    // calls since this includes LLM scorers
    const totalTokens = sum(
            Object.values(
              evalCall._rawEvaluationTraceData.summary.usage ?? {}
            ).map(v => v.total_tokens)
          )
    if (totalTokens != null) {

      const metricDimensionId = dimensionId(totalTokensMetricDimension);
      result.derivedMetricDimensions[metricDimensionId] = {...totalTokensMetricDimension};
      evalCall.summaryMetrics[metricDimensionId] = { 'mean': totalTokens };
    }
  })

  // 3. populate the model objects
  const modelRefs = evalRes.calls.map(call => call.inputs.model);
  // console.log(modelRefs)
  const modelObjRes = await objReadMany(modelRefs);
  result.models = Object.fromEntries(
    modelObjRes.map((objRes, objNdx) => {
      const ref = modelRefs[objNdx];
      const parsed = parseRef(ref) as WeaveObjectRef;
      const objData = objRes.obj.val;
      return [
        ref,
        {
          ref,
          properties: Object.fromEntries(
            Object.entries(objData as any).filter(
              ([key]) => key !== 'predict' &&
                !key.startsWith('_') &&
                key !== 'name' &&
                key !== 'description'
            )
          ) as any,
          predictOpRef: objData.predict,
          entity: parsed.entityName,
          project: parsed.projectName,
          _rawModelObject: objRes.obj,
        },
      ];
    })
  );

  // 3.5 Populate the inputs
  // We only ned 1 since we are going to effectively do an inner join on the rowDigest
  const datasetRef = Object.values(result.evaluations)[0].datasetRef as string;
  const parsedDatasetRef = parseRef(datasetRef) as WeaveObjectRef;
  const datasetObjRes = await traceServerClient.objRead({
    project_id: projectIdFromParts({
      entity: parsedDatasetRef.entityName,
      project: parsedDatasetRef.projectName,
    }),
    digest: parsedDatasetRef.artifactVersion,
    object_id: parsedDatasetRef.artifactName,
  });
  const rowsRef = datasetObjRes.obj.val.rows;
  const parsedRowsRef = parseRef(rowsRef) as WeaveObjectRef;
  const rowsQuery = await traceServerClient.tableQuery({
    project_id: projectIdFromParts({
      entity: parsedRowsRef.entityName,
      project: parsedRowsRef.projectName,
    }),
    digest: parsedRowsRef.artifactVersion,
  });
  // console.log(parsedDatasetRef);
  rowsQuery.rows.forEach(row => {
    result.inputs[row.digest] = {
      digest: row.digest,
      val: row.val,
    };
  });

  // 4. Populate the predictions and scores
  const evalTraceIds = evalRes.calls.map(call => call.trace_id);
  const evalTraceRes = await traceServerClient.callsQuery({
    project_id: projectId,
    filter: { trace_ids: evalTraceIds },
  });

  // Create a set of all of the scorer refs
  const scorerRefs = new Set(
    Object.values(result.evaluations).flatMap(
      evaluation => evaluation.scorerRefs
    )
  );

  // Create a map of all the predict_and_score_ops
  const predictAndScoreOps = Object.fromEntries(
    evalTraceRes.calls
      .filter(call => call.op_name.includes(PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC)
      )
      .map(call => [call.id, call])
  );

  // console.log(evalTraceRes, predictAndScoreOps)
  // Next, we need to build the predictions object
  evalTraceRes.calls.forEach(traceCall => {
    // We are looking for 2 types of calls:
    // 1. Predict calls
    // 2. Score calls.
    if (traceCall.parent_id != null &&
      predictAndScoreOps[traceCall.parent_id] != null) {
      const parentPredictAndScore = predictAndScoreOps[traceCall.parent_id];
      // console.log(traceCall)
      const exampleRef = parentPredictAndScore.inputs.example;
      const modelRef = parentPredictAndScore.inputs.model;
      const evaluationCallId = parentPredictAndScore.parent_id!;

      const split = '/attr/rows/id/';
      if (exampleRef.includes(split)) {
        const parts = exampleRef.split(split);
        if (parts.length === 2) {
          const maybeDigest = parts[1];
          if (maybeDigest != null && !maybeDigest.includes('/')) {
            const rowDigest = maybeDigest;
            const possiblePredictNames = ['predict', 'infer', 'forward'];
            const isProbablyPredictCall =
              _.some(possiblePredictNames, name => traceCall.op_name.includes(`.${name}:`)) &&
              modelRefs.includes(traceCall.inputs.self);

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
            // resultRows: {
            //   [rowDigest: string]: {
            //     models: {
            //       [modelRef: string]: {
            //         predictAndScores: {
            //           [predictAndScoreCallId: string]: PredictAndScoreCall;
            //         };
            //       }
            //     };
            //   };
            // };
            // type PredictAndScoreCall = {
            //   callId: string;
            //   exampleRef: string;
            //   modelRef: string;
            //   predictCall?: {
            //     callId: string;
            //     exampleRef: string;
            //     output: any
            //     latencyMs: number;
            //     totalUsageTokens: number;
            //     _rawPredictTraceData: TraceCallSchema;
            //   }
            //   scores: {
            //     [scorerRef: string]: ScoreResults;
            //   };
            //   _rawPredictAndScoreTraceData: TraceCallSchema;
            // };
            if (digestCollection.evaluations[evaluationCallId] == null) {
              digestCollection.evaluations[evaluationCallId] = {
                predictAndScores: {},
              };
            }

            const modelForDigestCollection = digestCollection.evaluations[evaluationCallId];

            if (modelForDigestCollection.predictAndScores[parentPredictAndScore.id] == null) {
              modelForDigestCollection.predictAndScores[parentPredictAndScore.id] = {
                callId: parentPredictAndScore.id,
                firstExampleRef: exampleRef,
                rowDigest,
                modelRef,
                evaluationCallId,
                _legacy_predictCall: undefined,
                scorerMetrics: {},
                derivedMetrics: {},
                _rawPredictAndScoreTraceData: parentPredictAndScore,
              };
            }

            const predictAndScoreFinal = modelForDigestCollection.predictAndScores[parentPredictAndScore.id];

            if (isProbablyPredictCall) {
              const totalTokens = sum(
                Object.values(traceCall.summary?.usage ?? {}).map(
                  (x: any) => x?.total_tokens ?? 0
                )
              );
              predictAndScoreFinal._legacy_predictCall = {
                callId: traceCall.id,
                output: traceCall.output as any,
                latencyMs: (convertISOToDate(
                  traceCall.ended_at ?? traceCall.started_at
                ).getTime() -
                  convertISOToDate(traceCall.started_at).getTime()) /
                  1000, // why is this different than the predictandscore model latency?
                totalUsageTokens: totalTokens,
                _rawPredictTraceData: traceCall,
              };

              // Add model latency and tokens
              const modelLatencyMetricDimensionId = dimensionId(modelLatencyMetricDimension);
              predictAndScoreFinal.derivedMetrics[modelLatencyMetricDimensionId] = {
                value: predictAndScoreFinal._legacy_predictCall.latencyMs,
                sourceCall: {
                  callId: traceCall.id,
                  _rawScoreTraceData: traceCall,
                },
              };

              // Add total tokens
              const totalTokensMetricDimensionId = dimensionId(totalTokensMetricDimension);
              predictAndScoreFinal.derivedMetrics[totalTokensMetricDimensionId] = {
                value: predictAndScoreFinal._legacy_predictCall.totalUsageTokens,
                sourceCall: {
                  callId: traceCall.id,
                  _rawScoreTraceData: traceCall,
                },
              };
            } else if (isProbablyScoreCall || isProbablyBoundScoreCall) {
              const results = traceCall.output as any;


               

              let scorerRef = traceCall.op_name;
              if (isProbablyBoundScoreCall) {
                scorerRef = traceCall.inputs.self;
              } 

              const likelyName = getScoreKeyNameFromScorerRef(scorerRef);
              const scorerDef: ScorerDefinition = {
                scorerOpOrObjRef: scorerRef,
                likelyTopLevelKeyName: likelyName,
              }

              const recursiveAddScore = (scoreVal: any, currPath: string[]) => {
                if (isBinaryScore(scoreVal)) {
                  const metricDimension: ScorerMetricDimension = {
                    dimensionType: 'scorerMetric',
                    scorerDef: {...scorerDef},
                    metricSubPath: currPath,
                    scoreType: 'binary',
                  }
                  const metricDimensionId = dimensionId(metricDimension);
                  if (result.scorerMetricDimensions[metricDimensionId] != null) {
                    result.scorerMetricDimensions[metricDimensionId] = metricDimension;
                    predictAndScoreFinal.scorerMetrics[metricDimensionId] = {
                      sourceCall: {
                        callId: traceCall.id,
                        _rawScoreTraceData: traceCall,
                      },
                      value: scoreVal,
                    };
                  } else {
                    console.error('Skipping metric', metricDimensionId);
                  }
                } else if (isContinuousScore(scoreVal)) {
                  const metricDimension: ScorerMetricDimension = {
                    dimensionType: 'scorerMetric',
                    scorerDef: {...scorerDef},
                    metricSubPath: currPath,
                    scoreType: 'continuous',
                  }
                  const metricDimensionId = dimensionId(metricDimension);
                  if (result.scorerMetricDimensions[metricDimensionId] != null) {
                    result.scorerMetricDimensions[metricDimensionId] = metricDimension;
                    predictAndScoreFinal.scorerMetrics[metricDimensionId] = {
                      sourceCall: {
                        callId: traceCall.id,
                        _rawScoreTraceData: traceCall,
                      },
                      value: scoreVal,
                    };
                  } else {
                    console.error('Skipping metric', metricDimensionId);
                  }
                } else if (scoreVal != null && typeof scoreVal === 'object' && !Array.isArray(scoreVal)) {
                  Object.entries(scoreVal).forEach(([key, val]) => {
                    recursiveAddScore(val, [...currPath, key]);
                  })
                }
              }

              recursiveAddScore(results, []);

            } else {
              // console.log(traceCall);
            }
          }
        }
      }
    }
  });


  return result;
};
const moveItemToFront = (arr: any[], item: any) => {
  const index = arr.indexOf(item);
  if (index > -1) {
    arr.splice(index, 1);
    arr.unshift(item);
  }
};

export const getOrderedCallIds = (state: EvaluationComparisonState) => {
  const initial = Object.keys(state.data.evaluationCalls);
  moveItemToFront(initial, state.baselineEvaluationCallId);
  return initial;
};

export const getOrderedModelRefs = (state: EvaluationComparisonState) => {
  const baselineRef = state.data.evaluationCalls[state.baselineEvaluationCallId].modelRef;
  const refs = Object.keys(state.data.models);
  // Make sure the baseline model is first
  moveItemToFront(refs, baselineRef);
  return refs;
};

const getScoreKeyNameFromScorerRef = (scorerRef: string) => {
  const parsed = parseRef(scorerRef) as WeaveObjectRef;
  return parsed.artifactName;
}


const modelLatencyMetricDimension: DerivedMetricDefinition = {
  dimensionType: 'derivedMetric',
  scoreType: 'continuous',
  derivedMetricName: 'Model Latency',
  shouldMinimize: true,
  unit: ' ms',
}

const totalTokensMetricDimension: DerivedMetricDefinition = {
  dimensionType: 'derivedMetric',
  scoreType: 'continuous',
  derivedMetricName: 'Total Tokens',
  shouldMinimize: true,
  unit: '',
}
