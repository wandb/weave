import {Box, Typography} from '@mui/material';
import {GridFilterModel} from '@mui/x-data-grid-pro';
import React from 'react';

import {A, TargetBlank} from '../../../../../../common/util/links';
import {makeYearLongDateFilter} from '../../filters/common';
import {Empty} from '../common/Empty';
import {
  EMPTY_PROPS_EVALUATIONS,
  EMPTY_PROPS_TRACES,
} from '../common/EmptyContent';
import {filterHasDefaultDateFilter} from './CallsTable';

interface CallsTableNoRowsOverlayProps {
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
}

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

  // Check if we have a date filter - different message for different cases
  const hasDateFilter = filterHasDefaultDateFilter(filterModelResolved);

  const expandDateRange = () => {
    if (!setFilterModel) {
      clearFilters?.();
      return;
    }
    const currentFilterModel = {...filterModelResolved};
    const items = [...currentFilterModel.items];
    // Remove any existing started_at filters
    const filteredItems = items.filter(item => item.field !== 'started_at');
    // Add the year-long date filter
    filteredItems.push(makeYearLongDateFilter());
    // Update the filter model
    setFilterModel({
      ...currentFilterModel,
      items: filteredItems,
    });
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

  const ClearFiltersAction = ({
    onClick,
    text,
  }: {
    onClick: () => void;
    text: string;
  }) => <A onClick={onClick}>{text}</A>;

  const DocsLink = () => (
    <TargetBlank href="https://wandb.me/weave">the docs</TargetBlank>
  );

  if (hasDateFilter) {
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
  }

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
