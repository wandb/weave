import {
  GridColDef,
  GridRenderCellParams,
  GridRowHeightParams,
} from '@mui/x-data-grid-pro';
import React from 'react';

import {Timestamp} from '../../../../Timestamp';
import {UserLink} from '../../../../UserLink';
import {CellValueString} from '../../Browse2/CellValueString';
import {CopyableId} from '../pages/common/Id';
import {Feedback} from '../pages/wfReactInterface/traceServerClientTypes';
import {StyledDataGrid} from '../StyledDataGrid';
import {FeedbackGridActions} from './FeedbackGridActions';
import {FeedbackTypeChip} from './FeedbackTypeChip';
import {
  getHumanAnnotationNameFromFeedbackType,
  isHumanAnnotationType,
} from './StructuredFeedback/humanAnnotationTypes';

type FeedbackGridInnerProps = {
  feedback: Feedback[];
  currentViewerId: string | null;
  showAnnotationName?: boolean;
};

export const FeedbackGridInner = ({
  feedback,
  currentViewerId,
  showAnnotationName,
}: FeedbackGridInnerProps) => {
  const columns: GridColDef[] = [
    {
      field: 'feedback_type',
      headerName: 'Type',
      display: 'flex',
      renderCell: params => (
        <div className="overflow-hidden">
          <FeedbackTypeChip feedbackType={params.row.feedback_type} />
        </div>
      ),
    },
    ...(showAnnotationName
      ? [
          {
            field: 'annotation_name',
            headerName: 'Name',
            flex: 1,
            renderCell: (params: GridRenderCellParams) => {
              const feedbackType = params.row.feedback_type;
              const annotationName = isHumanAnnotationType(feedbackType)
                ? getHumanAnnotationNameFromFeedbackType(feedbackType)
                : null;
              if (!annotationName) {
                return null;
              }
              return <CellValueString value={annotationName} />;
            },
          },
        ]
      : []),
    {
      field: 'payload',
      headerName: 'Feedback',
      sortable: false,
      flex: 1,
      renderCell: params => {
        if (params.row.feedback_type === 'wandb.note.1') {
          return <CellValueString value={params.row.payload.note} />;
        }
        if (params.row.feedback_type === 'wandb.reaction.1') {
          return (
            <span className="night-aware">{params.row.payload.emoji}</span>
          );
        }
        if (isHumanAnnotationType(params.row.feedback_type)) {
          if (typeof params.row.payload.value === 'string') {
            return <CellValueString value={params.row.payload.value} />;
          }
          return (
            <CellValueString
              value={JSON.stringify(params.row.payload.value ?? null)}
            />
          );
        }
        return <CellValueString value={JSON.stringify(params.row.payload)} />;
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
      field: 'id',
      headerName: 'ID',
      width: 48,
      minWidth: 48,
      display: 'flex',
      renderCell: params => <CopyableId id={params.row.id} type="Feedback" />,
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
          <FeedbackGridActions projectId={projectId} feedbackId={feedbackId} />
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
