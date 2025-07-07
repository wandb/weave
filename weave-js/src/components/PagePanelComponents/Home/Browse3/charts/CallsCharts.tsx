/*
  CallsCharts.tsx

  This file contains the CallsCharts component, which is used to display the charts for the calls page.
*/
import {GridFilterModel, GridSortModel} from '@mui/x-data-grid-pro';
import React from 'react';

import {Button} from '../../../../../components/Button';
import {WFHighLevelCallFilter} from '../pages/CallsPage/callsTableFilter';
import {
  callsChartsStyles,
  createDropdownOptionStyle,
  getDropdownTriggerHoverColor,
} from './CallsCharts.styles';
import {Chart} from './Chart';
import {ChartModal} from './ChartModal';
import {
  ChartsProvider,
  useChartsDispatch,
  useChartsState,
} from './ChartsContext';
import {ChartTypeSelectionDrawer} from './ChartTypeSelectionDrawer';
import {chartAxisFields} from './extractData';
import {ChartConfig} from './types';
import {useChartsData} from './useChartsData';

type CallsChartsProps = {
  entity: string;
  project: string;
  filterModelProp: GridFilterModel;
  filter: WFHighLevelCallFilter;
  sortModel?: GridSortModel;
};

const CallsChartsInner = ({
  entity,
  project,
  filter,
  filterModelProp,
  sortModel,
}: CallsChartsProps) => {
  const [pageSize, setPageSize] = React.useState(250);
  const [isDropdownOpen, setIsDropdownOpen] = React.useState(false);
  const [hoveredOption, setHoveredOption] = React.useState<number | null>(null);
  const [isDropdownTriggerHovered, setIsDropdownTriggerHovered] =
    React.useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);

  const pageSizeOptions = React.useMemo(
    () => [
      {value: 10, label: '10'},
      {value: 25, label: '25'},
      {value: 50, label: '50'},
      {value: 100, label: '100'},
      {value: 250, label: '250'},
      {value: 500, label: '500'},
      {value: 1000, label: '1000'},
    ],
    []
  );

  // Close dropdown when clicking outside the dropdown for selecting number of calls to show
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setIsDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handlePageSizeSelect = (option: {value: number; label: string}) => {
    setPageSize(option.value);
    setIsDropdownOpen(false);
  };

  const {data: callData, isLoading} = useChartsData({
    entity,
    project,
    filter,
    filterModelProp,
    pageSize,
    sortModel,
  });
  const {charts} = useChartsState();
  const dispatch = useChartsDispatch();

  const [typeSelectionDrawerOpen, setTypeSelectionDrawerOpen] =
    React.useState(false);
  const [pendingChartTypeSelection, setPendingChartTypeSelection] =
    React.useState<'scatter' | 'line' | 'bar' | null>(null);
  const [modalState, setModalState] = React.useState<
    | {open: false}
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

  const openTypeSelectionDrawer = () => {
    setTypeSelectionDrawerOpen(true);
  };

  const closeTypeSelectionDrawer = () => {
    setTypeSelectionDrawerOpen(false);
  };

  const handleChartTypeSelection = (plotType: 'scatter' | 'line' | 'bar') => {
    const newChartConfig = {
      ...defaultConfig,
      plotType,
    };
    setPendingChartTypeSelection(plotType);
    dispatch({
      type: 'ADD_CHART',
      payload: newChartConfig,
    });
    closeTypeSelectionDrawer();
  };

  const openEditModal = (id: string) => {
    const chart = charts.find(c => c.id === id);
    if (chart) {
      setModalState({
        open: true,
        mode: 'edit',
        initialConfig: {...chart},
        editId: id,
      });
    }
  };

  const closeModal = () => {
    setModalState({open: false});
  };

  const handleConfirm = (config: Partial<ChartConfig>) => {
    if (modalState.open && modalState.mode === 'edit' && modalState.editId) {
      dispatch({type: 'UPDATE_CHART', id: modalState.editId, payload: config});
    }
    closeModal();
  };

  const prevChartIdsRef = React.useRef(new Set(charts.map(c => c.id)));
  React.useEffect(() => {
    if (pendingChartTypeSelection && charts.length > 0) {
      const newCharts = charts.filter(
        chart => !prevChartIdsRef.current.has(chart.id)
      );
      const newChart = newCharts.find(
        chart => chart.plotType === pendingChartTypeSelection
      );
      if (newChart) {
        setPendingChartTypeSelection(null);
        setModalState({
          open: true,
          mode: 'edit',
          initialConfig: {...newChart},
          editId: newChart.id,
        });
      }
    }
    prevChartIdsRef.current = new Set(charts.map(c => c.id));
  }, [charts, pendingChartTypeSelection]);

  return (
    <div style={callsChartsStyles.container}>
      {/* Header */}
      <div style={callsChartsStyles.header}>
        <div style={callsChartsStyles.headerContent}>
          <div style={callsChartsStyles.headerLeft}>
            <span style={callsChartsStyles.headerText}>
              Charts showing data for
            </span>
            <div style={callsChartsStyles.dropdownContainer} ref={dropdownRef}>
              <span
                style={{
                  ...callsChartsStyles.dropdownTrigger,
                  color: getDropdownTriggerHoverColor(isDropdownTriggerHovered),
                }}
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                onMouseEnter={() => setIsDropdownTriggerHovered(true)}
                onMouseLeave={() => setIsDropdownTriggerHovered(false)}>
                {pageSize}
              </span>
              {isDropdownOpen && (
                <div style={callsChartsStyles.dropdownMenu}>
                  {pageSizeOptions.map(option => (
                    <div
                      key={option.value}
                      style={createDropdownOptionStyle(
                        pageSize === option.value,
                        hoveredOption === option.value
                      )}
                      onMouseEnter={() => setHoveredOption(option.value)}
                      onMouseLeave={() => setHoveredOption(null)}
                      onClick={() => handlePageSizeSelect(option)}>
                      {option.label}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <span style={callsChartsStyles.headerText}>calls</span>
          </div>
          <Button
            icon="add-new"
            variant="ghost"
            size="small"
            onClick={openTypeSelectionDrawer}>
            Add Chart
          </Button>
        </div>
      </div>

      {/* Scrollable charts container */}
      <div style={callsChartsStyles.chartsContainer}>
        {charts.length === 0 ? (
          <div style={callsChartsStyles.emptyState}>
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
                data={callData}
                height={260}
                xAxis={chart.xAxis}
                yAxis={chart.yAxis}
                plotType={chart.plotType || 'scatter'}
                binCount={chart.binCount}
                aggregation={chart.aggregation}
                title={chartTitle}
                chartId={chart.id}
                entity={entity}
                project={project}
                groupKeys={chart.groupKeys}
                isLoading={isLoading}
                onEdit={() => openEditModal(chart.id)}
                onRemove={() => dispatch({type: 'REMOVE_CHART', id: chart.id})}
                filter={filter}
              />
            );
          })
        )}
      </div>

      <ChartTypeSelectionDrawer
        open={typeSelectionDrawerOpen}
        onClose={closeTypeSelectionDrawer}
        onSelectType={handleChartTypeSelection}
      />

      {modalState.open && (
        <ChartModal
          open={modalState.open}
          mode="edit"
          initialConfig={modalState.initialConfig}
          onClose={closeModal}
          onConfirm={handleConfirm}
          callData={callData}
          entity={entity}
          project={project}
        />
      )}
    </div>
  );
};

export const CallsCharts = (props: CallsChartsProps) => (
  <ChartsProvider entity={props.entity} project={props.project}>
    <CallsChartsInner {...props} />
  </ChartsProvider>
);
