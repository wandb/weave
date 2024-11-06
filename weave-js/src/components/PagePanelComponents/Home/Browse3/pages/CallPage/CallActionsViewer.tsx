import {Button} from '@wandb/weave/components/Button/Button';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import {parseRef} from '@wandb/weave/react';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useCallback, useMemo, useState} from 'react';
import {z} from 'zod';

import {CellValue} from '../../../Browse2/CellValue';
import {NotApplicable} from '../../../Browse2/NotApplicable';
import {ActionDefinitionType} from '../../collections/actionCollection';
import {useCollectionObjects} from '../../collections/getCollectionObjects';
import {StyledDataGrid} from '../../StyledDataGrid'; // Import the StyledDataGrid component
import {WEAVE_REF_SCHEME} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {Feedback} from '../wfReactInterface/traceServerClientTypes';
import {
  convertISOToDate,
  projectIdFromParts,
} from '../wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

type CallActionRow = {
  actionRef: string;
  actionDef: ActionDefinitionType;
  runCount: number;
  lastResult?: unknown;
  lastRanAt?: Date;
};
// New RunButton component
const RunButton: React.FC<{
  actionRef: string;
  callId: string;
  entity: string;
  project: string;
  refetchFeedback: () => void;
  getClient: () => any;
}> = ({actionRef, callId, entity, project, refetchFeedback, getClient}) => {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRunClick = async () => {
    setIsRunning(true);
    setError(null);
    try {
      await getClient().actionsExecuteBatch({
        project_id: projectIdFromParts({entity, project}),
        call_ids: [callId],
        configured_action_ref: actionRef,
      });
      refetchFeedback();
    } catch (err) {
      setError('An error occurred while running the action.');
    } finally {
      setIsRunning(false);
    }
  };

  if (error) {
    return (
      <Button variant="destructive" onClick={handleRunClick} disabled>
        Error
      </Button>
    );
  }

  return (
    <div>
      <Button variant="secondary" onClick={handleRunClick} disabled={isRunning}>
        {isRunning ? 'Running...' : 'Run'}
      </Button>
    </div>
  );
};

