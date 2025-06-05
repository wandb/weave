/*
  useChartsData.ts

  This file contains the hook for fetching and processing data for charts.

  It fetches calls data based on the provided filters and processes it into
  chart-friendly format using extractCallData.
*/

import {GridSortDirection} from '@mui/x-data-grid-pro';
import React from 'react';

import {useCallsForQuery} from '../pages/CallsPage/callsTableQuery';
import {extractCallData} from './extractData';
import {UseChartsDataParams, UseChartsDataResult} from './types';

/**
 * Custom hook that combines data fetching and processing for charts.
 *
 * Fetches calls data based on the provided filters and processes it into
 * chart-friendly format using extractCallData.
 *
 * @param params - The query parameters including entity, project, filters, and page size
 * @returns Object containing processed chart data, loading state, and error information
 *
 * @example
 * const { data, isLoading, error } = useChartsData({
 *   entity: 'my-entity',
 *   project: 'my-project',
 *   filter: callsFilter,
 *   filterModelProp: gridFilterModel,
 *   pageSize: 250
 * });
 */
export const useChartsData = ({
  entity,
  project,
  filter,
  filterModelProp,
  pageSize = 250,
  sortModel,
}: UseChartsDataParams): UseChartsDataResult => {
  const columns = React.useMemo(
    () => [
      'display_name',
      'started_at',
      'ended_at',
      'exception',
      'id',
      'inputs',
      'output',
    ],
    []
  );

  const columnSet = React.useMemo(() => new Set(columns), [columns]);

  const sortCalls = React.useMemo(
    () =>
      sortModel ?? [{field: 'started_at', sort: 'desc' as GridSortDirection}],
    [sortModel]
  );

  const page = React.useMemo(
    () => ({
      pageSize,
      page: 0,
    }),
    [pageSize]
  );

  // Fetch calls data
  const calls = useCallsForQuery(
    entity,
    project,
    filter,
    filterModelProp,
    page,
    sortCalls,
    columnSet,
    columns
  );

  // Process call data into chart-friendly format
  const callData = React.useMemo(() => {
    return extractCallData(calls.result || []);
  }, [calls.result]);

  const isLoading = calls.loading || calls.costsLoading;
  const error =
    calls.primaryError || calls.costsError || calls.storageSizeError;

  return {
    data: callData,
    isLoading,
    error,
    refetch: calls.refetch,
  };
};
