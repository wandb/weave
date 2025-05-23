import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

import {GridFilterModel, GridSortDirection} from '@mui/x-data-grid-pro';
import React from 'react';
import RGL, {Layout, WidthProvider} from 'react-grid-layout';

import {TEAL_300, TEAL_600} from '../../../../../common/css/color.styles';
import {Button} from '../../../../../components/Button';
import {Tailwind} from '../../../../Tailwind';
import {WFHighLevelCallFilter} from '../pages/CallsPage/callsTableFilter';
import {useCallsForQuery} from '../pages/CallsPage/callsTableQuery';
import {Chart} from './Chart';
import {
  CHART_BREAKPOINTS,
  ChartConfig,
  ChartsProvider,
  useChartsDispatch,
  useChartsState,
} from './ChartsContext';
import {ChartDrawer} from './drawer/ChartDrawer';
import {chartAxisFields, extractCallData} from './extractData';

const ResponsiveGridLayout = WidthProvider(RGL.Responsive);

const COLUMN_SIZES = {lg: 12, xxs: 1};

type CallsChartsProps = {
  entity: string;
  project: string;
  filterModelProp: GridFilterModel;
  filter: WFHighLevelCallFilter;
};

// Constants for grid layout
const GRID_ROW_HEIGHT = 24;
const MIN_W = 3;
const MIN_H = 12; // 300px minimum height (12 * 24px = 312px)

