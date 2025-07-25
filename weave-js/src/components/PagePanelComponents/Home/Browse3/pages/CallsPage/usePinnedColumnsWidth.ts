import {GridApi, GridPinnedColumnFields} from '@mui/x-data-grid-pro';
import {useEffect, useState} from 'react';

interface PinnedColumnsWidth {
  left: number;
  right: number;
  total: number;
}

/**
 * Hook to calculate the total width of pinned columns in a DataGrid
 * @param apiRef - The DataGrid API reference
 * @param pinnedColumns - The current pinned columns configuration
 * @returns Object containing left, right, and total pinned column widths
 */
export const usePinnedColumnsWidth = (
  apiRef: React.MutableRefObject<GridApi>,
  pinnedColumns: GridPinnedColumnFields | undefined
): PinnedColumnsWidth => {
  const [pinnedWidths, setPinnedWidths] = useState<PinnedColumnsWidth>({
    left: 0,
    right: 0,
    total: 0,
  });

  useEffect(() => {
    const calculatePinnedWidths = () => {
      if (!apiRef.current) {
        return;
      }

      const columnsState = apiRef.current.state.columns;
      if (!columnsState || !columnsState.lookup) {
        return;
      }

      let leftWidth = 0;
      let rightWidth = 0;

      // Calculate left pinned columns width
      if (pinnedColumns?.left) {
        pinnedColumns.left.forEach(field => {
          const column = columnsState.lookup[field];
          if (column) {
            leftWidth += column.computedWidth || column.width || 0;
          }
        });
      }

      // Calculate right pinned columns width
      if (pinnedColumns?.right) {
        pinnedColumns.right.forEach(field => {
          const column = columnsState.lookup[field];
          if (column) {
            rightWidth += column.computedWidth || column.width || 0;
          }
        });
      }

      const newWidths = {
        left: leftWidth,
        right: rightWidth,
        total: leftWidth + rightWidth,
      };

      // Only update if widths have actually changed
      setPinnedWidths(prev => {
        if (prev.left !== newWidths.left || prev.right !== newWidths.right || prev.total !== newWidths.total) {
          return newWidths;
        }
        return prev;
      });
    };

    // Use a timeout to ensure the grid is fully initialized before calculating widths
    const timeoutId = setTimeout(calculatePinnedWidths, 0);

    // Subscribe to multiple events to ensure we catch width changes
    const unsubscribes: (() => void)[] = [];

    if (apiRef.current) {
      // Subscribe to column width changes
      const unsubscribeWidth = apiRef.current.subscribeEvent?.('columnWidthChange', calculatePinnedWidths);
      if (unsubscribeWidth) unsubscribes.push(unsubscribeWidth);

      // Subscribe to columns order changes (including pinning)
      const unsubscribeOrder = apiRef.current.subscribeEvent?.('columnOrderChange', calculatePinnedWidths);
      if (unsubscribeOrder) unsubscribes.push(unsubscribeOrder);

      // Subscribe to column visibility changes
      const unsubscribeVisibility = apiRef.current.subscribeEvent?.('columnVisibilityModelChange', calculatePinnedWidths);
      if (unsubscribeVisibility) unsubscribes.push(unsubscribeVisibility);

      // Subscribe to rows set event to recalculate when data changes
      const unsubscribeRows = apiRef.current.subscribeEvent?.('rowsSet', calculatePinnedWidths);
      if (unsubscribeRows) unsubscribes.push(unsubscribeRows);
    }

    return () => {
      clearTimeout(timeoutId);
      unsubscribes.forEach(unsub => unsub());
    };
  }, [apiRef, pinnedColumns]);

  return pinnedWidths;
};
