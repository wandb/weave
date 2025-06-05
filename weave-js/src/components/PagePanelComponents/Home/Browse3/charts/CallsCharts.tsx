import {GridFilterModel, GridSortDirection} from '@mui/x-data-grid-pro';
import React from 'react';

import {Button} from '../../../../../components/Button';
import {Tailwind} from '../../../../Tailwind';
import {WFHighLevelCallFilter} from '../pages/CallsPage/callsTableFilter';
import {useCallsForQuery} from '../pages/CallsPage/callsTableQuery';
import {Chart} from './Chart';
import {
  ChartConfig,
  ChartsProvider,
  useChartsDispatch,
  useChartsState,
} from './ChartsContext';
import {ChartDrawer} from './drawer/ChartDrawer';
import {chartAxisFields, extractCallData} from './extractData';

type CallsChartsProps = {
  entity: string;
  project: string;
  filterModelProp: GridFilterModel;
  filter: WFHighLevelCallFilter;
};

const CallsChartsInner = ({
  entity,
  project,
  filter,
  filterModelProp,
}: CallsChartsProps) => {
  const columns = React.useMemo(
    () => ['started_at', 'ended_at', 'exception', 'id', 'inputs', 'output'],
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
  const isLoading = calls.loading;
  const {charts} = useChartsState();
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

  return (
    <Tailwind>
      <style>{`
        .charts-scroll-container {
          scrollbar-width: thin;
          scrollbar-color: #cbd5e0 #f7fafc;
        }
        .charts-scroll-container::-webkit-scrollbar {
          height: 8px;
        }
        .charts-scroll-container::-webkit-scrollbar-track {
          background: #f7fafc;
          border-radius: 4px;
        }
        .charts-scroll-container::-webkit-scrollbar-thumb {
          background: #cbd5e0;
          border-radius: 4px;
        }
        .charts-scroll-container::-webkit-scrollbar-thumb:hover {
          background: #a0aec0;
        }
      `}</style>
      <div className="w-full">
        <div className="px-12 pb-0 pt-2">
          <div className="mb-2 flex items-center justify-between">
            <span className="mr-2 text-base font-semibold text-moon-750">
              Charts
            </span>
            <Button
              icon="add-new"
              variant="ghost"
              size="small"
              onClick={openCreateDrawer}>
              Add Chart
            </Button>
          </div>
          <div
            className="charts-scroll-container"
            style={{
              display: 'flex',
              gap: 16,
              overflowX: 'auto',
              overflowY: 'hidden',
              padding: '8px 0 16px 0',
              minHeight: 320,
            }}>
            {charts.length === 0 ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#8F8F8F',
                  fontSize: 14,
                  minWidth: '100%',
                  minHeight: 300,
                }}>
                No charts available. Click "Add Chart" to create one.
              </div>
            ) : (
              charts.map(chart => {
                const yField = chartAxisFields.find(f => f.key === chart.yAxis);
                const chartTitle = yField ? yField.label : chart.yAxis;
                return (
                  <Chart
                    key={chart.id}
                    data={callData}
                    xAxis={chart.xAxis}
                    yAxis={chart.yAxis}
                    plotType={chart.plotType || 'scatter'}
                    binCount={chart.binCount}
                    aggregation={chart.aggregation}
                    title={chartTitle}
                    chartId={chart.id}
                    entity={entity}
                    project={project}
                    colorGroupKey={chart.colorGroupKey}
                    isLoading={isLoading}
                    onEdit={() => openEditDrawer(chart.id)}
                    onRemove={() =>
                      dispatch({type: 'REMOVE_CHART', id: chart.id})
                    }
                    filter={filter}
                  />
                );
              })
            )}
          </div>
        </div>
        {drawerState.open && (
          <ChartDrawer
            open={drawerState.open}
            mode={drawerState.mode}
            initialConfig={drawerState.initialConfig}
            onClose={closeDrawer}
            onConfirm={handleConfirm}
            callData={callData}
            entity={entity}
            project={project}
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
