import {parseRef, WeaveObjectRef} from '../../../../../../react';
import {PREDICT_AND_SCORE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {
  TraceCallSchema,
  TraceObjSchema,
  TraceServerClient,
} from '../wfReactInterface/traceServerClient';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {EvaluationEvaluateCallSchema} from './evaluations';

export type BinarySummaryScore = {
  true_count: number;
  true_fraction: number;
};

export type ContinuousSummaryScore = {
  mean: number;
};

export const isBinarySummaryScore = (
  score: BinarySummaryScore | ContinuousSummaryScore
): score is BinarySummaryScore => {
  return 'true_count' in score && 'true_fraction' in score;
};

export const isContinuousSummaryScore = (
  score: BinarySummaryScore | ContinuousSummaryScore
): score is ContinuousSummaryScore => {
  return 'mean' in score;
};

type EvaluationCall = {
  callId: string;
  name: string;
  color: string;
  evaluationRef: string;
  modelRef: string;
  scores: {
    [scoreName: string]: {
      [path: string]: BinarySummaryScore | ContinuousSummaryScore;
    };
  };
  _rawEvaluationTraceData: EvaluationEvaluateCallSchema;
};

type EvaluationObj = {
  ref: string;
  datasetRef: string;
  scorerRefs: string[];
  project: string;
  entity: string;
  _rawEvaluationObject: TraceObjSchema;
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
  project: string;
  entity: string;
  _rawModelObject: TraceObjSchema;
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

const generateColorFromId = (id: string) => {
  const hash = id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const hue = hash % 360;
  const saturation = 70 + (hash % 30); // Saturation between 70% and 100%
  const lightness = 40 + (hash % 20); // Lightness between 40% and 60%
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
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
        color: generateColorFromId(call.id),
        evaluationRef: call.inputs.self,
        modelRef: call.inputs.model,
        scores: Object.fromEntries(
          Object.entries(call.output as any).filter(
            ([key]) => key !== 'model_latency'
          )
        ) as any,
        _rawEvaluationTraceData: call as EvaluationEvaluateCallSchema,
      },
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

  // 3. populate the model objects
  const modelRefs = evalRes.calls.map(call => call.inputs.model);
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
          _rawModelObject: objRes.obj,
        },
      ];
    })
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
