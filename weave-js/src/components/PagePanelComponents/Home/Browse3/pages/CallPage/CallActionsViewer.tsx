import {makeRefCall} from '@wandb/weave/util/refs';
import _ from 'lodash';
import React, {useMemo} from 'react';
import {z} from 'zod';

import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {
  ActionOpMapping,
  ActionWithConfig,
} from '../../collections/actionCollection';
import {useCollectionObjects} from '../../collections/getCollectionObjects';
import {WEAVE_REF_SCHEME} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {
  CallSchema,
  ObjectVersionSchema,
} from '../wfReactInterface/wfDataModelHooksInterface';

type CallActionRow = {
  actionRef: string;
  actionDef: ActionWithConfig;
  mapping?: ActionOpMapping;
  mappingRef?: string;
  runCount: number;
  lastResult: Record<string, unknown>;
};

export const CallActionsViewer: React.FC<{
  call: CallSchema;
}> = props => {
  const {artifactName, artifactVersion} =
    parseRefMaybe(props.call.traceCall?.op_name ?? '') ?? {};
  const {useFeedback, useRootObjectVersions, useRefsData} = useWFHooks();
  const weaveRef = makeRefCall(
    props.call.entity,
    props.call.project,
    props.call.callId
  );
  const feedbackQuery = useFeedback({
    entity: props.call.entity,
    project: props.call.project,
    weaveRef,
  });
  const actionOpMappings = useCollectionObjects('ActionOpMapping', {
    project_id: projectIdFromParts({
      entity: props.call.entity,
      project: props.call.project,
    }),
    filter: {latest_only: true},
  });

  const verifiedActions = useMemo(() => {
    return actionOpMappings.filter(mapping => {
      return (
        mapping.val.op_name === artifactName &&
        (mapping.val.op_digest === artifactVersion ||
          mapping.val.op_digest === '*')
      );
    });
  }, [actionOpMappings, artifactName, artifactVersion]);

  const actionWithConfigs = useCollectionObjects('ActionWithConfig', {
    project_id: projectIdFromParts({
      entity: props.call.entity,
      project: props.call.project,
    }),
    filter: {latest_only: true},
  });

  console.log({actionOpMappings, actionWithConfigs, verifiedActions});

  const allCallActions: CallActionRow[] = useMemo(() => {
    return (
      actionWithConfigs?.map(actionWithConfig => {
        const actionWithConfigRefUri = objectVersionKeyToRefUri({
          scheme: WEAVE_REF_SCHEME,
          weaveKind: 'object',
          entity: props.call.entity,
          project: props.call.project,
          objectId: actionWithConfig.object_id,
          versionHash: actionWithConfig.digest,
          path: '',
        });
        const mapping = verifiedActions?.find(mapping => {
          if (typeof mapping.val.action === 'string') {
            return mapping.val.action === actionWithConfigRefUri;
          } else {
            return _.isEqual(mapping.val.action, actionWithConfig);
          }
        });
        const mappingRef = mapping
          ? objectVersionKeyToRefUri({
              scheme: WEAVE_REF_SCHEME,
              weaveKind: 'object',
              entity: props.call.entity,
              project: props.call.project,
              objectId: mapping.object_id,
              versionHash: mapping.digest,
              path: '',
            })
          : undefined;
        return {
          actionRef: actionWithConfigRefUri,
          actionDef: actionWithConfig.val,
          mapping: mapping?.val,
          mappingRef,
          runCount: 0,
          lastResult: {},
        };
      }) ?? []
    );
  }, [
    verifiedActions,
    actionWithConfigs,
    props.call.entity,
    props.call.project,
  ]);
  //   console.log(allActions.result)

  type BuiltinAction = {
    action_type: 'builtin';
    name: string;
    digest: string;
  };

  type ActionWithConfig = {
    _type: 'ActionWithConfig';
    name: string;
    action: BuiltinAction;
    config: Record<string, unknown>;
  };

  const verifiedActionFeedbacks: ActionFeedback[] = useMemo(() => {
    return (feedbackQuery.result ?? [])
      .map(feedback => {
        const res = ActionFeedbackZ.safeParse(feedback.payload);
        console.log(res);
        return res;
      })
      .filter(result => result.success)
      .map(result => result.data);
  }, [feedbackQuery.result]);

  console.log({verifiedActions, verifiedActionFeedbacks});

  const getFeedbackForAction = (actionRef: string) => {
    return verifiedActionFeedbacks.filter(
      feedback => feedback.action_mapping_ref === actionRef
    );
  };

  const getClient = useGetTraceServerClientContext();

  return (
    <table>
      <thead>
        <tr>
          <th>Action</th>
          <th>Run Count</th>
          <th>Last Result</th>
          <th>Run</th>
          <th>Mapping</th>
        </tr>
      </thead>
      <tbody>
        {allCallActions.map(action => {
          const actionRef = action.actionRef;
          const feedbacks = getFeedbackForAction(action.mappingRef ?? '');
          return (
            <tr key={actionRef}>
              <td>{action.actionDef.name}</td>
              <td>{feedbacks.length}</td>
              <td>
                {feedbacks.length > 0
                  ? JSON.stringify(feedbacks[0].results)
                  : 'N/A'}
              </td>
              {action.mappingRef ? (
                <>
                  <td>
                    <button
                      onClick={() => {
                        // # TODO IF MAPPING REF IS UNDEFINED, THEN WE NEED TO FIND THE CORRECT MAPPING REF
                        getClient()
                          .executeBatchAction({
                            project_id: projectIdFromParts({
                              entity: props.call.entity,
                              project: props.call.project,
                            }),
                            call_ids: [props.call.callId],
                            mapping_ref: action.mappingRef,
                          })
                          .then(res => {
                            feedbackQuery.refetch();
                          });
                      }}>
                      Run
                    </button>
                  </td>
                  <td>
                    <button onClick={console.log}>Edit</button>
                  </td>
                </>
              ) : (
                <>
                  <td></td>
                  <td>
                    <button onClick={console.log}>Create</button>
                  </td>
                </>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

const ActionFeedbackZ = z.object({
  // _type: z.literal("ActionFeedback"),
  name: z.string(),
  action_mapping_ref: z.string(),
  results: z.record(z.string(), z.unknown()),
});

type ActionFeedback = z.infer<typeof ActionFeedbackZ>;
