import {Box} from '@mui/material';
import {GridColDef, GridRowHeightParams} from '@mui/x-data-grid-pro';
import {isWeaveObjectRef, parseRefMaybe} from '@wandb/weave/react';
import React from 'react';

import {Timestamp} from '../../../../Timestamp';
import {UserLink} from '../../../../UserLink';
import {CellValue} from '../../Browse2/CellValue';
import {CallRefLink} from '../pages/common/Links';
import {Feedback} from '../pages/wfReactInterface/traceServerClientTypes';
import {SmallRef} from '../smallRef/SmallRef';
import {StyledDataGrid} from '../StyledDataGrid';
import {FeedbackGridActions} from './FeedbackGridActions';

type FeedbackGridInnerProps = {
  feedback: Feedback[];
  currentViewerId: string | null;
  showAnnotationName?: boolean;
};

export const ScoresFeedbackGridInner = ({
  feedback,
  currentViewerId,
  showAnnotationName,
}: FeedbackGridInnerProps) => {
  /**
   * This component is very similar to `FeedbackGridInner`, but it only shows scores.
   * While some of the code is duplicated, it is kept separate to make it easier
   * to modify in the future.
   */
  const columns: Array<GridColDef<Feedback>> = [
    {
      field: 'runnable_ref',
      headerName: 'Scorer',
      display: 'flex',
      flex: 1,
      renderCell: params => {
        const runnable_ref = params.row.runnable_ref;
        if (!runnable_ref) {
          return null;
        }
        const objRef = parseRefMaybe(runnable_ref);
        if (!objRef) {
          return null;
        }
        return (
          <div className="overflow-hidden">
            <SmallRef objRef={objRef} />
          </div>
        );
      },
    },
    {
      field: 'payload',
      headerName: 'Score',
      sortable: false,
      flex: 1,
      renderCell: params => {
        const value = params.row.payload.output;
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
      field: 'call_ref',
      headerName: 'Score Call',
      display: 'flex',
      renderCell: params => {
        const call_ref = params.row.call_ref;
        if (!call_ref) {
          return null;
        }
        const objRef = parseRefMaybe(call_ref);
        if (!objRef) {
          return null;
        }
        if (!isWeaveObjectRef(objRef)) {
          return null;
        }
        return (
          <div className="overflow-hidden">
            <CallRefLink callRef={objRef} />
          </div>
        );
      },
    },
    {
      field: 'created_at',
      headerName: 'Timestamp',
      minWidth: 105,
      width: 105,
      renderCell: params => (
        <Timestamp value={params.row.created_at} format="relative" />
      ),
    },
    {
      field: 'wb_user_id',
      headerName: 'Creator',
      minWidth: 150,
      width: 150,
      // Might be confusing to enable as-is, because the user sees name /
      // email but the underlying data is userId.
      filterable: false,
      sortable: false,
      resizable: false,
      disableColumnMenu: true,
      renderCell: params => {
        if (
          params.row.creator &&
          params.row.creator !== params.row.wb_user_id
        ) {
          return params.row.creator;
        }
        return <UserLink userId={params.row.wb_user_id} includeName />;
      },
    },
    {
      field: 'actions',
      headerName: '',
      width: 36,
      minWidth: 36,
      filterable: false,
      sortable: false,
      resizable: false,
      disableColumnMenu: true,
      display: 'flex',
      renderCell: params => {
        const projectId = params.row.project_id;
        const feedbackId = params.row.id;
        const creatorId = params.row.wb_user_id;
        if (!currentViewerId || creatorId !== currentViewerId) {
          return null;
        }
        return (
          <FeedbackGridActions
            projectId={projectId}
            feedbackId={feedbackId}
            feedbackType="score"
          />
        );
      },
    },
  ];
  const rows = feedback;
  return (
    <StyledDataGrid
      autosizeOnMount
      // Start Column Menu
      // ColumnMenu is only needed when we have other actions
      // such as filtering.
      disableColumnMenu={true}
      // We don't have enough columns to justify filtering
      disableColumnFilter={true}
      disableMultipleColumnsFiltering={true}
      // ColumnPinning seems to be required in DataGridPro, else it crashes.
      disableColumnPinning={false}
      // We don't have enough columns to justify re-ordering
      disableColumnReorder={true}
      // The columns are fairly simple, so we don't need to resize them.
      disableColumnResize={false}
      // We don't have enough columns to justify hiding some of them.
      disableColumnSelector={true}
      // We don't have enough columns to justify sorting by multiple columns.
      disableMultipleColumnsSorting={true}
      // End Column Menu
      rows={rows}
      initialState={{
        sorting: {
          sortModel: [{field: 'created_at', sort: 'desc'}],
        },
      }}
      columnHeaderHeight={40}
      getRowHeight={(params: GridRowHeightParams) => {
        if (isWandbFeedbackType(params.model.feedback_type)) {
          return 38;
        }
        return 'auto';
      }}
      columns={columns}
      disableRowSelectionOnClick
    />
  );
};

const isWandbFeedbackType = (feedbackType: string) =>
  feedbackType.startsWith('wandb.');
