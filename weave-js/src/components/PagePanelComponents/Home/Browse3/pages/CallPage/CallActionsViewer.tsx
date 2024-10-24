import {Box, Button, TextField, Typography} from '@material-ui/core';
import {Drawer} from '@material-ui/core';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useMemo, useState} from 'react';
import {z} from 'zod';

import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {
  ActionOpMapping,
  ConfiguredAction,
} from '../../collections/actionCollection';
import {useCollectionObjects} from '../../collections/getCollectionObjects';
import {DynamicConfigForm} from '../../DynamicConfigForm';
import {WEAVE_REF_SCHEME} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

type CallActionRow = {
  actionRef: string;
  actionDef: ConfiguredAction;
  runCount: number;
  lastResult?: Record<string, unknown>;
};

export const CallActionsViewer: React.FC<{
  call: CallSchema;
}> = props => {
  const {artifactName, artifactVersion} =
    parseRefMaybe(props.call.traceCall?.op_name ?? '') ?? {};
  const {useFeedback} = useWFHooks();
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
  const configuredActions = useCollectionObjects('ConfiguredAction', {
    project_id: projectIdFromParts({
      entity: props.call.entity,
      project: props.call.project,
    }),
    filter: {latest_only: true},
  });



  const verifiedActionFeedbacks: ActionFeedback[] = useMemo(() => {
    return (feedbackQuery.result ?? [])
      .map(feedback => {
        const res = ActionFeedbackZ.safeParse(feedback.payload);
        return res;
      })
      .filter(result => result.success)
      .map(result => result.data) as ActionFeedback[];
  }, [feedbackQuery.result]);

  const getFeedbackForAction = (actionRef: string) => {
    console.log('verifiedActionFeedbacks', verifiedActionFeedbacks);
    return verifiedActionFeedbacks.filter(
      feedback => feedback.configured_action_ref === actionRef
    );
  };

  const getClient = useGetTraceServerClientContext();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newMapping, setNewMapping] = useState<Partial<ActionOpMapping>>({
    name: '',
    op_name: artifactName || '',
    op_digest: artifactVersion || '*',
    input_mapping: {},
  });

  const handleSaveMapping = () => {
    // TODO: Implement the logic to save the new mapping
    console.log('New mapping:', newMapping);
    setIsModalOpen(false);
  };


  const allCallActions: CallActionRow[] = useMemo(() => {
    return (
      configuredActions?.map(configuredAction => {
        const configuredActionRefUri = objectVersionKeyToRefUri({
          scheme: WEAVE_REF_SCHEME,
          weaveKind: 'object',
          entity: props.call.entity,
          project: props.call.project,
          objectId: configuredAction.object_id,
          versionHash: configuredAction.digest,
          path: '',
        });
        const feedbacks = getFeedbackForAction(configuredActionRefUri);
        return {
          actionRef: configuredActionRefUri,
          actionDef: configuredAction.val,
          runCount: feedbacks.length,
          lastResult: feedbacks.length > 0 ? feedbacks[0].output : undefined,
        };
      }) ?? []
    );
  }, [configuredActions, getFeedbackForAction, props.call.entity, props.call.project]);


  return (
    <>
      <table>
        <thead>
          <tr>
            <th>Action</th>
            <th>Run Count</th>
            <th>Last Result</th>
            <th>Run</th>
          </tr>
        </thead>
        <tbody>
          {allCallActions.map(action => {
            const actionRef = action.actionRef;
            const feedbacks = getFeedbackForAction(action.actionRef ?? '');
            return (
              <tr key={actionRef}>
                <td>{action.actionDef.name}</td>
                <td>{feedbacks.length}</td>
                <td>
                  {feedbacks.length > 0
                    ? JSON.stringify(feedbacks[0].output)
                    : 'N/A'}
                </td>

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
                          configured_action_ref: action.actionRef,
                        })
                        .then(res => {
                          feedbackQuery.refetch();
                        });
                    }}>
                    Run
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <Drawer
        anchor="right"
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile
        }}>
        <Box
          sx={{
            width: '40vw',
            marginTop: '60px',
            height: '100%', // -40 for the header
            bgcolor: 'background.paper',
            p: 4,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'auto',
          }}>
          <Typography
            id="create-action-mapping-modal"
            variant="h6"
            component="h2"
            gutterBottom>
            Create Action Mapping
          </Typography>
          <TextField
            fullWidth
            label="Name"
            value={newMapping.name}
            onChange={e =>
              setNewMapping(prev => ({...prev, name: e.target.value}))
            }
            margin="normal"
          />
          <Typography variant="subtitle1" gutterBottom>
            Input Mapping
          </Typography>
          <DynamicConfigForm
            configSchema={z.record(z.string())}
            config={newMapping.input_mapping || {}}
            setConfig={newInputMapping =>
              setNewMapping(prev => ({...prev, input_mapping: newInputMapping}))
            }
          />
          <Box sx={{display: 'flex', justifyContent: 'flex-end', mt: 2}}>
            <Button
              onClick={() => setIsModalOpen(false)}
              style={{marginRight: 8}}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveMapping}
              variant="contained"
              color="primary">
              Save
            </Button>
          </Box>
        </Box>
      </Drawer>
    </>
  );
};

const ActionFeedbackZ = z.object({
  // _type: z.literal("ActionFeedback"),
  configured_action_ref: z.string(),
  output: z.record(z.string(), z.unknown()),
});

type ActionFeedback = z.infer<typeof ActionFeedbackZ>;
