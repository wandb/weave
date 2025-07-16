import {ApolloProvider} from '@apollo/client';
import {GridPaginationModel, GridSortModel} from '@mui/x-data-grid-pro';
import {makeGorillaApolloClient} from '@wandb/weave/apollo';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useCallback, useMemo, useState} from 'react';

import {DeleteModal} from '../common/DeleteModal';
import {useWFHooks, WFDataModelAutoProvider} from '../wfReactInterface/context';
import {CostQueryOutput} from '../wfReactInterface/traceServerClientTypes';
import {AddCostDrawer, AddCostForm} from './AddCostDrawer';
import {CostsFilters} from './CostsFilters';
import {CostsTable} from './CostsTable';

const CostsTabInner = ({
  entityName,
  projectName,
}: {
  entityName: string;
  projectName: string;
}) => {
  const {useCosts, useCostCreate, useCostDelete} = useWFHooks();

  // State for filters and pagination
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 100,
  });
  const [sortModel, setSortModel] = useState<GridSortModel>([
    {field: 'effective_date', sort: 'desc'},
  ]);
  const [showOnlyLatest, setShowOnlyLatest] = useState(false);
  const [showCloseToZero, setShowCloseToZero] = useState(false);
  const [showProjectCostsFirst, setShowProjectCostsFirst] = useState(true);
  const [searchText, setSearchText] = useState('');

  // Add cost drawer state
  const [showAddCostDrawer, setShowAddCostDrawer] = useState(false);
  const [editingCost, setEditingCost] = useState<CostQueryOutput | null>(null);
  const [selectedCosts, setSelectedCosts] = useState<Set<string>>(new Set());

  // Delete modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [costsToDelete, setCostsToDelete] = useState<CostQueryOutput[]>([]);
  const [isBulkDelete, setIsBulkDelete] = useState(false);

  // Get cost create function
  const createCost = useCostCreate();
  const deleteCost = useCostDelete();

  // Build query parameters
  const queryParams = useMemo(() => {
    const params: any = {
      projectId: `${entityName}/${projectName}`,
      // Remove limit and offset for client-side pagination
      sortBy: sortModel.map(sort => ({
        field: sort.field,
        direction: sort.sort || 'asc',
      })),
    };

    // Build query to filter costs - include close to zero costs if checkbox is checked
    const minCostThreshold = showCloseToZero ? 0 : 0.00000001;
    const queryExpr = {
      $and: [
        {
          $gt: [{$getField: 'prompt_token_cost'}, {$literal: minCostThreshold}],
        },
        {
          $gt: [
            {$getField: 'completion_token_cost'},
            {$literal: minCostThreshold},
          ],
        },
      ],
    };

    params.query = {
      $expr: queryExpr,
    };

    return params;
  }, [entityName, projectName, sortModel, showCloseToZero]);

  // Fetch costs
  const costsResult = useCosts(queryParams);

  // Filter costs based on search text - move allCosts logic inside useMemo
  const searchFilteredCosts = useMemo(() => {
    const allCosts = costsResult.loading ? [] : costsResult.result || [];

    if (!searchText.trim()) return allCosts;

    const searchLower = searchText.toLowerCase();
    return allCosts.filter(
      cost =>
        cost.llm_id?.toLowerCase().includes(searchLower) ||
        cost.provider_id?.toLowerCase().includes(searchLower) ||
        cost.pricing_level?.toLowerCase().includes(searchLower)
    );
  }, [costsResult.loading, costsResult.result, searchText]);

  // Filter for latest costs only if checkbox is checked
  const filteredCosts = useMemo(() => {
    if (!showOnlyLatest) return searchFilteredCosts;

    // Group by llm_id and provider_id, then get the most recent for each
    const latestCosts = new Map<string, CostQueryOutput>();

    searchFilteredCosts.forEach(cost => {
      const key = `${cost.llm_id}-${cost.provider_id}`;
      const existing = latestCosts.get(key);

      if (
        !existing ||
        (cost.effective_date &&
          (!existing.effective_date ||
            cost.effective_date > existing.effective_date))
      ) {
        latestCosts.set(key, cost);
      }
    });

    return Array.from(latestCosts.values());
  }, [searchFilteredCosts, showOnlyLatest]);

  // Separate project costs from other costs and always put project costs first
  const orderedCosts = useMemo(() => {
    // First, apply sorting to the filtered costs
    const sortedCosts = [...filteredCosts].sort((a, b) => {
      for (const sort of sortModel) {
        const aValue = a[sort.field as keyof CostQueryOutput];
        const bValue = b[sort.field as keyof CostQueryOutput];

        let comparison = 0;

        // Handle null/undefined values
        if (aValue == null && bValue == null) comparison = 0;
        else if (aValue == null) comparison = 1;
        else if (bValue == null) comparison = -1;
        // Handle date fields
        else if (
          sort.field === 'effective_date' ||
          sort.field === 'created_at'
        ) {
          comparison =
            new Date(aValue as string).getTime() -
            new Date(bValue as string).getTime();
        }
        // Handle pricing_level field (project costs first)
        else if (sort.field === 'pricing_level') {
          if (aValue === 'project' && bValue !== 'project') comparison = -1;
          else if (aValue !== 'project' && bValue === 'project') comparison = 1;
          else comparison = (aValue as string).localeCompare(bValue as string);
        }
        // Handle other fields
        else {
          if (typeof aValue === 'string' && typeof bValue === 'string') {
            comparison = aValue.localeCompare(bValue);
          } else if (typeof aValue === 'number' && typeof bValue === 'number') {
            comparison = aValue - bValue;
          } else {
            comparison = String(aValue).localeCompare(String(bValue));
          }
        }

        if (comparison !== 0) {
          return sort.sort === 'desc' ? -comparison : comparison;
        }
      }
      return 0;
    });

    // If project costs first is not enabled, just return the sorted costs
    if (!showProjectCostsFirst) return sortedCosts;

    // Separate project costs from other costs while preserving sort order within each group
    const projectCosts = sortedCosts.filter(
      cost => cost.pricing_level === 'project'
    );
    const otherCosts = sortedCosts.filter(
      cost => cost.pricing_level !== 'project'
    );

    // Only separate if there are actually project costs
    if (projectCosts.length === 0) {
      return sortedCosts;
    }

    return [...projectCosts, ...otherCosts];
  }, [filteredCosts, showProjectCostsFirst, sortModel]);

  // Client-side pagination
  const paginatedCosts = useMemo(() => {
    const startIndex = paginationModel.page * paginationModel.pageSize;
    const endIndex = startIndex + paginationModel.pageSize;
    return orderedCosts.slice(startIndex, endIndex);
  }, [orderedCosts, paginationModel]);

  // Handle pagination changes
  const handlePaginationModelChange = useCallback(
    (model: GridPaginationModel) => {
      setPaginationModel(model);
    },
    []
  );

  // Handle sort changes
  const handleSortModelChange = useCallback((model: GridSortModel) => {
    setSortModel(model);
  }, []);

  // Handle checkbox change
  const handleShowOnlyLatestChange = useCallback((checked: boolean) => {
    setShowOnlyLatest(checked);
    // Reset to first page when filter changes
    setPaginationModel(prev => ({...prev, page: 0}));
  }, []);

  // Handle close to zero checkbox change
  const handleShowCloseToZeroChange = useCallback((checked: boolean) => {
    setShowCloseToZero(checked);
    // Reset to first page when filter changes
    setPaginationModel(prev => ({...prev, page: 0}));
  }, []);

  // Handle show project costs first checkbox change
  const handleShowProjectCostsFirstChange = useCallback((checked: boolean) => {
    setShowProjectCostsFirst(checked);
    // Reset to first page when filter changes
    setPaginationModel(prev => ({...prev, page: 0}));
  }, []);

  // Use regular sortModel instead of effectiveSortModel since we're not using sort for project prioritization
  const effectiveSortModel = sortModel;

  // Handle search change - optimized to reduce re-renders
  const handleSearchChange = useCallback((value: string) => {
    setSearchText(value);
    // Reset to first page when search changes
    setPaginationModel(prev => ({...prev, page: 0}));
  }, []);

  // Handle edit cost
  const handleEditCost = useCallback((cost: CostQueryOutput) => {
    setEditingCost(cost);
    setShowAddCostDrawer(true);
  }, []);

  // Handle add cost form submission
  const handleAddCostSubmit = useCallback(
    async (form: AddCostForm) => {
      await createCost({
        project_id: `${entityName}/${projectName}`,
        costs: {
          [form.llm_id]: {
            prompt_token_cost: parseFloat(form.prompt_token_cost),
            completion_token_cost: parseFloat(form.completion_token_cost),
            prompt_token_cost_unit: 'USD',
            completion_token_cost_unit: 'USD',
            provider_id: form.provider_id,
            effective_date: form.effective_date || undefined,
          },
        },
      });

      // Wait for refetch to complete before returning
      await costsResult.refetch();
    },
    [createCost, entityName, projectName, costsResult]
  );

  // Handle drawer close
  const handleDrawerClose = useCallback(() => {
    setEditingCost(null);
    setShowAddCostDrawer(false);
  }, []);

  // Handle selection change
  const handleSelectionChange = useCallback((selectedIds: Set<string>) => {
    setSelectedCosts(selectedIds);
  }, []);

  // Handle bulk delete
  const handleBulkDelete = useCallback(
    (costIds: string[]) => {
      if (costIds.length === 0) return;

      // Find the actual cost objects to show in the modal
      const costsToDeleteList = orderedCosts.filter(
        cost => cost.id && costIds.includes(cost.id)
      );

      setCostsToDelete(costsToDeleteList);
      setIsBulkDelete(true);
      setDeleteModalOpen(true);
    },
    [orderedCosts]
  );

  // Handle individual delete
  const handleDelete = useCallback(
    (costId: string) => {
      // Find the actual cost object to show in the modal
      const costToDelete = orderedCosts.find(cost => cost.id === costId);
      if (!costToDelete) return;

      setCostsToDelete([costToDelete]);
      setIsBulkDelete(false);
      setDeleteModalOpen(true);
    },
    [orderedCosts]
  );

  // Actual delete function called by the modal
  const performDelete = useCallback(async () => {
    const costIds = costsToDelete
      .map(cost => cost.id)
      .filter(Boolean) as string[];

    if (costIds.length === 0) return;

    // Use $eq for single delete, $or with multiple $eq for bulk delete
    const query =
      costIds.length === 1
        ? {
            $expr: {
              $eq: [{$getField: 'id'}, {$literal: costIds[0]}],
            },
          }
        : {
            $expr: {
              $or: costIds.map(id => ({
                $eq: [{$getField: 'id'}, {$literal: id}],
              })),
            },
          };

    await deleteCost({
      project_id: `${entityName}/${projectName}`,
      query,
    });

    // Clear selection and refetch costs
    setSelectedCosts(new Set());
    costsResult.refetch();
  }, [costsToDelete, deleteCost, entityName, projectName, costsResult]);

  // Handle modal close
  const handleDeleteModalClose = useCallback(() => {
    setDeleteModalOpen(false);
    setCostsToDelete([]);
    setIsBulkDelete(false);
  }, []);

  // Format cost information for the modal
  const formatCostInfo = useCallback((cost: CostQueryOutput) => {
    const effectiveDate = cost.effective_date
      ? new Date(cost.effective_date).toLocaleDateString()
      : 'No date';
    return `${cost.llm_id} (${cost.provider_id}) - ${effectiveDate}`;
  }, []);

  const deleteModalTitle = isBulkDelete
    ? `${costsToDelete.length} cost${costsToDelete.length === 1 ? '' : 's'}`
    : 'cost';

  const deleteModalBodyStrs = costsToDelete.map(formatCostInfo);

  // Calculate total count for client-side pagination
  const totalCount = orderedCosts.length;

  return (
    <div className="mx-32 my-8">
      {/* Results count */}
      <div className="mb-4 text-sm text-moon-600">
        {costsResult.loading
          ? 'Loading costs...'
          : `Showing ${paginatedCosts.length} of ${totalCount} costs${
              showOnlyLatest ? ' (latest only)' : ''
            }`}
      </div>

      <CostsFilters
        showOnlyLatest={showOnlyLatest}
        onShowOnlyLatestChange={handleShowOnlyLatestChange}
        showCloseToZero={showCloseToZero}
        onShowCloseToZeroChange={handleShowCloseToZeroChange}
        showProjectCostsFirst={showProjectCostsFirst}
        onShowProjectCostsFirstChange={handleShowProjectCostsFirstChange}
        searchText={searchText}
        onSearchChange={handleSearchChange}
        onAddCostClick={() => setShowAddCostDrawer(true)}
        selectedCosts={selectedCosts}
        onBulkDelete={handleBulkDelete}
      />

      {/* Table */}
      <div className="scroll-x w-full overflow-hidden rounded-lg border border-moon-200 bg-white">
        <CostsTable
          costs={paginatedCosts}
          loading={costsResult.loading}
          paginationModel={paginationModel}
          onPaginationModelChange={handlePaginationModelChange}
          sortModel={effectiveSortModel}
          onSortModelChange={handleSortModelChange}
          totalCount={totalCount}
          onEdit={handleEditCost}
          selectedCosts={selectedCosts}
          onSelectionChange={handleSelectionChange}
          onDelete={handleDelete}
        />
      </div>

      <AddCostDrawer
        open={showAddCostDrawer}
        onClose={handleDrawerClose}
        onSubmit={handleAddCostSubmit}
        editingCost={editingCost}
      />

      <DeleteModal
        open={deleteModalOpen}
        onClose={handleDeleteModalClose}
        onDelete={performDelete}
        deleteTitleStr={deleteModalTitle}
        deleteBodyStrs={deleteModalBodyStrs}
      />
    </div>
  );
};

export const CostsTab = ({
  entityName,
  projectName,
}: {
  entityName: string;
  projectName: string;
}) => {
  return (
    <ApolloProvider client={makeGorillaApolloClient()}>
      <WFDataModelAutoProvider
        entityName={entityName}
        projectName={projectName}>
        <Tailwind className="h-full w-full">
          <CostsTabInner entityName={entityName} projectName={projectName} />
        </Tailwind>
      </WFDataModelAutoProvider>
    </ApolloProvider>
  );
};

export default CostsTab;
