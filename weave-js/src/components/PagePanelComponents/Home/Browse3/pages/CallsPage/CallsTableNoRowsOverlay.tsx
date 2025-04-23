import {Box, Typography} from '@mui/material';
import {GridFilterModel} from '@mui/x-data-grid-pro';
import React from 'react';

import {A, TargetBlank} from '../../../../../../common/util/links';
import {makeDateFilter, makeMonthFilter} from '../../filters/common';
import {Empty} from '../common/Empty';
import {
  EMPTY_PROPS_EVALUATIONS,
  EMPTY_PROPS_TRACES,
} from '../common/EmptyContent';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {filterHasCalledAfterDateFilter} from './CallsTable';

type CallsTableNoRowsOverlayProps = {
  entity: string;
  project: string;
  callsLoading: boolean;
  callsResult: CallSchema[];
  isEvaluateTable: boolean;
  effectiveFilter: {
    traceRootsOnly?: boolean;
    [key: string]: any;
  };
  filterModelResolved: GridFilterModel;
  clearFilters?: () => void;
  setFilterModel?: (model: GridFilterModel) => void;
  isFilterAdjusting?: boolean;
};

export const CallsTableNoRowsOverlay: React.FC<
  CallsTableNoRowsOverlayProps
> = ({
  entity,
  project,
  callsLoading,
  callsResult,
  isEvaluateTable,
  effectiveFilter,
  filterModelResolved,
  clearFilters,
  setFilterModel,
  isFilterAdjusting,
}) => {
  const {opLoading, opCreatedAt} = useCallsTableNoRowsOpLookup(entity, project);

  if (callsLoading || opLoading || isFilterAdjusting) {
    return null;
  }

  const isEmpty = callsResult.length === 0;
  if (!isEmpty) {
    return null;
  }

  const opExists = opCreatedAt != null;
  const hasDateFilter = filterHasCalledAfterDateFilter(filterModelResolved);

  // Handle special empty states
  if (isEvaluateTable) {
    if (!hasDateFilter) {
      return <Empty {...EMPTY_PROPS_EVALUATIONS} />;
    } else {
      return (
        <DateFilterEmptyState
          filterModelResolved={filterModelResolved}
          clearFilters={clearFilters}
          setFilterModel={setFilterModel}
        />
      );
    }
    // Show empty page if we have no ops, and thus haven't logged a real trace
  } else if (effectiveFilter.traceRootsOnly && !opExists) {
    return <Empty {...EMPTY_PROPS_TRACES} />;
  }

  if (hasDateFilter) {
    return (
      <DateFilterEmptyState
        filterModelResolved={filterModelResolved}
        clearFilters={clearFilters}
        setFilterModel={setFilterModel}
      />
    );
  }

  return <GeneralFilterEmptyState clearFilters={clearFilters} />;
};

type DateFilterEmptyStateProps = {
  filterModelResolved: GridFilterModel;
  clearFilters?: () => void;
  setFilterModel?: (model: GridFilterModel) => void;
};

const DateFilterEmptyState: React.FC<DateFilterEmptyStateProps> = ({
  filterModelResolved,
  clearFilters,
  setFilterModel,
}) => {
  const existingFilter = filterModelResolved.items.find(
    item => item.field === 'started_at' && item.operator === '(date): after'
  );

  const now = new Date();
  const existingFilterDays = existingFilter
    ? Math.round(
        (now.getTime() - new Date(existingFilter.value).getTime()) /
          (24 * 60 * 60 * 1000)
      )
    : 0;

  const clearingFilters = !setFilterModel || existingFilterDays > 7;

  const expandDateRange = () => {
    if (!setFilterModel) {
      clearFilters?.();
      return;
    }

    const currentFilterModel = {...filterModelResolved};
    const filteredItems = currentFilterModel.items.filter(
      item => item.field !== 'started_at'
    );

    // Determine new date range based on opCreatedAt
    let newDateFilter;
    if (existingFilterDays < 4) {
      newDateFilter = makeDateFilter(7);
    } else if (existingFilterDays <= 7) {
      newDateFilter = makeMonthFilter();
    } else {
      newDateFilter = undefined;
    }

    // Add the new date filter
    if (newDateFilter) {
      filteredItems.push(newDateFilter);
    }

    // Update the filter model
    setFilterModel({
      ...currentFilterModel,
      items: filteredItems,
    });
  };

  const dateRangeText = clearingFilters
    ? 'clearing your date range'
    : 'expanding your date range';

  return (
    <EmptyStateBox>
      No calls found for the specified date range.{' '}
      <>
        Try{' '}
        <ClearFiltersAction onClick={expandDateRange} text={dateRangeText} /> or
        looking for data in a different time period.
      </>
    </EmptyStateBox>
  );
};

type GeneralFilterEmptyStateProps = {
  clearFilters?: () => void;
};

const GeneralFilterEmptyState: React.FC<GeneralFilterEmptyStateProps> = ({
  clearFilters,
}) => {
  return (
    <EmptyStateBox>
      No calls found with the current filters.{' '}
      {clearFilters != null ? (
        <>
          Try{' '}
          <ClearFiltersAction
            onClick={clearFilters}
            text="clearing the filters"
          />{' '}
          or learn more about how to log calls by visiting <DocsLink />.
        </>
      ) : (
        <>
          Learn more about how to log calls by visiting <DocsLink />.
        </>
      )}
    </EmptyStateBox>
  );
};

// Common box styling for both empty states
const EmptyStateBox = ({children}: {children: React.ReactNode}) => (
  <Box
    sx={{
      width: '100%',
      height: '100%',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
    }}>
    <Typography color="textSecondary">{children}</Typography>
  </Box>
);

// Helper for rendering a clickable action
const ClearFiltersAction = ({
  onClick,
  text,
}: {
  onClick: () => void;
  text: string;
}) => <A onClick={onClick}>{text}</A>;

// Documentation link that appears in both states
const DocsLink = () => (
  <TargetBlank href="https://wandb.me/weave">the docs</TargetBlank>
);

const useCallsTableNoRowsOpLookup = (entity: string, project: string) => {
  const {useOpVersions} = useWFHooks();
  const {loading, result} = useOpVersions(
    entity,
    project,
    {latestOnly: true},
    1,
    true,
    [{field: 'created_at', direction: 'desc'}],
    undefined
  );
  if (loading) {
    return {opLoading: true, opCreatedAt: null};
  }
  const opCreatedAt = result?.[0]?.createdAtMs;
  return {opLoading: false, opCreatedAt};
};
