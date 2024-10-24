import {makeRefCall} from '@wandb/weave/util/refs';
import _ from 'lodash';
import React, {useMemo, useState} from 'react';
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
import {
  Modal,
  Box,
  Typography,
  Button,
  TextField,
} from '@material-ui/core';
import {DynamicConfigForm} from '../../DynamicConfigForm';
import {ActionOpMappingSchema} from '../../collections/actionCollection';

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
  // const actionOpMappings = useCollectionObjects('ActionOpMapping', {
  //   project_id: projectIdFromParts({
  //     entity: props.call.entity,
  //     project: props.call.project,
  //   }),
  //   filter: {latest_only: true},
  // });

  // const verifiedActions = useMemo(() => {
  //   return actionOpMappings.filter(mapping => {
  //     return (
  //       mapping.val.op_name === artifactName &&
  //       (mapping.val.op_digest === artifactVersion ||
  //         mapping.val.op_digest === '*')
  //     );
  //   });
  // }, [actionOpMappings, artifactName, artifactVersion]);

  const actionWithConfigs = useCollectionObjects('ActionWithConfig', {
    project_id: projectIdFromParts({
      entity: props.call.entity,
      project: props.call.project,
    }),
    filter: {latest_only: true},
  });

  // console.log({actionOpMappings, actionWithConfigs, verifiedActions});

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
        // const mapping = verifiedActions?.find(mapping => {
        //   if (typeof mapping.val.action === 'string') {
        //     return mapping.val.action === actionWithConfigRefUri;
        //   } else {
        //     return _.isEqual(mapping.val.action, actionWithConfig);
        //   }
        // });
        // const mappingRef = mapping
        //   ? objectVersionKeyToRefUri({
        //       scheme: WEAVE_REF_SCHEME,
        //       weaveKind: 'object',
        //       entity: props.call.entity,
        //       project: props.call.project,
        //       objectId: mapping.object_id,
        //       versionHash: mapping.digest,
        //       path: '',
        //     })
        //   : undefined;
        return {
          actionRef: actionWithConfigRefUri,
          actionDef: actionWithConfig.val,
          // mapping: mapping?.val,
          // mappingRef,
          runCount: 0,
          lastResult: {},
        };
      }) ?? []
    );
  }, [actionWithConfigs, props.call.entity, props.call.project]);
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

  // console.log({verifiedActions, verifiedActionFeedbacks});

  const getFeedbackForAction = (actionRef: string) => {
    return verifiedActionFeedbacks.filter(
      feedback => feedback.action_ref === actionRef
    );
  };

  const getClient = useGetTraceServerClientContext();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedAction, setSelectedAction] = useState<CallActionRow | null>(null);
  const [newMapping, setNewMapping] = useState<Partial<ActionOpMapping>>({
    name: '',
    op_name: artifactName || '',
    op_digest: artifactVersion || '*',
    input_mapping: {},
  });

  const handleCreateMapping = (action: CallActionRow) => {
    setSelectedAction(action);
    setNewMapping(prev => ({
      ...prev,
      action: action.actionRef,
    }));
    setIsModalOpen(true);
  };

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
            {/* <th>Mapping</th> */}
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
                              action_ref: action.actionRef,
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
        aria-labelledby="create-action-mapping-modal"
      >
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 400,
            bgcolor: 'background.paper',
            boxShadow: 24,
            p: 4,
            borderRadius: 2,
            display: 'flex',
            flexDirection: 'column',
            maxHeight: '80vh',
            overflowY: 'auto',
          }}
        >
          <Typography id="create-action-mapping-modal" variant="h6" component="h2" gutterBottom>
            Create Action Mapping
          </Typography>
          <TextField
            fullWidth
            label="Name"
            value={newMapping.name}
            onChange={(e) => setNewMapping(prev => ({...prev, name: e.target.value}))}
            margin="normal"
          />
          {/* <TextField
            fullWidth
            label="Op Name"
            value={newMapping.op_name}
            onChange={(e) => setNewMapping(prev => ({...prev, op_name: e.target.value}))}
            margin="normal"
          />
          <TextField
            fullWidth
            label="Op Digest"
            value={newMapping.op_digest}
            onChange={(e) => setNewMapping(prev => ({...prev, op_digest: e.target.value}))}
            margin="normal"
          /> */}
          <Typography variant="subtitle1" gutterBottom>
            Input Mapping
          </Typography>
          <DynamicConfigForm
            configSchema={z.record(z.string())}
            config={newMapping.input_mapping || {}}
            setConfig={(newInputMapping) => setNewMapping(prev => ({...prev, input_mapping: newInputMapping}))}
          />
          <Box sx={{display: 'flex', justifyContent: 'flex-end', mt: 2}}>
            <Button onClick={() => setIsModalOpen(false)} sx={{mr: 1}}>
              Cancel
            </Button>
            <Button onClick={handleSaveMapping} variant="contained" color="primary">
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
