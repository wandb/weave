import {
  GridColDef,
  GridColumnVisibilityModel,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumnFields,
  GridSortModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {FC, useCallback, useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {TailwindContents} from '../../../../../Tailwind';
import {Timestamp} from '../../../../../Timestamp';
import {useEntityProject, useWeaveflowRouteContext} from '../../context';
import {FilterPanel} from '../../filters/FilterPanel';
import {StyledDataGrid} from '../../StyledDataGrid';
import {ColumnInfo} from '../../types';
import {PaginationButtons, RefreshButton} from '../CallsPage/CallsTableButtons';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {StatusChip} from '../common/StatusChip';
import {
  convertISOToDate,
  useThreadsQuery,
} from '../wfReactInterface/tsDataModelHooks';
import {ThreadsExportSelector} from './ThreadsExportSelector';

// Convert GridSortModel to backend format
const getSortBy = (gridSort: GridSortModel) => {
  return gridSort.map(sort => {
    return {
      field: sort.field,
      direction: sort.sort ?? 'asc',
    };
  });
};

// Convert GridFilterModel to backend datetime filters
// Only supports 'last_updated' field with date operators
const convertFilterModelToDatetimeFilters = (
  filterModel: GridFilterModel
): {after_datetime?: string; before_datetime?: string} => {
  const filters: {after_datetime?: string; before_datetime?: string} = {};

  for (const item of filterModel.items) {
    if (item.field === 'started_at' && item.value) {
      if (item.operator === '(date): after') {
        filters.after_datetime = item.value;
      } else if (item.operator === '(date): before') {
        filters.before_datetime = item.value;
      }
    }
  }

  return filters;
};

export const ThreadsTable: FC<{
  columnVisibilityModel: GridColumnVisibilityModel;
  setColumnVisibilityModel: (newModel: GridColumnVisibilityModel) => void;

  pinModel: GridPinnedColumnFields;
  setPinModel: (newModel: GridPinnedColumnFields) => void;

  filterModel: GridFilterModel;
  setFilterModel: (newModel: GridFilterModel) => void;

  sortModel: GridSortModel;
  setSortModel: (newModel: GridSortModel) => void;

  paginationModel: GridPaginationModel;
  setPaginationModel: (newModel: GridPaginationModel) => void;
}> = ({
  columnVisibilityModel,
  setColumnVisibilityModel,
  pinModel,
  setPinModel,
  filterModel,
  setFilterModel,
  sortModel,
  setSortModel,
  paginationModel,
  setPaginationModel,
}) => {
  const {entity, project} = useEntityProject();
  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();

  // Setup Ref to underlying table
  const apiRef = useGridApiRef();

  // Note: All models are now required props, no need for fallbacks

  // Convert sort model to backend format
  const backendSortBy = useMemo(() => {
    return getSortBy(sortModel);
  }, [sortModel]);

  // Convert filter model to backend datetime filters
  const datetimeFilters = useMemo(() => {
    return convertFilterModelToDatetimeFilters(filterModel);
  }, [filterModel]);

  // Store the query params
  const queryParams = useMemo(() => {
    const effectiveOffset = paginationModel.page * paginationModel.pageSize;
    const effectiveLimit = paginationModel.pageSize;

    const effectiveAfterDatetime = datetimeFilters.after_datetime;
    const effectiveBeforeDatetime = datetimeFilters.before_datetime;

    const filter: any = {
      after_datetime: effectiveAfterDatetime,
    };

    if (effectiveBeforeDatetime) {
      filter.before_datetime = effectiveBeforeDatetime;
    }

    return {
      project_id: `${entity}/${project}`,
      filter,
      sort_by: backendSortBy,
      limit: effectiveLimit,
      offset: effectiveOffset,
    };
  }, [entity, project, backendSortBy, datetimeFilters, paginationModel]);

  // Use the actual threads query hook
  const {threadsState, turnCallsDataResult} = useThreadsQuery(queryParams);

  const loading = threadsState.loading;

  // Create column info for FilterPanel - only include datetime filterable columns
  const filterColumnInfo: ColumnInfo = useMemo(() => {
    return {
      cols: [
        {
          field: 'started_at',
          headerName: 'started_at',
          width: 120,
          type: 'dateTime',
        },
      ],
      colGroupingModel: [],
    };
  }, []);

  // Map server data to table format
  const tableData = useMemo(() => {
    const threads = threadsState.value?.threads || [];
    return threads.map((thread, index) => ({
      id: thread.thread_id,
      thread_id: thread.thread_id,
      status: thread.last_turn_id,
      number_of_traces: thread.turn_count,
      first_turn_id: thread.first_turn_id,
      last_turn_id: thread.last_turn_id,
      start_time: thread.start_time,
      last_updated: thread.last_updated,
      p50_latency: Math.max(thread.p50_turn_duration_ms ?? 0, 0.001),
      p99_latency: Math.max(thread.p99_turn_duration_ms ?? 0, 0.001),
    }));
  }, [threadsState.value]);

  // Refetch function for refresh button
  const refetch = useCallback(() => {
    threadsState.retry();
  }, [threadsState]);

  // Pagination change callback
  const onPaginationModelChange = useCallback(
    (newModel: GridPaginationModel) => {
      if (!setPaginationModel || loading) {
        return;
      }
      setPaginationModel(newModel);
    },
    [loading, setPaginationModel]
  );

  // Define columns for the threads table
  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'thread_id',
        headerName: 'Thread ID',
        width: 100,
        flex: 1,
        sortable: false,
        renderCell: params => (
          <div
            className="hover:text-blue-800 cursor-pointer text-blue-600 hover:underline"
            onClick={() => {
              const threadId = params.value;
              if (threadId) {
                history.push(
                  peekingRouter.threadUIUrl(entity, project, threadId)
                );
              }
            }}>
            {params.value}
          </div>
        ),
      },
      {
        field: 'status',
        headerName: 'Status',
        headerAlign: 'center',
        width: 90,
        resizable: false,
        display: 'flex',
        sortable: false,
        renderCell: params => (
          <ThreadStatus
            turnCallsDataResult={turnCallsDataResult}
            lastTurnId={params.value}
          />
        ),
      },
      {
        field: 'number_of_traces',
        headerName: 'Turns',
        width: 80,
        type: 'number',
        sortable: false,
      },
      {
        field: 'first_turn_id',
        headerName: 'First Input',
        width: 320,
        flex: 1,
        sortable: false,
        renderCell: params => (
          <FirstTurnInput
            turnCallsDataResult={turnCallsDataResult}
            turnId={params.value}
          />
        ),
      },
      {
        field: 'last_turn_id',
        headerName: 'Last Output',
        width: 320,
        flex: 1,
        sortable: false,
        renderCell: params => (
          <LastTurnOutput
            turnCallsDataResult={turnCallsDataResult}
            turnId={params.value}
          />
        ),
      },
      {
        field: 'start_time',
        headerName: 'Start Time',
        width: 120,
        minWidth: 100,
        maxWidth: 120,
        sortable: false,
        renderCell: params => {
          if (!params.value) return '';
          const date = convertISOToDate(params.value);
          const value = date.getTime() / 1000;
          return <Timestamp value={value} format="relative" />;
        },
      },
      {
        field: 'last_updated',
        headerName: 'Last Updated',
        width: 120,
        minWidth: 100,
        maxWidth: 120,
        sortable: true,
        sortingOrder: ['desc', 'asc'],
        renderCell: params => {
          if (!params.value) return '';
          const date = convertISOToDate(params.value);
          const value = date.getTime() / 1000;
          return <Timestamp value={value} format="relative" />;
        },
      },
      {
        field: 'p50_latency',
        headerName: 'p50 Latency',
        width: 140,
        type: 'number',
        sortable: false,
        renderCell: params => {
          if (!params.value) return '';
          // Convert from milliseconds to seconds for monthRoundedTime
          const timeS = params.value / 1000;
          return timeS.toFixed(3) + 's';
        },
      },
      {
        field: 'p99_latency',
        headerName: 'p99 Latency',
        width: 140,
        type: 'number',
        sortable: false,
        renderCell: params => {
          if (!params.value) return '';
          // Convert from milliseconds to seconds for monthRoundedTime
          const timeS = params.value / 1000;
          return timeS.toFixed(3) + 's';
        },
      },
    ],
    // Adding the missing peekingRouter to the dependency array causes a re-render loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [turnCallsDataResult, entity, history, project]
  );

  return (
    <FilterLayoutTemplate
      filterListSx={{
        pb: 1,
        display: 'flex',
        alignItems: 'center',
      }}
      filterListItems={
        <TailwindContents>
          <RefreshButton onClick={refetch} disabled={loading} />
          <FilterPanel
            entity={entity}
            project={project}
            filterModel={filterModel}
            columnInfo={filterColumnInfo}
            setFilterModel={setFilterModel}
            selectedCalls={[]}
            clearSelectedCalls={() => {}}
            isGrouped={true}
          />
          <div className="ml-auto flex min-w-0 items-center gap-8 overflow-hidden">
            <div className="flex-none">
              <ThreadsExportSelector
                numTotalThreads={tableData.length}
                disabled={tableData.length === 0}
              />
            </div>
          </div>
        </TailwindContents>
      }>
      <StyledDataGrid
        apiRef={apiRef}
        rows={tableData}
        columns={columns}
        loading={loading}
        // Column management
        columnVisibilityModel={columnVisibilityModel}
        onColumnVisibilityModelChange={setColumnVisibilityModel}
        pinnedColumns={pinModel}
        onPinnedColumnsChange={setPinModel}
        // Column Menu - disable filter and column management features
        disableColumnFilter={true}
        // Pagination
        pagination
        rowCount={
          // For server pagination without total count, we estimate based on current page
          // If we have a full page, assume there might be more pages
          threadsState.loading
            ? 0
            : (threadsState.value?.threads?.length ?? 0) <
              paginationModel.pageSize
            ? paginationModel.page * paginationModel.pageSize +
              (threadsState.value?.threads?.length ?? 0)
            : (paginationModel.page + 1) * paginationModel.pageSize + 1
        }
        paginationMode="server"
        paginationModel={paginationModel}
        onPaginationModelChange={onPaginationModelChange}
        // Filtering
        filterModel={filterModel}
        filterMode="server"
        // Sorting
        sortModel={sortModel}
        onSortModelChange={setSortModel}
        sortingMode="server"
        // Other settings
        pageSizeOptions={[10, 25, 50, 100]}
        disableRowSelectionOnClick
        rowHeight={40}
        columnHeaderHeight={38}
        // Footer settings
        hideFooter={false}
        hideFooterSelectedRowCount
        // Styling
        sx={{
          borderRadius: 0,
          '& .MuiDataGrid-footerContainer': {
            justifyContent: 'flex-start',
          },
          '& .MuiDataGrid-main:focus-visible': {
            outline: 'none',
          },
        }}
        // Custom slots
        slots={{
          pagination: () => <PaginationButtons />,
          loadingOverlay: () => (
            <div className="flex h-full w-full items-center justify-center">
              <WaveLoader size="huge" />
            </div>
          ),
        }}
        className="tw-style"
      />
    </FilterLayoutTemplate>
  );
};

