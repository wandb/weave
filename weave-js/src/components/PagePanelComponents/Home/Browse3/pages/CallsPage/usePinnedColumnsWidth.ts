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
      if (!columnsState) {
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

      setPinnedWidths({
        left: leftWidth,
        right: rightWidth,
        total: leftWidth + rightWidth,
      });
    };

    // Calculate initially
    calculatePinnedWidths();

    // Subscribe to column state changes
    const unsubscribe = apiRef.current?.subscribeEvent?.(
      'columnWidthChange',
      calculatePinnedWidths
    );

    return () => {
      unsubscribe?.();
    };
  }, [apiRef, pinnedColumns]);

  return pinnedWidths;
};
