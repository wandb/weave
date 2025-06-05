import {
  GridFilterModel,
  GridLogicOperator,
  GridSortDirection,
} from '@mui/x-data-grid-pro';
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
import {
  chartAxisFields,
  extractCallData,
  ExtractedCallData,
} from './extractData';

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
  const {pageType} = useChartsState();
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
    () => [{field: 'started_at', sort: 'desc' as GridSortDirection}],
    []
  );
  const page = React.useMemo(
    () => ({
      pageSize: 500,
      page: 0,
    }),
    []
  );

  // First query: Get the evaluation root calls (standard behavior)
  const evalCalls = useCallsForQuery(
    entity,
    project,
    filter,
    filterModelProp,
    page,
    sortCalls,
    columnSet,
    columns
  );

  // Extract eval call IDs for the children query
  const evalCallIds = React.useMemo(() => {
    if (pageType !== 'evaluations' || !evalCalls.result || evalCalls.loading) {
      return [];
    }
    return evalCalls.result.map(call => call.callId);
  }, [pageType, evalCalls.result, evalCalls.loading]);

  // Filter for children query - specifically for predict_and_score operations
  const childrenFilter = React.useMemo((): WFHighLevelCallFilter => {
    if (evalCallIds.length === 0) {
      return {};
    }
    // For single eval call, use parentId filter
    return evalCallIds.length === 1 ? {parentId: evalCallIds[0]} : {};
  }, [evalCallIds]);

  // Children filter model for grid filtering - target predict_and_score specifically
  const childrenFilterModel = React.useMemo((): GridFilterModel => {
    const items = [];

    // Filter by parent IDs (multiple eval calls)
    if (evalCallIds.length > 1) {
      items.push({
        field: 'parent_id',
        operator: '(string): in',
        value: evalCallIds,
      });
    }

    // Always filter for predict_and_score operations
    if (evalCallIds.length > 0) {
      items.push({
        field: 'op_name',
        operator: '(string): contains',
        value: 'predict_and_score',
      });
    }

    return {
      items,
      logicOperator: GridLogicOperator.And,
    };
  }, [evalCallIds]);

  // Second query: Get children of evaluation calls (only when on evals page and we have eval calls)
  const childrenCalls = useCallsForQuery(
    entity,
    project,
    childrenFilter,
    childrenFilterModel,
    {
      pageSize: 500,
      page: 0,
    },
    sortCalls,
    columnSet,
    columns
  );

  // Process call data from both queries
  const {callData, evalChildrenData, traceIdToDisplayName} =
    React.useMemo(() => {
      const evalCallData = extractCallData(evalCalls.result || []);

      // Create trace ID to display name mapping for evaluations
      const traceIdMapping = new Map<string, string>();
      evalCallData.forEach(evalCall => {
        if (evalCall.traceId && evalCall.display_name) {
          traceIdMapping.set(evalCall.traceId, evalCall.display_name);
        }
      });

      if (pageType !== 'evaluations') {
        return {
          callData: evalCallData,
          evalChildrenData: new Map<string, ExtractedCallData[]>(),
          traceIdToDisplayName: traceIdMapping,
        };
      }

      // For evaluations, organize children by parent eval call
      const childrenByParent = new Map<string, ExtractedCallData[]>();

      // Initialize map with eval calls
      evalCallData.forEach(evalCall => {
        childrenByParent.set(evalCall.callId, []);
      });

      // Add children data if we have it
      if (childrenCalls.result) {
        const childrenCallData = extractCallData(childrenCalls.result);

        childrenCallData.forEach(childCall => {
          // Find the parent eval call for this child
          const parentEvalCall = evalCallData.find(
            evalCall => evalCall.traceId === childCall.traceId // Assuming parent relationship
          );

          if (parentEvalCall) {
            const enhancedChildCall = {
              ...childCall,
              evalParentTraceId: parentEvalCall.traceId,
              evalParentCallId: parentEvalCall.callId,
              // Override traceId for grouping purposes - use parent's traceId
              traceId: parentEvalCall.traceId,
            };
            childrenByParent
              .get(parentEvalCall.callId)!
              .push(enhancedChildCall);
          }
        });

        // After all children are added, populate prediction_index for each parent's children
        childrenByParent.forEach((children, parentCallId) => {
          // Sort children by start time to ensure consistent ordering
          children.sort(
            (a, b) =>
              new Date(a.started_at).getTime() -
              new Date(b.started_at).getTime()
          );

          // Assign prediction_index based on position in sorted array
          children.forEach((child, index) => {
            child.prediction_index = index;
          });
        });
      }

      return {
        callData: evalCallData,
        evalChildrenData: childrenByParent,
        traceIdToDisplayName: traceIdMapping,
      };
    }, [evalCalls.result, childrenCalls.result, pageType]);

  // console.log('traceIdToDisplayName', traceIdToDisplayName);

  // Chart data - for evaluations, show only predict_and_score children
  const chartData = React.useMemo(() => {
    if (pageType !== 'evaluations') {
      return callData;
    }

    // For evaluations, only show the predict_and_score children, not the eval root calls
    const predictAndScoreChildren: ExtractedCallData[] = [];
    evalChildrenData.forEach(children => {
      predictAndScoreChildren.push(...children);
    });

    return predictAndScoreChildren;
  }, [pageType, callData, evalChildrenData]);

  const isLoading =
    evalCalls.loading || (pageType === 'evaluations' && childrenCalls.loading);
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
          width: 8px;
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
      <div className="flex h-full w-full flex-col">
        <div className="flex-shrink-0 px-4 pb-0 pt-2">
          <div className="mx-16 flex items-center justify-between">
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
        </div>
        <div
          className="charts-scroll-container flex-1"
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
            overflowX: 'hidden',
            overflowY: 'auto',
            padding: '8px 16px 16px 16px',
            minHeight: 0,
          }}>
          {charts.length === 0 ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#8F8F8F',
                fontSize: 14,
                width: '100%',
                minHeight: 200,
                textAlign: 'center',
                padding: '40px 20px',
              }}>
              No charts available. Click "Add Chart" to create one.
            </div>
          ) : (
            charts.map(chart => {
              const yField = chartAxisFields.find(f => f.key === chart.yAxis);
              const baseTitle = yField ? yField.label : chart.yAxis;
              const chartTitle = baseTitle;
              return (
                <Chart
                  key={chart.id}
                  data={chartData}
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
                  evalChildrenData={
                    pageType === 'evaluations' ? evalChildrenData : undefined
                  }
                  groupByTraceId={pageType === 'evaluations'}
                  traceIdToDisplayName={traceIdToDisplayName}
                />
              );
            })
          )}
        </div>
        {drawerState.open && (
          <ChartDrawer
            open={drawerState.open}
            mode={drawerState.mode}
            initialConfig={drawerState.initialConfig}
            onClose={closeDrawer}
            onConfirm={handleConfirm}
            callData={chartData}
            entity={entity}
            project={project}
          />
        )}
      </div>
    </Tailwind>
  );
};

export const CallsCharts = (props: CallsChartsProps) => (
  <ChartsProvider entity={props.entity} project={props.project}>
    <CallsChartsInner {...props} />
  </ChartsProvider>
);
