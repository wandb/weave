import { Button } from '@wandb/weave/components/Button/Button';
import {makeRefCall} from '@wandb/weave/util/refs';
import React, {useCallback, useMemo, useState} from 'react';
import {z} from 'zod';

import {
  ConfiguredAction,
} from '../../collections/actionCollection';
import {useCollectionObjects} from '../../collections/getCollectionObjects';
import {StyledDataGrid} from '../../StyledDataGrid'; // Import the StyledDataGrid component
import {WEAVE_REF_SCHEME} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {convertISOToDate, projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import { Feedback } from '../wfReactInterface/traceServerClientTypes';
import { Timestamp } from '@wandb/weave/components/Timestamp';
import { NotApplicable } from '../../../Browse2/NotApplicable';
import { ValueView } from './ValueView';
import { CellValue } from '../../../Browse2/CellValue';

type CallActionRow = {
  actionRef: string;
  actionDef: ConfiguredAction;
  runCount: number;
  lastResult?: Record<string, unknown>;
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

  const handleRunClick = async () => {
    setIsRunning(true);
    try {
      await getClient().executeBatchAction({
        project_id: projectIdFromParts({entity, project}),
        call_ids: [callId],
        configured_action_ref: actionRef,
      });
      refetchFeedback();
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <Button variant="secondary" onClick={handleRunClick} disabled={isRunning}>
      {isRunning ? 'Running...' : 'Run'}
    </Button>
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

  const configuredActions = useCollectionObjects('ConfiguredAction', {
    project_id: projectIdFromParts({
      entity: props.call.entity,
      project: props.call.project,
    }),
    filter: {latest_only: true},
  }).sort((a, b) => a.val.name.localeCompare(b.val.name));


  const verifiedActionFeedbacks: {data: ActionFeedback, feedbackRaw: Feedback }[] = useMemo(() => {
    return (feedbackQuery.result ?? [])
      .map(feedback => {
        const res = ActionFeedbackZ.safeParse(feedback.payload);
        return {res, feedbackRaw: feedback};
      })
      .filter(result => result.res.success)
      .map(result => ({data: result.res.data, feedbackRaw: result.feedbackRaw})) as {data: ActionFeedback, feedbackRaw: Feedback}[];
  }, [feedbackQuery.result]);

  const getFeedbackForAction = useCallback((actionRef: string) => {
    return verifiedActionFeedbacks.filter(
      feedback => feedback.data.configured_action_ref === actionRef
    );
  }, [verifiedActionFeedbacks]);

  const getClient = useGetTraceServerClientContext();

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
        const selectedFeedback = feedbacks.length > 0 ? feedbacks[0] : undefined;
        return {
          actionRef: configuredActionRefUri,
          actionDef: configuredAction.val,
          runCount: feedbacks.length,
          lastRanAt: selectedFeedback ? convertISOToDate(selectedFeedback.feedbackRaw.created_at + "Z") : undefined,
          lastResult: selectedFeedback?.data.output,
        };
      }) ?? []
    );
  }, [configuredActions, getFeedbackForAction, props.call.entity, props.call.project]);

  const columns = [
    {field: 'action', headerName: 'Action', flex: 1},
    {field: 'runCount', headerName: 'Run Count', flex: 1},
    {field: 'lastResult', headerName: 'Last Result', flex: 1, renderCell: (params: any) => {
      const value = params.row.lastResult;
      if (value == null) {
        return <NotApplicable />
      }
      return <CellValue value={value} isExpanded={false} />
    }},
    {field: 'lastRanAt', headerName: 'Last Ran At', flex: 1, renderCell: (params: any) => {
      const value = params.row.lastRanAt ? params.row.lastRanAt.getTime() / 1000 : undefined;
      if (value == null) {
        return <NotApplicable />
      }
      return <Timestamp value={value} format="relative" />
    }},
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

const ActionFeedbackZ = z.object({
  // _type: z.literal("ActionFeedback"),
  configured_action_ref: z.string(),
  output: z.record(z.string(), z.unknown()),
});

type ActionFeedback = z.infer<typeof ActionFeedbackZ>;
