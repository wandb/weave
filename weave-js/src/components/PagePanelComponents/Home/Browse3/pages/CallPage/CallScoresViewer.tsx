import {Box} from '@material-ui/core';
import {GridColDef} from '@mui/x-data-grid-pro';
import {Button} from '@wandb/weave/components/Button/Button';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import {parseRef} from '@wandb/weave/react';
import {makeRefCall} from '@wandb/weave/util/refs';
import _ from 'lodash';
import React, {useMemo, useState} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../../Browse2/browse2Util';
import {CellValue} from '../../../Browse2/CellValue';
import {NotApplicable} from '../../../Browse2/NotApplicable';
import {SmallRef} from '../../../Browse2/SmallRef';
import {StyledDataGrid} from '../../StyledDataGrid'; // Import the StyledDataGrid component
import {WEAVE_REF_SCHEME} from '../wfReactInterface/constants';
import {useWFHooks} from '../wfReactInterface/context';
import {
  TraceObjSchemaForBaseObjectClass,
  useBaseObjectInstances,
} from '../wfReactInterface/objectClassQuery';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {Feedback} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

export const RUNNABLE_FEEDBACK_TYPE_PREFIX = 'wandb.runnable';

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
  const weaveRef = makeRefCall(call.entity, call.project, call.callId);
  const feedbackQuery = useFeedback({
    entity: call.entity,
    project: call.project,
    weaveRef,
  });

  const runnableFeedbacks: Feedback[] = useMemo(() => {
    return (feedbackQuery.result ?? []).filter(
      f =>
        f.feedback_type?.startsWith(RUNNABLE_FEEDBACK_TYPE_PREFIX) &&
        f.runnable_ref !== null
    );
  }, [feedbackQuery.result]);

  return {runnableFeedbacks, refetchFeedback: feedbackQuery.refetch};
};