// Shared component for displaying truncated JSON with tooltip
const TruncatedJsonDisplay: FC<{content: any}> = ({content}) => {
  const jsonString = JSON.stringify(content);
  const maxLength = 200;

  if (!jsonString || jsonString.length <= maxLength) {
    return <div>{jsonString}</div>;
  }

  const truncated = jsonString.substring(0, maxLength) + '...';

  return (
    <Tooltip
      trigger={
        <div className="cursor-pointer overflow-hidden text-ellipsis whitespace-nowrap">
          {truncated}
        </div>
      }
      content={jsonString}
    />
  );
};

// Component for displaying thread status based on last turn
const ThreadStatus: FC<{
  turnCallsDataResult: ReturnType<
    typeof useThreadsQuery
  >['turnCallsDataResult'];
  lastTurnId: string;
}> = ({turnCallsDataResult, lastTurnId}) => {
  if (turnCallsDataResult.lastTurnsLoading) {
    return <LoadingDots />;
  }

  const status = turnCallsDataResult.lastTurnsStatuses.get(lastTurnId);

  if (!status) {
    return null;
  }

  return (
    <div style={{margin: 'auto'}}>
      <StatusChip value={status} iconOnly />
    </div>
  );
};

interface FirstTurnInputProps {
  turnCallsDataResult: ReturnType<
    typeof useThreadsQuery
  >['turnCallsDataResult'];
  turnId: string;
}

function FirstTurnInput({turnCallsDataResult, turnId}: FirstTurnInputProps) {
  if (turnCallsDataResult.firstTurnsLoading) {
    return <LoadingDots />;
  }
  const input = turnCallsDataResult.firstTurnsInputs.get(turnId);
  if (!input) {
    return <span className="text-gray-500 italic">{'{No input}'}</span>;
  }
  return <TruncatedJsonDisplay content={input} />;
}

interface LastTurnOutputProps {
  turnCallsDataResult: ReturnType<
    typeof useThreadsQuery
  >['turnCallsDataResult'];
  turnId: string;
}

function LastTurnOutput({turnCallsDataResult, turnId}: LastTurnOutputProps) {
  if (turnCallsDataResult.lastTurnsLoading) {
    return <LoadingDots />;
  }
  const output = turnCallsDataResult.lastTurnsOutputs.get(turnId);
  if (!output) {
    return <span className="text-gray-500 italic">{'{No output}'}</span>;
  }
  return <TruncatedJsonDisplay content={output} />;
}
