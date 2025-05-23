import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

import {GridFilterModel, GridSortDirection} from '@mui/x-data-grid-pro';
import React from 'react';
import RGL, {Layout, WidthProvider} from 'react-grid-layout';

import {TEAL_400} from '../../../../../common/css/color.styles';
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
      validLayouts[breakpoint] = charts.map(chart => {
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
        // Find a good position that doesn't overlap with existing charts
        const occupiedPositions = new Set(
          existingLayouts.map(l => `${l.x},${l.y}`)
        );
        
        let x = 0;
        let y = 0;
        
        // Find first available position
        while (occupiedPositions.has(`${x},${y}`)) {
          x += defaultW;
          if (x + defaultW > COLUMN_SIZES[breakpoint as keyof typeof COLUMN_SIZES]) {
            x = 0;
            y += defaultH;
          }
        }
        
        return {
          i: chart.id,
          x,
          y,
          w: Math.min(defaultW, COLUMN_SIZES[breakpoint as keyof typeof COLUMN_SIZES]),
          h: defaultH,
          minW: MIN_W,
          minH: MIN_H,
        };
      });
    });

    return validLayouts;
  }, [layouts, defaultLayouts, charts]);

  return (
    <Tailwind>
      <style>{`
        .react-grid-placeholder {
          background: ${TEAL_400} !important;
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
            onLayoutChange={(layout, allLayouts) => {
              dispatch({type: 'UPDATE_LAYOUTS', layouts: allLayouts});
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
