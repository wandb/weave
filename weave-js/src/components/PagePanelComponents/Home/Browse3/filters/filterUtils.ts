import {GridFilterItem} from '@mui/x-data-grid-pro';

import {FilterId} from './common';

// Global counter to ensure unique filter IDs
let globalFilterIdCounter = 0;

/**
 * Computes the next available filter ID using a global counter.
 * This ensures unique IDs even when filters are deleted and added.
 */
export const getNextFilterId = (items: GridFilterItem[]): number => {
  // Initialize counter based on existing items if this is the first call
  if (globalFilterIdCounter === 0 && items.length > 0) {
    const existingIds = items.map(item => {
      const id = item.id;
      if (id == null) {
        return 0;
      }
      return typeof id === 'number' ? id : parseInt(String(id), 10) || 0;
    });
    globalFilterIdCounter = Math.max(...existingIds) + 1;
  }

  return globalFilterIdCounter++;
};

/**
 * Combines range filters into a single filter item for each field.
 * - Groups filters by field
 * - Combines before and after filters into a single range filter
 * - Keeps track of active edit IDs
 * - Returns combined items and active edit IDs
 */
export const combineRangeFilters = (
  items: GridFilterItem[],
  activeEditId: FilterId | null
): {items: GridFilterItem[]; activeIds: Set<FilterId>} => {
  const result: GridFilterItem[] = [];
  const dateRanges = new Map<
    string,
    {before?: GridFilterItem; after?: GridFilterItem}
  >();
  const activeIds = new Set<FilterId>();

  items.forEach(item => {
    if (
      item.operator === '(date): before' ||
      item.operator === '(date): after'
    ) {
      const range = dateRanges.get(item.field) || {};
      item.operator === '(date): before'
        ? (range.before = item)
        : (range.after = item);
      dateRanges.set(item.field, range);
    } else {
      result.push(item);
    }
  });

  dateRanges.forEach((range, field) => {
    if (range.before && range.after) {
      const afterDate = new Date(range.after.value);
      const beforeDate = new Date(range.before.value);

      if (afterDate < beforeDate) {
        const combinedFilter = {
          ...range.before,
          operator: '(date): range',
          value: {before: range.before.value, after: range.after.value},
        };
        result.push(combinedFilter);

        if (
          activeEditId === range.before.id ||
          activeEditId === range.after.id
        ) {
          activeIds.add(range.before.id);
          activeIds.add(range.after.id);
        }
      } else {
        result.push(range.after, range.before);
      }
    } else {
      if (range.before) {
        result.push(range.before);
      }
      if (range.after) {
        result.push(range.after);
      }
    }
  });

  return {items: result, activeIds};
};
