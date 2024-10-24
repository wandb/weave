import {Box, Button, Modal, TextField, Typography} from '@material-ui/core';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useMemo, useState} from 'react';
import {z} from 'zod';

import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {
  ActionOpMapping,
  ActionWithConfig,
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
  actionDef: ActionWithConfig;
  // mapping?: ActionOpMapping;
  // mappingRef?: string;
  runCount: number;
  lastResult: Record<string, unknown>;
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
  const actionWithConfigs = useCollectionObjects('ActionWithConfig', {
    project_id: projectIdFromParts({
      entity: props.call.entity,
      project: props.call.project,
    }),
    filter: {latest_only: true},
  });

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
        return {
          actionRef: actionWithConfigRefUri,
          actionDef: actionWithConfig.val,
          runCount: 0,
          lastResult: {},
        };
      }) ?? []
    );
  }, [actionWithConfigs, props.call.entity, props.call.project]);

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
    return verifiedActionFeedbacks.filter(
      feedback => feedback.action_ref === actionRef
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
                    ? JSON.stringify(feedbacks[0].results)
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

      <Modal
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        aria-labelledby="create-action-mapping-modal">
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            // transform: 'translate(-50%, -50%)',
            width: 400,
            bgcolor: 'background.paper',
            boxShadow: 24,
            p: 4,
            borderRadius: 2,
            display: 'flex',
            flexDirection: 'column',
            maxHeight: '80vh',
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
      </Modal>
    </>
  );
};

const ActionFeedbackZ = z.object({
  // _type: z.literal("ActionFeedback"),
  name: z.string(),
  action_ref: z.string(),
  results: z.record(z.string(), z.unknown()),
});

type ActionFeedback = z.infer<typeof ActionFeedbackZ>;
