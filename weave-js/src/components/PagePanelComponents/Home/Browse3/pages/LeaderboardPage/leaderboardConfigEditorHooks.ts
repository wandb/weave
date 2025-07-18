import {parseRefMaybe, refUri} from '@wandb/weave/react';
import {useEffect, useState} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../flattenObject';
import {ALL_VALUE} from '../../views/Leaderboard/types/leaderboardConfigType';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {opVersionKeyToRefUri} from '../wfReactInterface/utilities';

export type EvaluationHelperObj = {
  obj: TraceObjSchema;
  ref: string;
  name: string;
  versionIndex: number;
  digest: string;
};

export const useEvaluationObjects = (
  entity: string,
  project: string
): EvaluationHelperObj[] => {
  const getClient = useGetTraceServerClientContext();
  const client = getClient();
  const [evalObjs, setEvalObjs] = useState<EvaluationHelperObj[]>([]);
  useEffect(() => {
    let mounted = true;
    client
      .objsQuery({
        project_id: projectIdFromParts({entity, project}),
        filter: {
          base_object_classes: ['Evaluation'],
          is_op: false,
        },
        metadata_only: true,
        sort_by: [{field: 'created_at', direction: 'desc'}],
      })
      .then(res => {
        if (mounted) {
          setEvalObjs(
            res.objs.map(obj => ({
              obj,
              ref: refUri({
                scheme: 'weave',
                entityName: entity,
                projectName: project,
                weaveKind: 'object',
                artifactName: obj.object_id,
                artifactVersion: obj.digest,
              }),
              name: obj.object_id,
              versionIndex: obj.version_index,
              digest: obj.digest,
            }))
          );
        }
      });

    return () => {
      mounted = false;
    };
  }, [client, entity, project]);
  return evalObjs;
};

export const useScorers = (
  entity: string,
  project: string,
  evaluationObjectRef: string
): string[] => {
  const getClient = useGetTraceServerClientContext();
  const client = getClient();
  const [scorers, setScorers] = useState<string[]>([]);

  useEffect(() => {
    if (!evaluationObjectRef) {
      setScorers([]);
      return;
    }

    let mounted = true;
    client.readBatch({refs: [evaluationObjectRef]}).then(res => {
      if (mounted) {
        const scorers = (res.vals[0].scorers ?? [])
          .map((scorer: string) => parseRefMaybe(scorer)?.artifactName)
          .filter(Boolean) as string[];

        // Regular eval; populate scorers from the scorers field
        if (scorers.length > 0) {
          setScorers(scorers);
          return;
        }

        // Imperative eval; populate scorers using the eval's output key
        client
          .callsStreamQuery({
            project_id: projectIdFromParts({entity, project}),
            filter: {
              op_names: [
                opVersionKeyToRefUri({
                  entity,
                  project,
                  opId: EVALUATE_OP_NAME_POST_PYDANTIC,
                  versionHash: ALL_VALUE,
                }),
              ],
              input_refs: [evaluationObjectRef],
            },
            limit: 1,
          })
          .then(evalCallsRes => {
            if (mounted && evalCallsRes.calls.length > 0) {
              const output = evalCallsRes.calls[0].output ?? {};
              if (typeof output === 'object' && output != null) {
                // Extract scorer names from the output keys
                const outputObj = output as Record<string, any>;
                const extractedScorers = Object.keys(outputObj).filter(
                  key =>
                    // Filter out any non-scorer keys if needed
                    key !== '_result' && typeof outputObj[key] === 'object'
                );
                setScorers(extractedScorers);
              }
            }
          })
          .catch(err => {
            console.error(
              'Failed to fetch evaluation calls for scorer extraction:',
              err
            );
          });
      }
    });

    return () => {
      mounted = false;
    };
  }, [client, entity, project, evaluationObjectRef]);

  return scorers;
};

export const useMetrics = (
  entity: string,
  project: string,
  evaluationObjectRef: string,
  scorerName: string
): string[] => {
  const getClient = useGetTraceServerClientContext();
  const client = getClient();
  const [metrics, setMetrics] = useState<string[]>([]);

  useEffect(() => {
    if (!evaluationObjectRef || !scorerName) {
      setMetrics([]);
      return;
    }

    let mounted = true;
    client
      .callsStreamQuery({
        project_id: projectIdFromParts({entity, project}),
        filter: {
          op_names: [
            opVersionKeyToRefUri({
              entity,
              project,
              opId: EVALUATE_OP_NAME_POST_PYDANTIC,
              versionHash: ALL_VALUE,
            }),
          ],
          input_refs: [evaluationObjectRef],
        },
        limit: 1,
      })
      .then(res => {
        if (mounted) {
          const calls = res.calls;
          if (calls.length === 0) {
            setMetrics([]);
          } else {
            const output = calls[0].output ?? {};
            if (
              typeof output === 'object' &&
              output != null &&
              scorerName in output
            ) {
              setMetrics(
                Object.keys(
                  flattenObjectPreservingWeaveTypes(
                    (output as Record<string, any>)[scorerName]
                  )
                )
              );
            } else {
              setMetrics([]);
            }
          }
        }
      });

    return () => {
      mounted = false;
    };
  }, [client, entity, project, evaluationObjectRef, scorerName]);

  return metrics;
};
