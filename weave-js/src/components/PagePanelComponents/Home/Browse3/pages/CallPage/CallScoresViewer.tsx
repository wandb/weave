import {Box} from '@material-ui/core';
import {GridColDef} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button/Button';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import {parseRef} from '@wandb/weave/react';
import {makeRefCall} from '@wandb/weave/util/refs';
import _ from 'lodash';
import React, {useMemo, useState} from 'react';

import {CellValue} from '../../../Browse2/CellValue';
import {NotApplicable} from '../../../Browse2/NotApplicable';
import {SmallRef} from '../../../Browse2/SmallRef';
import {StyledDataGrid} from '../../StyledDataGrid'; // Import the StyledDataGrid component
import {TraceObjSchemaForBaseObjectClass, useBaseObjectInstances} from '../wfReactInterface/baseObjectClassQuery';
import {WEAVE_REF_SCHEME} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {Feedback} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

const RUNNABLE_REF_PREFIX = 'wandb.runnable';


// New RunButton component
const RunButton: React.FC<{
  actionRef: string;
  callId: string;
  entity: string;
  project: string;
  refetchFeedback: () => void;
}> = ({actionRef, callId, entity, project, refetchFeedback}) => {
  const getClient = useGetTraceServerClientContext();

  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRunClick = async () => {
    setIsRunning(true);
    setError(null);
    try {
      await getClient().actionsExecuteBatch({
        project_id: projectIdFromParts({entity, project}),
        call_ids: [callId],
        action_ref: actionRef,
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


const useLatestActionDefinitionsForCall = (call: CallSchema) => {
  const actionSpecs = (
    useBaseObjectInstances('ActionSpec', {
      project_id: projectIdFromParts({
        entity: call.entity,
        project: call.project,
      }),
      filter: {latest_only: true},
    }).result ?? []
  ).sort((a, b) => (a.val.name ?? '').localeCompare(b.val.name ?? ''));
  return actionSpecs;
};

const useRunnableFeedbacksForCall = (call: CallSchema) => {
  const {useFeedback} = useWFHooks();
  const weaveRef = makeRefCall(
    call.entity,
    call.project,
    call.callId
  );
  const feedbackQuery = useFeedback({
    entity: call.entity,
    project: call.project,
    weaveRef,
  });

  const runnableFeedbacks: Feedback[] = useMemo(() => {
    return (feedbackQuery.result ?? []).filter(
      f =>
        f.feedback_type?.startsWith(RUNNABLE_REF_PREFIX) &&
        f.runnable_ref !== null
    );
  }, [feedbackQuery.result]);

  return {runnableFeedbacks, refetchFeedback: feedbackQuery.refetch};
};

const useRunnableFeedbackTypeToLatestActionRef = (call: CallSchema, actionSpecs:  Array<TraceObjSchemaForBaseObjectClass<'ActionSpec'>>): Record<string, string> => {
  return useMemo(() => {
    return _.fromPairs(
      actionSpecs.map(actionSpec => {
        return [
          RUNNABLE_REF_PREFIX + '.' + actionSpec.object_id,
          objectVersionKeyToRefUri({
            scheme: WEAVE_REF_SCHEME,
            weaveKind: 'object',
            entity: call.entity,
            project: call.project,
            objectId: actionSpec.object_id,
            versionHash: actionSpec.digest,
            path: '',
          }),
        ];
      })
    );
  }, [actionSpecs, call.entity, call.project]);
}



export const CallScoresViewer: React.FC<{
  call: CallSchema;
}> = props => {
  const actionSpecs = useLatestActionDefinitionsForCall(props.call);
  const {runnableFeedbacks, refetchFeedback} = useRunnableFeedbacksForCall(props.call);
  const runnableFeedbackTypeToLatestActionRef = useRunnableFeedbackTypeToLatestActionRef(props.call, actionSpecs);

  

  const scoredRows = useMemo(() => {
    return Object.entries(
      _.groupBy(runnableFeedbacks, f => f.feedback_type)
    ).map(([runnableRef, fs]) => {
      const val = _.reverse(_.sortBy(fs, 'created_at'))[0];
      return {
        id: val.feedback_type,
        feedback: val,
        runCount: fs.length,
      };
    });
  }, [runnableFeedbacks]);

  const rows = useMemo(() => {
    const additionalRows = actionSpecs
      .map(actionSpec => {
        return {
          id: RUNNABLE_REF_PREFIX + '.' + actionSpec.object_id,
          feedback: null,
          runCount: 0,
        };
      })
      .filter(row => !scoredRows.some(r => r.id === row.id));
    return _.sortBy([...scoredRows, ...additionalRows], s => s.id);
  }, [actionSpecs, scoredRows]);

  const columns: Array<GridColDef<(typeof rows)[number]>> = [
    {
      field: 'scorer',
      headerName: 'Scorer',
      width: 150,
      renderCell: params => {
        return params.row.id.slice(RUNNABLE_REF_PREFIX.length + 1);
      },
    },
    {
      field: 'runnable_ref',
      headerName: 'Logic',
      width: 60,
      renderCell: params => {
        if (params.row.feedback == null) {
          return null;
        }
        return (
          <Box
            sx={{
              width: '100%',
              display: 'flex',
              justifyContent: 'center',
              height: '100%',
              lineHeight: '20px',
              alignItems: 'center',
            }}>
            <SmallRef
              objRef={parseRef(params.row.feedback.runnable_ref ?? '')}
              iconOnly={true}
            />
          </Box>
        );
      },
    },
    {field: 'runCount', headerName: 'Runs', width: 55},
    {
      field: 'lastResult',
      headerName: 'Last Result',
      flex: 1,
      renderCell: params => {
        if (params.row.feedback == null) {
          return null;
        }
        const value = params.row.feedback.payload.output;
        if (value == null) {
          return <NotApplicable />;
        }
        return (
          <Box
            sx={{
              width: '100%',
              display: 'flex',
              height: '100%',
              lineHeight: '20px',
              alignItems: 'center',
            }}>
            <CellValue value={value} isExpanded={false} />
          </Box>
        );
      },
    },
    {
      field: 'lastRanAt',
      headerName: 'Last Ran At',
      width: 100,
      renderCell: params => {
        if (params.row.feedback == null) {
          return null;
        }
        const createdAt = new Date(params.row.feedback.created_at + 'Z');
        const value = createdAt ? createdAt.getTime() / 1000 : undefined;
        if (value == null) {
          return <NotApplicable />;
        }
        return <Timestamp value={value} format="relative" />;
      },
    },
    {
      field: 'run',
      headerName: '',
      width: 70,
      renderCell: params => {
        const actionRef = runnableFeedbackTypeToLatestActionRef[params.row.id];
        return actionRef ? (
          <RunButton
            actionRef={actionRef}
            callId={props.call.callId}
            entity={props.call.entity}
            project={props.call.project}
            refetchFeedback={refetchFeedback}
          />
        ) : null;
      },
    },
  ];

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
