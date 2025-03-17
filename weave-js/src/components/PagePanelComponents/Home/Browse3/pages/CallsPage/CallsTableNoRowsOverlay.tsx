import {Box, Typography} from '@mui/material';
import {GridFilterModel} from '@mui/x-data-grid-pro';
import React from 'react';

import {A, TargetBlank} from '../../../../../../common/util/links';
import {
  make3MonthsLongDateFilter,
  makeYearLongDateFilter,
} from '../../filters/common';
import {Empty} from '../common/Empty';
import {
  EMPTY_PROPS_EVALUATIONS,
  EMPTY_PROPS_TRACES,
} from '../common/EmptyContent';
import {filterHasDefaultDateFilter} from './CallsTable';

type CallsTableNoRowsOverlayProps = {
  callsLoading: boolean;
  callsResult: any[];
  isEvaluateTable: boolean;
  effectiveFilter: {
    traceRootsOnly?: boolean;
    [key: string]: any;
  };
  filterModelResolved: GridFilterModel;
  clearFilters?: () => void;
  setFilterModel?: (model: GridFilterModel) => void;
};

export const CallsTableNoRowsOverlay: React.FC<
  CallsTableNoRowsOverlayProps
> = ({
  callsLoading,
  callsResult,
  isEvaluateTable,
  effectiveFilter,
  filterModelResolved,
  clearFilters,
  setFilterModel,
}) => {
  if (callsLoading) {
    return <></>;
  }

  const isEmpty = callsResult.length === 0;
  if (!isEmpty) {
    return null;
  }

  // Handle special empty states
  if (isEvaluateTable) {
    return <Empty {...EMPTY_PROPS_EVALUATIONS} />;
  } else if (
    effectiveFilter.traceRootsOnly &&
    filterModelResolved.items.length === 0
  ) {
    return <Empty {...EMPTY_PROPS_TRACES} />;
  }

  const hasDateFilter = filterHasDefaultDateFilter(filterModelResolved);
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
  const expandDateRange = () => {
    if (!setFilterModel) {
      clearFilters?.();
      return;
    }
    const currentFilterModel = {...filterModelResolved};
    const items = [...currentFilterModel.items];

    // Find existing date filter to determine what range to expand to next
    const dateFilter = items.find(item => item.field === 'started_at');
    // Remove any existing started_at filters
    const filteredItems = items.filter(item => item.field !== 'started_at');

    // Determine new date range based on current filter's date
    let newDateFilter;
    if (dateFilter && dateFilter.value) {
      const filterDate = new Date(dateFilter.value);
      const now = new Date();
      const daysDifference = Math.round(
        (now.getTime() - filterDate.getTime()) / (24 * 60 * 60 * 1000)
      );

      // If the current filter is approximately 30 days, expand to 3 months
      if (daysDifference >= 25 && daysDifference <= 35) {
        newDateFilter = make3MonthsLongDateFilter();
      }
      // If the current filter is approximately 3 months, expand to 1 year
      else if (daysDifference >= 85 && daysDifference <= 95) {
        newDateFilter = makeYearLongDateFilter();
      }
      // For any other case, don't add a datetime filter
      else {
        setFilterModel({
          ...currentFilterModel,
          items: filteredItems,
        });
        return;
      }
    } else {
      // Impossible (block conditioned on hasDateFilter), but default to 3 months
      newDateFilter = make3MonthsLongDateFilter();
    }

    // Add the new date filter
    filteredItems.push(newDateFilter);

    // Update the filter model
    setFilterModel({
      ...currentFilterModel,
      items: filteredItems,
    });
  };

  return (
    <EmptyStateBox>
      No calls found for the specified date range.{' '}
      <>
        Try{' '}
        <ClearFiltersAction
          onClick={expandDateRange}
          text="expanding your date range"
        />{' '}
        or looking for data in a different time period.
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