const CallsChartsInner = ({
  entity,
  project,
  filter,
  filterModelProp,
}: CallsChartsProps) => {
  // Track the previous layouts to detect which chart was resized
  const prevLayoutsRef = React.useRef<Record<string, Layout[]>>({});
  const columns = React.useMemo(
    () => ['started_at', 'ended_at', 'exception', 'id'],
    []
  );
  const columnSet = React.useMemo(() => new Set(columns), [columns]);
  const sortCalls = React.useMemo(
    () => [{field: 'started_at', sort: 'desc' as GridSortDirection}],
    []
  );
  const page = React.useMemo(
    () => ({
      pageSize: 1000,
      page: 0,
    }),
    []
  );

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

  const callData = extractCallData(calls.result || []);
  const {charts, layouts} = useChartsState();
  const dispatch = useChartsDispatch();

  const [drawerState, setDrawerState] = React.useState<
    | {open: false}
    | {open: true; mode: 'create'; initialConfig: Partial<ChartConfig>}
    | {
        open: true;
        mode: 'edit';
        initialConfig: Partial<ChartConfig>;
        editId: string;
      }
  >({open: false});

  const defaultConfig = React.useMemo(
    () => ({
      xAxis: chartAxisFields[0]?.key || 'started_at',
      yAxis: chartAxisFields.find(f => f.type === 'number')?.key || 'latency',
      plotType: 'scatter' as const,
      binCount: 20,
      aggregation: 'average' as const,
    }),
    []
  );

  const openCreateDrawer = () => {
    setDrawerState({
      open: true,
      mode: 'create',
      initialConfig: {...defaultConfig},
    });
  };

  const openEditDrawer = (id: string) => {
    const chart = charts.find(c => c.id === id);
    if (chart) {
      setDrawerState({
        open: true,
        mode: 'edit',
        initialConfig: {...chart},
        editId: id,
      });
    }
  };

  const closeDrawer = () => {
    setDrawerState({open: false});
  };

  const handleConfirm = (config: Partial<ChartConfig>) => {
    if (drawerState.open && drawerState.mode === 'edit' && drawerState.editId) {
      dispatch({type: 'UPDATE_CHART', id: drawerState.editId, payload: config});
    } else if (drawerState.open && drawerState.mode === 'create') {
      dispatch({type: 'ADD_CHART', payload: config});
    }
    closeDrawer();
  };

  // Default layouts if none are persisted
  const defaultW = 4;
  const defaultH = 12; // ~300px height (12 * 24px = 312px)
  const defaultLayouts = React.useMemo(() => {
    const layouts: Record<string, Layout[]> = {};

    Object.keys(CHART_BREAKPOINTS).forEach(breakpoint => {
      layouts[breakpoint] = charts.map((chart, i) => ({
        i: chart.id,
        x:
          (i * defaultW) %
          COLUMN_SIZES[breakpoint as keyof typeof COLUMN_SIZES],
        y:
          Math.floor(
            (i * defaultW) /
              COLUMN_SIZES[breakpoint as keyof typeof COLUMN_SIZES]
          ) * defaultH,
        w: Math.min(
          defaultW,
          COLUMN_SIZES[breakpoint as keyof typeof COLUMN_SIZES]
        ),
        h: defaultH,
        minW: MIN_W,
        minH: MIN_H,
      }));
    });

    return layouts;
  }, [charts]);

  // Function to reflow layouts into a row-based format with height syncing
  const reflowLayout = (
    items: Layout[], 
    cols: number, 
    syncHeights: boolean = true,
    resizedItemId?: string
  ): Layout[] => {
    if (items.length === 0) return [];

    // Sort items by their current position (y first, then x)
    const sortedItems = [...items].sort((a, b) => {
      if (a.y !== b.y) return a.y - b.y;
      return a.x - b.x;
    });

    // Create rows based on current layout
    const rows: Array<{y: number; height: number; items: Layout[]; hasResizedItem: boolean}> = [];
    let currentRow: {y: number; height: number; items: Layout[]; hasResizedItem: boolean} | null = null;

    sortedItems.forEach(item => {
      // Check if item belongs to current row (similar y position)
      if (!currentRow || Math.abs(item.y - currentRow.y) > 2) {
        // Start a new row
        currentRow = {
          y: item.y,
          height: item.h,
          items: [item],
          hasResizedItem: item.i === resizedItemId,
        };
        rows.push(currentRow);
      } else {
        currentRow.items.push(item);
        if (item.i === resizedItemId) {
          currentRow.hasResizedItem = true;
          // If this is the resized item, use its height for the row
          currentRow.height = item.h;
        } else if (!currentRow.hasResizedItem) {
          // Only update with max if we haven't found the resized item yet
          currentRow.height = Math.max(currentRow.height, item.h);
        }
      }
    });

    // Now reflow items within each row and pack rows tightly
    const reflowedItems: Layout[] = [];
    let currentY = 0;

    rows.forEach(row => {
      // Sort items in the row by x position
      row.items.sort((a, b) => a.x - b.x);
      
      // Pack items in the row from left to right
      let currentX = 0;
      const rowHeight = row.height;

      row.items.forEach(item => {
        // If item doesn't fit in current row, wrap to next row
        if (currentX + item.w > cols) {
          currentX = 0;
          currentY += rowHeight;
        }

        reflowedItems.push({
          ...item,
          x: currentX,
          y: currentY,
          h: syncHeights ? rowHeight : item.h, // Sync heights if enabled
        });

        currentX += item.w;
      });

      // Move to next row
      currentY += rowHeight;
    });

    return reflowedItems;
  };


  const effectiveLayouts = React.useMemo(() => {
    // Make sure we only use layouts that match our breakpoints
    if (!layouts || Object.keys(layouts).length === 0) {
      return defaultLayouts;
    }

    const validLayouts: Record<string, Layout[]> = {};
    Object.keys(CHART_BREAKPOINTS).forEach(breakpoint => {
      const existingLayouts = layouts[breakpoint] || [];
      const defaultLayoutsForBreakpoint = defaultLayouts[breakpoint] || [];
      
      // Create a map of existing layouts by chart id
      const existingLayoutMap = new Map(existingLayouts.map(l => [l.i, l]));
      
      // For each chart, use existing layout if available, otherwise use default
      const layoutItems = charts.map(chart => {
        const existing = existingLayoutMap.get(chart.id);
        if (existing) {
          return existing;
        }
        
        // Find the default layout for this chart
        const defaultLayout = defaultLayoutsForBreakpoint.find(l => l.i === chart.id);
        if (defaultLayout) {
          return defaultLayout;
        }
        
        // If no default layout exists (new chart), create one
        return {
          i: chart.id,
          x: 0,
          y: 0,
          w: Math.min(defaultW, COLUMN_SIZES[breakpoint as keyof typeof COLUMN_SIZES]),
          h: defaultH,
          minW: MIN_W,
          minH: MIN_H,
        };
      });

      // Reflow the layout to ensure row-based alignment with height syncing
      validLayouts[breakpoint] = reflowLayout(
        layoutItems,
        COLUMN_SIZES[breakpoint as keyof typeof COLUMN_SIZES],
        true // Enable height syncing
      );
    });

    return validLayouts;
  }, [layouts, defaultLayouts, charts]);

  // Update the previous layouts reference when layouts change
  React.useEffect(() => {
    prevLayoutsRef.current = effectiveLayouts;
  }, [effectiveLayouts]);

  return (
    <Tailwind>
      <style>{`
        .react-grid-placeholder {
          background: ${TEAL_300} !important;
          border: dashed 1px ${TEAL_600} !important;
        }
      `}</style>
      <div className="w-full min-h-screen overflow-auto bg-moon-50">
        <div className="px-4 pb-4 pt-2">
          <div className="mb-2 flex items-center justify-between">
            <span className="mr-2 text-base font-semibold text-moon-750">
              Charts
            </span>
            <Button
              icon="add-new"
              variant="secondary"
              size="small"
              onClick={openCreateDrawer}
            />
          </div>
          <ResponsiveGridLayout
            className="layout"
            layouts={effectiveLayouts}
            breakpoints={CHART_BREAKPOINTS}
            cols={COLUMN_SIZES}
            rowHeight={GRID_ROW_HEIGHT}
            draggableHandle=".drag-handle"
            isResizable
            isDraggable
            margin={[8, 8]}
            compactType="horizontal"
            preventCollision={false}
            isDroppable={false}
            onLayoutChange={(layout, allLayouts) => {
              // Detect which chart was resized by comparing with previous layouts
              let resizedItemId: string | undefined;
              
              // Check each breakpoint to find the resized item
              Object.keys(allLayouts).forEach(breakpoint => {
                const currentLayouts = allLayouts[breakpoint];
                const previousLayouts = prevLayoutsRef.current[breakpoint] || [];
                
                currentLayouts.forEach(currentItem => {
                  const prevItem = previousLayouts.find(p => p.i === currentItem.i);
                  if (prevItem && prevItem.h !== currentItem.h) {
                    resizedItemId = currentItem.i;
                  }
                });
              });

              // Apply reflow to ensure row-based alignment with height syncing
              const reflowedLayouts: Record<string, Layout[]> = {};
              Object.keys(allLayouts).forEach(breakpoint => {
                reflowedLayouts[breakpoint] = reflowLayout(
                  allLayouts[breakpoint],
                  COLUMN_SIZES[breakpoint as keyof typeof COLUMN_SIZES],
                  true, // Enable height syncing
                  resizedItemId // Pass the resized item ID
                );
              });
              
              // Update the previous layouts reference
              prevLayoutsRef.current = reflowedLayouts;
              
              dispatch({type: 'UPDATE_LAYOUTS', layouts: reflowedLayouts});
            }}>
            {charts.map(chart => {
              const yField = chartAxisFields.find(f => f.key === chart.yAxis);
              const chartTitle = yField ? yField.label : chart.yAxis;
              return (
                <div key={chart.id}>
                  <Chart
                    data={callData}
                    xAxis={chart.xAxis}
                    yAxis={chart.yAxis}
                    plotType={chart.plotType || 'scatter'}
                    binCount={chart.binCount}
                    aggregation={chart.aggregation}
                    groupKey={chart.groupKey}
                    title={chartTitle}
                    onEdit={() => openEditDrawer(chart.id)}
                    onRemove={() =>
                      dispatch({type: 'REMOVE_CHART', id: chart.id})
                    }
                  />
                </div>
              );
            })}
          </ResponsiveGridLayout>
        </div>
        {drawerState.open && (
          <ChartDrawer
            open={drawerState.open}
            mode={drawerState.mode}
            initialConfig={drawerState.initialConfig}
            onClose={closeDrawer}
            onConfirm={handleConfirm}
            callData={callData}
          />
        )}
      </div>
    </Tailwind>
  );
};

export const CallsCharts = (props: CallsChartsProps) => (
  <ChartsProvider>
    <CallsChartsInner {...props} />
  </ChartsProvider>
);