const useRunnableFeedbackTypeToLatestActionRef = (
  call: CallSchema,
  actionSpecs: Array<TraceObjSchemaForBaseObjectClass<'ActionSpec'>>
): Record<string, string> => {
  return useMemo(() => {
    return _.fromPairs(
      actionSpecs.map(actionSpec => {
        return [
          RUNNABLE_FEEDBACK_TYPE_PREFIX + '.' + actionSpec.object_id,
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
};

type GroupedRowType = {
  id: string;
  displayName: string;
  runnableActionRef?: string;
  feedback?: Feedback;
  runCount: number;
};

const useTableRowsForRunnableFeedbacks = (
  actionSpecs: Array<TraceObjSchemaForBaseObjectClass<'ActionSpec'>>,
  runnableFeedbacks: Feedback[],
  runnableFeedbackTypeToLatestActionRef: Record<string, string>
): GroupedRowType[] => {
  const rows = useMemo(() => {
    const scoredRows = Object.entries(
      _.groupBy(runnableFeedbacks, f => f.feedback_type)
    ).map(([feedbackType, fs]) => {
      const val = _.reverse(_.sortBy(fs, 'created_at'))[0];
      return {
        id: feedbackType,
        displayName: feedbackType.slice(
          RUNNABLE_FEEDBACK_TYPE_PREFIX.length + 1
        ),
        runnableActionRef:
          runnableFeedbackTypeToLatestActionRef[val.feedback_type],
        feedback: val,
        runCount: fs.length,
      };
    });
    const additionalRows = actionSpecs
      .map(actionSpec => {
        const feedbackType =
          RUNNABLE_FEEDBACK_TYPE_PREFIX + '.' + actionSpec.object_id;
        return {
          id: feedbackType,
          runnableActionRef:
            runnableFeedbackTypeToLatestActionRef[feedbackType],
          displayName: actionSpec.object_id,
          runCount: 0,
        };
      })
      .filter(row => !scoredRows.some(r => r.id === row.id));
    return _.sortBy([...scoredRows, ...additionalRows], s => s.id);
  }, [actionSpecs, runnableFeedbackTypeToLatestActionRef, runnableFeedbacks]);

  return rows;
};

type FlattenedRowType = {
  id: string;
  displayName: string;
  runnableActionRef?: string;
  feedback?: Feedback;
  runCount: number;
  feedbackKey?: string;
  feedbackValue?: any;
};

const useFlattenedRows = (rows: GroupedRowType[]): FlattenedRowType[] => {
  return useMemo(() => {
    return rows.flatMap(r => {
      if (r.feedback == null) {
        return [r];
      }
      const feedback = flattenObjectPreservingWeaveTypes(r.feedback.payload);
      return Object.entries(feedback).map(([k, v]) => ({
        ...r,
        id: r.id + '::' + k,
        feedbackKey: k,
        feedbackValue: v,
      }));
    });
  }, [rows]);
};

export const CallScoresViewer: React.FC<{
  call: CallSchema;
}> = props => {
  const actionSpecs = useLatestActionDefinitionsForCall(props.call);
  const {runnableFeedbacks, refetchFeedback} = useRunnableFeedbacksForCall(
    props.call
  );
  const runnableFeedbackTypeToLatestActionRef =
    useRunnableFeedbackTypeToLatestActionRef(props.call, actionSpecs);
  const rows = useTableRowsForRunnableFeedbacks(
    actionSpecs,
    runnableFeedbacks,
    runnableFeedbackTypeToLatestActionRef
  );
  const flattenedRows = useFlattenedRows(rows);

  const columns: Array<GridColDef<FlattenedRowType>> = [
    {
      field: 'scorer',
      headerName: 'Scorer',
      width: 150,
      rowSpanValueGetter: (value, row) => row.displayName,
      renderCell: params => {
        const refToUse =
          params.row.runnableActionRef || params.row.feedback?.runnable_ref;
        const title = params.row.displayName;
        return (
          <Box
            sx={{
              width: '100%',
              display: 'flex',
              height: '100%',
              lineHeight: '20px',
              alignItems: 'flex-start',
              marginTop: '16px',
            }}>
            {' '}
            {refToUse && (
              <Box>
                <SmallRef objRef={parseRef(refToUse)} iconOnly={true} />
              </Box>
            )}
            <Box>{title}</Box>
          </Box>
        );
      },
    },
    {
      field: 'runCount',
      headerName: 'Runs',
      width: 55,
      rowSpanValueGetter: (value, row) => row.displayName,
    },
    {
      field: 'lastRanAt',
      headerName: 'Last Ran At',
      width: 100,
      rowSpanValueGetter: (value, row) => row.displayName,
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
      field: 'lastResultKey',
      headerName: 'Key',
      width: 100,
      renderCell: params => {
        let key = params.row.feedbackKey;
        // Handle cases where the output is a primitive value vs a nested object
        if (key?.startsWith('output.')) {
          key = key.slice(7);
        }
        return key;
      },
    },
    {
      field: 'lastResultValue',
      headerName: 'Value',
      flex: 1,
      renderCell: params => {
        const value = params.row.feedbackValue;
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
            <CellValue value={value} />
          </Box>
        );
      },
    },
    {
      field: 'run',
      headerName: '',
      width: 75,
      rowSpanValueGetter: (value, row) => row.displayName,
      renderCell: params => {
        const actionRef = params.row.runnableActionRef;
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
        disableColumnSorting={true}
        // End Column Menu
        columnHeaderHeight={40}
        rows={flattenedRows}
        columns={columns}
        autoHeight
        disableRowSelectionOnClick
        unstable_rowSpanning={true}
        sx={{
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'inherit',
          },
        }}
      />
    </>
  );
};

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
      <Button
        variant="destructive"
        onClick={handleRunClick}
        disabled
        style={{width: '55px'}}>
        Error
      </Button>
    );
  }

  return (
    <div>
      <Button
        variant="secondary"
        onClick={handleRunClick}
        disabled={isRunning}
        style={{width: '55px'}}>
        {isRunning ? '...' : 'Run'}
      </Button>
    </div>
  );
};
