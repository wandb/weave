import {
  GridColDef,
  GridPaginationModel,
  GridRenderCellParams,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {MOON_600, OBLIVION} from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import {Button} from '@wandb/weave/components/Button';
import {Checkbox} from '@wandb/weave/components/Checkbox';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import React, {useMemo} from 'react';

import {StyledDataGrid} from '../../StyledDataGrid';
import {PaginationButtons} from '../CallsPage/CallsTableButtons';
import {CostQueryOutput} from '../wfReactInterface/traceServerClientTypes';

const HEADER_BACKGROUND = hexToRGB(OBLIVION, 0.02);

interface CostsTableProps {
  costs: CostQueryOutput[];
  loading: boolean;
  paginationModel: GridPaginationModel;
  onPaginationModelChange: (model: GridPaginationModel) => void;
  sortModel: GridSortModel;
  onSortModelChange: (model: GridSortModel) => void;
  totalCount: number;
  onEdit: (cost: CostQueryOutput) => void;
  selectedCosts: Set<string>;
  onSelectionChange: (selectedIds: Set<string>) => void;
  onDelete: (costId: string) => void;
}

export const CostsTable: React.FC<CostsTableProps> = ({
  costs,
  loading,
  paginationModel,
  onPaginationModelChange,
  sortModel,
  onSortModelChange,
  totalCount,
  onEdit,
  selectedCosts,
  onSelectionChange,
  onDelete,
}) => {
  // Filter project costs for checkbox functionality
  const projectCosts = useMemo(
    () => costs.filter(cost => cost.pricing_level === 'project'),
    [costs]
  );

  // Check if all project costs are selected
  const allProjectCostsSelected = useMemo(() => {
    if (projectCosts.length === 0) return false;
    return projectCosts.every(cost => selectedCosts.has(cost.id || ''));
  }, [projectCosts, selectedCosts]);

  // Check if some (but not all) project costs are selected
  const someProjectCostsSelected = useMemo(() => {
    if (projectCosts.length === 0) return false;
    return (
      projectCosts.some(cost => selectedCosts.has(cost.id || '')) &&
      !allProjectCostsSelected
    );
  }, [projectCosts, selectedCosts, allProjectCostsSelected]);

  // Handle header checkbox toggle
  const handleHeaderCheckboxChange = (checked: boolean) => {
    const newSelection = new Set(selectedCosts);

    if (newSelection.size > 0) {
      newSelection.clear();
    } else {
      // Select all project costs
      projectCosts.forEach(cost => {
        if (cost.id) newSelection.add(cost.id);
      });
    }
    onSelectionChange(newSelection);
  };

  // Handle individual checkbox change
  const handleCheckboxChange = (costId: string, checked: boolean) => {
    const newSelection = new Set(selectedCosts);

    if (checked) {
      newSelection.add(costId);
    } else {
      newSelection.delete(costId);
    }

    onSelectionChange(newSelection);
  };

  const columns: GridColDef[] = [
    {
      field: 'selection',
      headerName: '',
      width: 50,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      renderHeader: () => (
        <div className="flex h-full w-full items-center justify-start">
          <Checkbox
            checked={
              someProjectCostsSelected
                ? 'indeterminate'
                : allProjectCostsSelected
            }
            onCheckedChange={handleHeaderCheckboxChange}
            disabled={projectCosts.length === 0}
          />
        </div>
      ),
      renderCell: (params: GridRenderCellParams) => {
        const isProjectCost = params.row.pricing_level === 'project';
        const costId = params.row.id || '';

        if (!isProjectCost) {
          return null;
        }

        return (
          <div className="flex h-full w-full items-center justify-start">
            <Checkbox
              checked={selectedCosts.has(costId)}
              onCheckedChange={checked =>
                handleCheckboxChange(costId, !!checked)
              }
            />
          </div>
        );
      },
    },
    {
      field: 'llm_id',
      headerName: 'Model',
      flex: 0.2,
      minWidth: 150,
    },
    {
      field: 'provider_id',
      headerName: 'Provider',
      flex: 0.15,
      minWidth: 120,
    },
    {
      field: 'prompt_token_cost',
      headerName: 'Prompt Cost',
      flex: 0.15,
      minWidth: 120,
      type: 'number',
      renderCell: (params: GridRenderCellParams) => {
        if (!params.value) return '-';
        return `$${Number(params.value).toFixed(8)}`;
      },
    },
    {
      field: 'completion_token_cost',
      headerName: 'Completion Cost',
      flex: 0.15,
      minWidth: 120,
      type: 'number',
      renderCell: (params: GridRenderCellParams) => {
        if (!params.value) return '-';
        return `$${Number(params.value).toFixed(8)}`;
      },
    },
    {
      field: 'effective_date',
      headerName: 'Effective Date',
      flex: 0.15,
      minWidth: 150,
      sortComparator: (v1, v2) => {
        // Handle null values - put them at the end
        if (!v1 && !v2) return 0;
        if (!v1) return 1;
        if (!v2) return -1;
        return new Date(v1).getTime() - new Date(v2).getTime();
      },
      renderCell: (params: GridRenderCellParams) => {
        if (!params.value) return '-';
        return <Timestamp value={params.value} format="relative" />;
      },
    },
    {
      field: 'created_at',
      headerName: 'Created',
      flex: 0.15,
      minWidth: 150,
      sortComparator: (v1, v2) => {
        // Handle null values - put them at the end
        if (!v1 && !v2) return 0;
        if (!v1) return 1;
        if (!v2) return -1;
        return new Date(v1).getTime() - new Date(v2).getTime();
      },
      renderCell: (params: GridRenderCellParams) => {
        if (!params.value) return '-';
        return <Timestamp value={params.value} format="relative" />;
      },
    },
    {
      field: 'pricing_level',
      headerName: 'Level',
      flex: 0.1,
      minWidth: 80,
      sortComparator: (v1, v2) => {
        // Custom sort to ensure project costs come first
        if (v1 === 'project' && v2 !== 'project') return -1;
        if (v1 !== 'project' && v2 === 'project') return 1;
        return v1.localeCompare(v2);
      },
      renderCell: (params: GridRenderCellParams) => {
        const level = params.value;
        return (
          <span
            className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
              level === 'project'
                ? 'bg-blue-100 text-blue-800'
                : 'bg-gray-100 text-gray-800'
            }`}>
            {level === 'project' ? 'Project' : 'Default'}
          </span>
        );
      },
    },
    {
      field: 'actions',
      headerName: '',
      width: 80,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      renderCell: (params: GridRenderCellParams) => {
        const isProjectCost = params.row.pricing_level === 'project';

        return (
          <div className="mt-2 flex items-center justify-end gap-4">
            {isProjectCost && (
              <Button
                icon="delete"
                variant="ghost"
                onClick={() => {
                  onDelete(params.row.id);
                }}
                tooltip="Delete cost"
              />
            )}
            <Button
              icon="pencil-edit"
              variant="ghost"
              onClick={() => onEdit(params.row)}
              tooltip="Update cost"
            />
          </div>
        );
      },
    },
  ];

  const tableData = useMemo(() => {
    return costs.map((cost, index) => ({
      id: cost.id || `cost-${index}`,
      ...cost,
    }));
  }, [costs]);

  return loading ? (
    <div className="flex h-full min-h-[400px] items-center justify-center">
      <LoadingDots />
    </div>
  ) : (
    <StyledDataGrid
      rows={tableData}
      columns={columns}
      loading={loading}
      autoHeight
      // Pagination
      pagination
      paginationMode="server"
      paginationModel={paginationModel}
      onPaginationModelChange={onPaginationModelChange}
      rowCount={totalCount}
      pageSizeOptions={[25, 50, 100]}
      // Sorting
      sortingMode="server"
      sortModel={sortModel}
      onSortModelChange={onSortModelChange}
      // Column settings
      disableColumnMenu={false}
      disableColumnFilter={true}
      disableMultipleColumnsFiltering={true}
      disableColumnReorder={false}
      disableColumnSelector={false}
      disableMultipleColumnsSorting={false}
      disableColumnResize={false}
      disableColumnPinning={false}
      // Display settings
      columnHeaderHeight={38}
      rowHeight={38}
      disableRowSelectionOnClick
      hideFooter={false}
      hideFooterSelectedRowCount
      // Custom pagination component
      slots={{
        pagination: () => <PaginationButtons />,
      }}
      // Styling
      sx={{
        '& .MuiDataGrid-columnHeader': {
          backgroundColor: HEADER_BACKGROUND,
        },
        '& .MuiDataGrid-columnHeaderTitle': {
          color: MOON_600,
          fontWeight: 600,
        },
        '& .MuiDataGrid-footerContainer': {
          justifyContent: 'flex-start',
        },
      }}
    />
  );
};
