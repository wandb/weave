import {PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {
  TraceCallSchema,
  TraceObjSchema,
  TraceServerClient,
} from '../wfReactInterface/traceServerClient';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {EvaluationEvaluateCallSchema} from './evaluations';

type BinarySummaryScore = {
  true_count: number;
  true_fraction: number;
};

type ContinuousSummaryScore = {
  mean: number;
};

type EvaluationCall = {
  callId: string;
  name: string;
  color: string;
  evaluationRef: string;
  modelRef: string;
  scores: {
    [scorerRef: string]: {
      [path: string]: BinarySummaryScore | ContinuousSummaryScore;
    };
  };
  _rawEvaluationTraceData: EvaluationEvaluateCallSchema;
};

type EvaluationObj = {
  ref: string;
  datasetRef: string;
  scorerRefs: string[];
  _rawEvaluationObjectVersionData: TraceObjSchema;
};

//   type Scorer = {
//     ref: string;
//     //   scoreSchema: string; ??
//     _rawScorerObjectVersionData: TraceObjSchema;
//   };

//   type Dataset = {
//     ref: string;
//     rowDigests: string[];
//     _rawDatasetObjectVersionData: TraceObjSchema;
//   };

type PredictCall = {
  callId: string;
  inputDigest: string;
  modelRef: string;
  _rawPredictTraceData: TraceCallSchema;
};

//   type Input = {
//     digest: string;
//     data: any;
//   };

type ModelObj = {
  ref: string;
  predictOpRef: string;
  properties: {[prop: string]: any};
  _rawModelObjectVersionData: TraceObjSchema;
};

type ScoreResults = {
  callId: string;
  results: {[path: string]: number | boolean};
  _rawScoreTraceData: TraceCallSchema;
};

export type EvaluationComparisonData = {
  entity: string;
  project: string;
  evaluationCalls: {
    [callId: string]: EvaluationCall;
  };
  evaluations: {
    [objectRef: string]: EvaluationObj;
  };
  //   datasets: {
  //     [objectRef: string]: Dataset;
  //   };
  //   scorers: {
  //     [objectRef: string]: Scorer;
  //   };
  //   inputs: {
  //     [rowDigest: string]: Input;
  //   };
  models: {
    [modelRef: string]: ModelObj;
  };
  resultRows: {
    [rowDigest: string]: {
      models: {
        [modelRef: string]: {
          prediction?: PredictCall;
          scores: {
            [scorerRef: string]: ScoreResults;
          };
        };
      };
    };
  };
};

export const fetchEvaluationComparisonData = async (
  traceServerClient: TraceServerClient, // TODO: Bad that this is leaking into user-land
  entity: string,
  project: string,
  evaluationCallIds: string[]
): Promise<EvaluationComparisonData> => {
  //   const [result, setResult] = useState<EvaluationComparisonState | null>(null);
  const projectId = projectIdFromParts({entity, project});
  const result: EvaluationComparisonData = {
    entity,
    project,
    evaluationCalls: {},
    evaluations: {},
    // datasets: {},
    // scorers: {},
    // inputs: {},
    models: {},
    resultRows: {},
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
    filter: {call_ids: evaluationCallIds},
  });
  result.evaluationCalls = Object.fromEntries(
    evalRes.calls.map((call, ndx) => [
      call.id,
      {
        callId: call.id,
        // TODO: Get user-defined name for the evaluation
        name: 'Evaluation',
        // TODO: Get user-defined color for the evaluation
        color: `hsl(${(ndx * 360) / evalRes.calls.length}, 100%, 50%)`,
        evaluationRef: call.inputs.self,
        modelRef: call.inputs.model,
        scores: Object.fromEntries(
          Object.entries(call.output as any).filter(
            ([key]) => key !== 'model_usage'
          )
        ) as any,
        _rawEvaluationTraceData: call as EvaluationEvaluateCallSchema,
      },
    ])
  );

  // 2. populate the actual evaluation objects
  const evalRefs = evalRes.calls.map(call => call.inputs.self);
  const evalObjRes = await traceServerClient.readBatch({refs: evalRefs});
  result.evaluations = Object.fromEntries(
    evalObjRes.vals.map((obj, objNdx) => [
      evalRefs[objNdx],
      {
        ref: evalRefs[objNdx],
        datasetRef: obj.dataset,
        scorerRefs: obj.scorers,
        _rawEvaluationObjectVersionData: obj,
      },
    ])
  );

  // 3. populate the model objects
  const modelRefs = evalRes.calls.map(call => call.inputs.model);
  const modelObjRes = await traceServerClient.readBatch({refs: modelRefs});
  result.models = Object.fromEntries(
    modelObjRes.vals.map((obj, objNdx) => [
      modelRefs[objNdx],
      {
        ref: modelRefs[objNdx],
        properties: Object.fromEntries(
          Object.entries(obj as any).filter(([key]) => key !== 'predict')
        ) as any,
        predictOpRef: obj.predict,
        _rawEvaluationObjectVersionData: obj,
      },
    ])
  );

  // 4. Populate the predictions and scores
  const evalTraceIds = evalRes.calls.map(call => call.trace_id);
  const evalTraceRes = await traceServerClient.callsQuery({
    project_id: projectId,
    filter: {trace_ids: evalTraceIds},
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
      .filter(call => call.op_name === PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC)
      .map(call => [call.id, call])
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
      const modelRef = parentPredictAndScore.inputs.model;

      const split = '/attr/rows/id/';
      if (exampleRef.includes(split)) {
        const parts = exampleRef.split(split);
        if (parts.length === 2) {
          const maybeDigest = parts[1];
          if (maybeDigest != null && !maybeDigest.includes('/')) {
            const rowDigest = maybeDigest;
            const isProbablyPredictCall =
              traceCall.op_name.includes('predict:') &&
              modelRefs.includes(traceCall.inputs.model);

            const isProbablyScoreCall = scorerRefs.has(traceCall.op_name);

            if (result.resultRows[rowDigest] == null) {
              result.resultRows[rowDigest] = {
                models: {},
              };
            }

            if (result.resultRows[rowDigest].models[modelRef] == null) {
              result.resultRows[rowDigest].models[modelRef] = {
                prediction: undefined,
                scores: {},
              };
            }

            if (isProbablyPredictCall) {
              result.resultRows[rowDigest].models[modelRef].prediction = {
                callId: traceCall.id,
                inputDigest: rowDigest,
                modelRef,
                _rawPredictTraceData: traceCall,
              };
            } else if (isProbablyScoreCall) {
              result.resultRows[rowDigest].models[modelRef].scores[
                traceCall.op_name
              ] = {
                callId: traceCall.id,
                results: traceCall.output as any,
                _rawScoreTraceData: traceCall,
              };
            }
          }
        }
      }
    }
  });

  return result;
};
