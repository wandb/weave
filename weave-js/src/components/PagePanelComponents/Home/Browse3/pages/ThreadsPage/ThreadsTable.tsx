import {
  GridColDef,
  GridFilterModel,
  GridPaginationModel,
  GridSortModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import React, {FC, useMemo, useState} from 'react';

import {TailwindContents} from '../../../../../Tailwind';
import {useEntityProject} from '../../context';
import {DEFAULT_PAGE_SIZE} from '../../grid/pagination';
import {StyledDataGrid} from '../../StyledDataGrid';
import {PaginationButtons, RefreshButton} from '../CallsPage/CallsTableButtons';
import {FilterLayoutTemplate} from '../common/SimpleFilterableDataTable';
import {ThreadsExportSelector} from './ThreadsExportSelector';

// Mock data for now - will be replaced with actual API calls later
const MOCK_THREADS_DATA = [
  {
    id: 'thread_1',
    thread_id: 'thread_abc123',
    status: 'completed',
    number_of_traces: 15,
    tokens: 1250,
    first_input: 'What is machine learning?',
    last_output: 'Machine learning is a subset of artificial intelligence...',
    start_time: '2024-01-15T10:30:00Z',
    last_updated: '2024-01-15T10:45:00Z',
    p50_latency: 120,
    p99_latency: 450,
  },
  {
    id: 'thread_2',
    thread_id: 'thread_def456',
    status: 'running',
    number_of_traces: 8,
    tokens: 890,
    first_input: 'Explain neural networks',
    last_output: 'Neural networks are computing systems...',
    start_time: '2024-01-15T11:00:00Z',
    last_updated: '2024-01-15T11:15:00Z',
    p50_latency: 95,
    p99_latency: 320,
  },
  {
    id: 'thread_3',
    thread_id: 'thread_ghi789',
    status: 'failed',
    number_of_traces: 3,
    tokens: 150,
    first_input: 'How does deep learning work?',
    last_output: '',
    start_time: '2024-01-15T12:00:00Z',
    last_updated: '2024-01-15T12:05:00Z',
    p50_latency: null,
    p99_latency: null,
  },
];

export const ThreadsTable: FC<{
  filterModel?: GridFilterModel;
  setFilterModel?: (newModel: GridFilterModel) => void;

  sortModel?: GridSortModel;
  setSortModel?: (newModel: GridSortModel) => void;

  paginationModel?: GridPaginationModel;
  setPaginationModel?: (newModel: GridPaginationModel) => void;
}> = ({
  filterModel,
  setFilterModel,
  sortModel,
  setSortModel,
  paginationModel,
  setPaginationModel,
}) => {
  const {entity, project} = useEntityProject();

  // Setup Ref to underlying table
  const apiRef = useGridApiRef();
  const [loading, setLoading] = useState(false);

  // Mock refetch function for refresh button
  const refetch = () => {
    setLoading(true);
    // Simulate API call
    setTimeout(() => setLoading(false), 1000);
  };

  // Define columns for the threads table
  const columns: GridColDef[] = useMemo(
    () => [
      {
        field: 'thread_id',
        headerName: 'Thread ID',
        width: 200,
        flex: 1,
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 120,
        renderCell: params => {
          const status = params.value as string;
          const color =
            status === 'completed'
              ? 'green'
              : status === 'running'
              ? 'blue'
              : status === 'failed'
              ? 'red'
              : 'gray';
          return <span style={{color, fontWeight: 'bold'}}>{status}</span>;
        },
      },
      {
        field: 'number_of_traces',
        headerName: 'Number of Traces',
        width: 150,
        type: 'number',
      },
      {
        field: 'tokens',
        headerName: 'Tokens',
        width: 120,
        type: 'number',
        renderCell: params => params.value?.toLocaleString() || '',
      },
      {
        field: 'first_input',
        headerName: 'First Input',
        width: 250,
        flex: 1,
        renderCell: params => (
          <div
            style={{
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '100%',
            }}>
            {params.value || ''}
          </div>
        ),
      },
      {
        field: 'last_output',
        headerName: 'Last Output',
        width: 250,
        flex: 1,
        renderCell: params => (
          <div
            style={{
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '100%',
            }}>
            {params.value || ''}
          </div>
        ),
      },
      {
        field: 'start_time',
        headerName: 'Start Time',
        width: 180,
        type: 'dateTime',
        valueGetter: value => (value ? new Date(value) : null),
        renderCell: params => {
          if (!params.value) return '';
          return new Date(params.value).toLocaleString();
        },
      },
      {
        field: 'last_updated',
        headerName: 'Last Updated',
        width: 180,
        type: 'dateTime',
        valueGetter: value => (value ? new Date(value) : null),
        renderCell: params => {
          if (!params.value) return '';
          return new Date(params.value).toLocaleString();
        },
      },
      {
        field: 'p50_latency',
        headerName: 'p50 Latency (ms)',
        width: 140,
        type: 'number',
        renderCell: params => (params.value ? `${params.value}ms` : ''),
      },
      {
        field: 'p99_latency',
        headerName: 'p99 Latency (ms)',
        width: 140,
        type: 'number',
        renderCell: params => (params.value ? `${params.value}ms` : ''),
      },
    ],
    []
  );

  const resolvedPaginationModel = paginationModel ?? {
    pageSize: DEFAULT_PAGE_SIZE,
    page: 0,
  };

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
          <div className="ml-auto flex min-w-0 items-center gap-8 overflow-hidden">
            <div className="flex-none">
              <ThreadsExportSelector
                numTotalThreads={MOCK_THREADS_DATA.length}
                disabled={MOCK_THREADS_DATA.length === 0}
              />
            </div>
          </div>
        </TailwindContents>
      }>
      <StyledDataGrid
        apiRef={apiRef}
        rows={MOCK_THREADS_DATA}
        columns={columns}
        loading={loading}
        // Pagination
        pagination
        rowCount={MOCK_THREADS_DATA.length}
        paginationMode="client"
        paginationModel={resolvedPaginationModel}
        onPaginationModelChange={setPaginationModel}
        // Filtering
        filterModel={filterModel}
        onFilterModelChange={setFilterModel}
        // Sorting
        sortModel={sortModel}
        onSortModelChange={setSortModel}
        sortingMode="client"
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
          // Move pagination controls to the left like CallsTable
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