export const CallActionsViewer: React.FC<{
  call: CallSchema;
}> = props => {
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

  const ActionDefinitions = useCollectionObjects('ActionDefinition', {
    project_id: projectIdFromParts({
      entity: props.call.entity,
      project: props.call.project,
    }),
    filter: {latest_only: true},
  }).sort((a, b) => a.val.name.localeCompare(b.val.name));
  const verifiedActionFeedbacks: Array<{
    data: MachineScoreFeedbackPayloadType;
    feedbackRaw: Feedback;
  }> = useMemo(() => {
    return (feedbackQuery.result ?? [])
      .map(feedback => {
        const res = MachineScoreFeedbackPayloadSchema.safeParse(
          feedback.payload
        );
        return {res, feedbackRaw: feedback};
      })
      .filter(result => result.res.success)
      .map(result => ({
        data: result.res.data,
        feedbackRaw: result.feedbackRaw,
      })) as Array<{
      data: MachineScoreFeedbackPayloadType;
      feedbackRaw: Feedback;
    }>;
  }, [feedbackQuery.result]);

  const getFeedbackForAction = useCallback(
    (actionRef: string) => {
      return verifiedActionFeedbacks.filter(
        feedback => feedback.data.runnable_ref === actionRef
      );
    },
    [verifiedActionFeedbacks]
  );

  const getClient = useGetTraceServerClientContext();

  const allCallActions: CallActionRow[] = useMemo(() => {
    return (
      ActionDefinitions?.map(ActionDefinition => {
        const ActionDefinitionRefUri = objectVersionKeyToRefUri({
          scheme: WEAVE_REF_SCHEME,
          weaveKind: 'object',
          entity: props.call.entity,
          project: props.call.project,
          objectId: ActionDefinition.object_id,
          versionHash: ActionDefinition.digest,
          path: '',
        });
        const feedbacks = getFeedbackForAction(ActionDefinitionRefUri);
        const selectedFeedback =
          feedbacks.length > 0 ? feedbacks[0] : undefined;
        return {
          actionRef: ActionDefinitionRefUri,
          actionDef: ActionDefinition.val,
          runCount: feedbacks.length,
          lastRanAt: selectedFeedback
            ? convertISOToDate(selectedFeedback.feedbackRaw.created_at + 'Z')
            : undefined,
          lastResult: selectedFeedback
            ? getValueFromMachineScoreFeedbackPayload(selectedFeedback.data)
            : undefined,
        };
      }) ?? []
    );
  }, [
    ActionDefinitions,
    getFeedbackForAction,
    props.call.entity,
    props.call.project,
  ]);

  const columns = [
    {field: 'action', headerName: 'Action', flex: 1},
    {field: 'runCount', headerName: 'Run Count', flex: 1},
    {
      field: 'lastResult',
      headerName: 'Last Result',
      flex: 1,
      renderCell: (params: any) => {
        const value = params.row.lastResult;
        if (value == null) {
          return <NotApplicable />;
        }
        return <CellValue value={value} isExpanded={false} />;
      },
    },
    {
      field: 'lastRanAt',
      headerName: 'Last Ran At',
      flex: 1,
      renderCell: (params: any) => {
        const value = params.row.lastRanAt
          ? params.row.lastRanAt.getTime() / 1000
          : undefined;
        if (value == null) {
          return <NotApplicable />;
        }
        return <Timestamp value={value} format="relative" />;
      },
    },
    {
      field: 'run',
      headerName: 'Run',
      flex: 1,
      renderCell: (params: any) => (
        <RunButton
          actionRef={params.row.actionRef}
          callId={props.call.callId}
          entity={props.call.entity}
          project={props.call.project}
          refetchFeedback={feedbackQuery.refetch}
          getClient={getClient}
        />
      ),
    },
  ];

  const rows = allCallActions.map((action, index) => ({
    id: index,
    action: action.actionDef.name,
    runCount: action.runCount,
    lastResult: action.lastResult,
    lastRanAt: action.lastRanAt,
    actionRef: action.actionRef,
  }));
  return (
    <>
      <StyledDataGrid
        // Start Column Menu
        // ColumnMenu is needed to support pinning and column visibility
        disableColumnMenu={true}
        // ColumnFilter is definitely useful
        disableColumnFilter={true}
        disableMultipleColumnsFiltering={true}
        // ColumnPinning seems to be required in DataGridPro, else it crashes.
        // However, in this case it is also useful.
        disableColumnPinning={true}
        // ColumnReorder is definitely useful
        // TODO (Tim): This needs to be managed externally (making column
        // ordering a controlled property) This is a "regression" from the calls
        // table refactor
        disableColumnReorder={true}
        // ColumnResize is definitely useful
        disableColumnResize={false}
        // ColumnSelector is definitely useful
        disableColumnSelector={true}
        disableMultipleColumnsSorting={true}
        // End Column Menu
        columnHeaderHeight={40}
        rows={rows}
        columns={columns}
        autoHeight
        disableRowSelectionOnClick
        sx={{
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'inherit',
          },
        }}
      />
    </>
  );
};

const MachineScoreFeedbackPayloadSchema = z.object({
  // _type: z.literal("ActionFeedback"),
  runnable_ref: z.string(),
  call_ref: z.string().optional(),
  trigger_ref: z.string().optional(),
  value: z.record(z.string(), z.record(z.string(), z.boolean())),
});

type MachineScoreFeedbackPayloadType = z.infer<
  typeof MachineScoreFeedbackPayloadSchema
>;

const getValueFromMachineScoreFeedbackPayload = (
  payload: MachineScoreFeedbackPayloadType
) => {
  const ref = parseRef(payload.runnable_ref);
  const name = ref.artifactName;
  const digest = ref.artifactVersion;
  return payload.value[name][digest];
};
