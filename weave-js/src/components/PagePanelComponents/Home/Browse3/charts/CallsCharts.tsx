import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Modal,
  Select,
  Typography,
} from '@mui/material';
import {GridFilterModel, GridSortModel} from '@mui/x-data-grid-pro';
import React, {useMemo, useRef, useState} from 'react';
import {Responsive, WidthProvider} from 'react-grid-layout';

import {MOON_400} from '../../../../../common/css/color.styles';
import * as userEvents from '../../../../../integrations/analytics/userEvents';
import {Button} from '../../../../Button';
import {IconInfo} from '../../../../Icon';
import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {Tailwind} from '../../../../Tailwind';
import {WFHighLevelCallFilter} from '../pages/CallsPage/callsTableFilter';
import {useCallsForQuery} from '../pages/CallsPage/callsTableQuery';
import {ChartConfigProvider, useChartConfigContext} from './ChartConfigContext';
import {ScatterPlot} from './Charts';
import {ChartConfig} from './ChartTypes';
import {extractCallData, ExtractedCallData} from './extractCallData';

const ResponsiveReactGridLayout = WidthProvider(Responsive);

// Available axis options - allow any field for either axis
type AxisOption =
  | 'started_at'
  | 'ended_at'
  | 'latency'
  | 'cost'
  | 'total_tokens';
type PlotType = 'scatter';

const allAxisOptions: {value: keyof ExtractedCallData; label: string}[] = [
  {value: 'started_at', label: 'Start Time'},
  {value: 'ended_at', label: 'End Time'},
  {value: 'latency', label: 'Latency'},
  {value: 'cost', label: 'Cost'},
  {value: 'prompt_tokens', label: 'Prompt Tokens'},
  {value: 'completion_tokens', label: 'Completion Tokens'},
  {value: 'total_tokens', label: 'Total Tokens'},
];

type CallsChartsProps = {
  entity: string;
  project: string;
  filterModelProp: GridFilterModel;
  filter: WFHighLevelCallFilter;
};

// Modal component for configuring charts
const ChartConfigModal = ({
  config,
  onSave,
  onCancel,
  isNew = false,
  processedData,
  isLoading,
}: {
  config: ChartConfig;
  onSave: (config: ChartConfig) => void;
  onCancel: () => void;
  isNew?: boolean;
  processedData: any[];
  isLoading: boolean;
}) => {
  const [xAxis, setXAxis] = useState(config.xAxis);
  const [yAxis, setYAxis] = useState(config.yAxis);
  const [plotType, setPlotType] = useState(config.plotType);

  // Use all fields for both X and Y axes
  const xAxisOptions = allAxisOptions;
  const yAxisOptions = allAxisOptions;

  // Available plot type options
  const plotTypeOptions: {value: PlotType; label: string}[] = [
    {value: 'scatter', label: 'Scatter Plot'},
  ];

  const handleSave = () => {
    onSave({
      ...config,
      xAxis,
      yAxis,
      plotType,
      xMin: undefined,
      xMax: undefined,
      yMin: undefined,
      yMax: undefined,
    });
  };

  // Generate a preview config for the chart
  const previewConfig = {
    ...config,
    xAxis,
    yAxis,
    plotType,
  };

  // Chart preview component
  const ChartPreview = () => {
    if (isLoading) {
      return (
        <div className="flex h-64 items-center justify-center">
          <WaveLoader size="small" />
        </div>
      );
    }

    if (!processedData || processedData.length === 0) {
      return (
        <div className="flex h-64 items-center justify-center">
          <div className="flex flex-col items-center justify-center">
            <IconInfo color={MOON_400} />
            <div className="text-moon-500">No data available for preview</div>
          </div>
        </div>
      );
    }

    // Filter data based on the selected X and Y axes
    const filteredData = processedData
      .filter(item => item[xAxis] != null && item[yAxis] != null)
      .map(item => ({
        started_at: item[xAxis],
        [yAxis]: item[yAxis],
      }));

    if (filteredData.length === 0) {
      return (
        <div className="flex h-64 items-center justify-center">
          <div className="flex flex-col items-center justify-center">
            <IconInfo color={MOON_400} />
            <div className="text-moon-500">
              No {yAxis.replace(/_/g, ' ')} data available for the selected
              calls
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="h-64 w-full bg-white">
        <Typography variant="subtitle1" sx={{mb: 1, fontWeight: 500}}>
          Chart Preview
        </Typography>
        <div className="h-56 rounded-lg border border-moon-250 bg-white p-3">
          <CustomChart
            chartData={filteredData}
            height={200}
            plotType={plotType as 'scatter'}
            yAxisField={yAxis as AxisOption}
            config={previewConfig}
          />
        </div>
      </div>
    );
  };

  const modalStyle = {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: '80%',
    maxWidth: '1000px',
    bgcolor: 'background.paper',
    boxShadow: 24,
    p: 4,
    borderRadius: 2,
    maxHeight: '90vh',
    overflow: 'auto',
  };

  return (
    <Modal
      open={true}
      onClose={onCancel}
      aria-labelledby="chart-config-modal"
      aria-describedby="configure-chart-settings">
      <Box sx={modalStyle}>
        <Typography
          id="chart-config-modal"
          variant="h5"
          component="h3"
          sx={{mb: 3}}>
          {isNew ? 'Add New Chart' : 'Edit Chart'}
        </Typography>

        <Box
          sx={{
            mb: 3,
            display: 'grid',
            gridTemplateColumns: {xs: '1fr', md: '1fr 1fr 1fr'},
            gap: 3,
          }}>
          <FormControl fullWidth>
            <InputLabel id="plot-type-label">Plot Type</InputLabel>
            <Select
              labelId="plot-type-label"
              value={plotType}
              label="Plot Type"
              onChange={e => setPlotType(e.target.value as PlotType)}>
              {plotTypeOptions.map(option => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth>
            <InputLabel id="x-axis-label">X Axis</InputLabel>
            <Select
              labelId="x-axis-label"
              value={xAxis}
              label="X Axis"
              onChange={e => setXAxis(e.target.value as AxisOption)}>
              {xAxisOptions.map(option => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth>
            <InputLabel id="y-axis-label">Y Axis</InputLabel>
            <Select
              labelId="y-axis-label"
              value={yAxis}
              label="Y Axis"
              onChange={e => setYAxis(e.target.value as AxisOption)}>
              {yAxisOptions.map(option => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {plotType === 'bar' && (
          <Box sx={{mt: 2, display: 'flex', gap: 2}}>
            <FormControl fullWidth>
              <InputLabel shrink htmlFor="min-bins-input">
                Min Bins
              </InputLabel>
              <input
                id="min-bins-input"
                type="number"
                min={1}
                max={100}
                value={config.minBins ?? 10}
                onChange={e =>
                  onSave({...config, minBins: Number(e.target.value)})
                }
                style={{
                  width: '100%',
                  padding: '8px',
                  fontSize: '16px',
                  borderRadius: '4px',
                  border: '1px solid #ccc',
                }}
              />
            </FormControl>
            <FormControl fullWidth>
              <InputLabel id="aggregation-label">Aggregation</InputLabel>
              <Select
                labelId="aggregation-label"
                value={config.aggregation ?? 'sum'}
                label="Aggregation"
                onChange={e =>
                  onSave({...config, aggregation: e.target.value as any})
                }>
                {['sum', 'avg', 'count', 'min', 'max'].map(val => (
                  <MenuItem key={val} value={val}>
                    {val}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>
        )}
        {plotType === 'line' && (
          <Box sx={{mt: 2, display: 'flex', gap: 2}}>
            <FormControl fullWidth>
              <InputLabel id="aggregation-label-line">Aggregation</InputLabel>
              <Select
                labelId="aggregation-label-line"
                value={config.aggregation ?? 'sum'}
                label="Aggregation"
                onChange={e =>
                  onSave({...config, aggregation: e.target.value as any})
                }>
                {['sum', 'avg', 'count', 'min', 'max'].map(val => (
                  <MenuItem key={val} value={val}>
                    {val}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel shrink htmlFor="interval-minutes-input">
                Interval (minutes)
              </InputLabel>
              <input
                id="interval-minutes-input"
                type="number"
                min={1}
                max={1440}
                value={config.intervalMinutes ?? 60}
                onChange={e =>
                  onSave({...config, intervalMinutes: Number(e.target.value)})
                }
                style={{
                  width: '100%',
                  padding: '8px',
                  fontSize: '16px',
                  borderRadius: '4px',
                  border: '1px solid #ccc',
                }}
              />
            </FormControl>
          </Box>
        )}

        <Box sx={{mt: 4, borderRadius: 2, overflow: 'hidden'}}>
          <ChartPreview />
        </Box>

        <Box sx={{mt: 4, display: 'flex', justifyContent: 'flex-end', gap: 2}}>
          <Button
            variant="secondary"
            onClick={onCancel}
            style={{padding: '8px 16px'}}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            style={{padding: '8px 16px', backgroundColor: 'teal.500'}}>
            {isNew ? 'Add Chart' : 'Save Changes'}
          </Button>
        </Box>
      </Box>
    </Modal>
  );
};

// Custom chart component that supports different plot types
const CustomChart = ({
  chartData,
  height,
  plotType,
  yAxisField,
  config,
}: {
  chartData: any[];
  height: number | string;
  plotType: PlotType;
  yAxisField: AxisOption;
  config: ChartConfig;
}) => {
  if (!chartData || chartData.length === 0) {
    return (
      <div
        style={{
          height: typeof height === 'number' ? `${height}px` : height,
        }}></div>
    );
  }

  const xDomain =
    config.xMin !== undefined || config.xMax !== undefined
      ? [config.xMin, config.xMax]
      : undefined;

  const yDomain =
    config.yMin !== undefined || config.yMax !== undefined
      ? [config.yMin, config.yMax]
      : undefined;

  // Map data to TimestampPoint[] for generic chart components
  const mappedData = chartData
    .map(item => ({
      started_at: item.started_at || item[config.xAxis],
      [yAxisField]: item[yAxisField],
    }))
    .filter(item => item[yAxisField] != null);

  if (mappedData.length === 0) {
    return (
      <div
        style={{height: typeof height === 'number' ? `${height}px` : height}}>
        No data available
      </div>
    );
  }

  return (
    <ScatterPlot
      data={mappedData}
      height={height}
      xLabel={config.xAxis}
      yLabel={yAxisField}
      xDomain={xDomain}
      yDomain={yDomain}
    />
  );
};

// Chart display component
const ChartDisplay = ({
  isLoading,
  processedData,
  config,
  onDelete,
  onEditConfig,
}: {
  isLoading: boolean;
  processedData: any[];
  config: ChartConfig;
  onDelete: () => void;
  onEditConfig: () => void;
}) => {
  const CHART_CONTAINER_STYLES =
    'flex-1 rounded-lg border border-moon-250 bg-white p-10 relative flex flex-col min-h-0';
  const CHART_TITLE_STYLES =
    'ml-12 mt-8 text-base font-semibold text-moon-750 flex justify-between items-center';
  const LOADING_CONTAINER_STYLES = `flex flex-1 items-center justify-center`;

  let chart = null;
  if (isLoading) {
    chart = (
      <div className={LOADING_CONTAINER_STYLES}>
        <WaveLoader size="small" />
      </div>
    );
  } else if (processedData.length > 0) {
    // Filter data based on the selected X and Y axes
    const filteredData = processedData
      .filter(item => item[config.xAxis] != null && item[config.yAxis] != null)
      .map(item => ({
        started_at: item[config.xAxis],
        [config.yAxis]: item[config.yAxis],
      }));

    if (filteredData.length > 0) {
      chart = (
        <CustomChart
          chartData={filteredData}
          height="100%"
          plotType={config.plotType as 'scatter'}
          yAxisField={config.yAxis as AxisOption}
          config={config}
        />
      );
    } else {
      chart = (
        <div className={LOADING_CONTAINER_STYLES}>
          <div className="flex flex-col items-center justify-center">
            <IconInfo color={MOON_400} />
            <div className="text-moon-500">
              No {config.yAxis.replace(/_/g, ' ')} data available for the
              selected calls
            </div>
          </div>
        </div>
      );
    }
  } else {
    chart = (
      <div className={LOADING_CONTAINER_STYLES}>
        <div className="flex flex-col items-center justify-center">
          <IconInfo color={MOON_400} />
          <div className="text-moon-500">
            No data available for the selected time frame
          </div>
        </div>
      </div>
    );
  }

  // Generate title from X and Y axes
  const getChartTitle = () => {
    // Find the label for the selected axis option
    const getAxisLabel = (axisValue: AxisOption) => {
      const option = allAxisOptions.find(opt => opt.value === axisValue);
      return option ? option.label : axisValue.replace(/_/g, ' ');
    };

    const xAxisLabel = getAxisLabel(config.xAxis as AxisOption);
    const yAxisLabel = getAxisLabel(config.yAxis as AxisOption);

    return `${yAxisLabel} vs ${xAxisLabel}`;
  };

  return (
    <div className={CHART_CONTAINER_STYLES}>
      <div className={CHART_TITLE_STYLES}>
        <span>{getChartTitle()}</span>
        <div className="flex space-x-2">
          <Button
            icon="settings"
            variant="ghost"
            onClick={onEditConfig}
            aria-label="Edit chart settings"
          />
          <Button
            icon="delete"
            variant="ghost"
            onClick={onDelete}
            aria-label="Delete chart"
          />
        </div>
      </div>
      <div className="flex min-h-0 flex-1 flex-col">{chart}</div>
    </div>
  );
};

// Helper to create a new chart config
const createDefaultChartConfig = (): ChartConfig => ({
  id: Math.random().toString(36).slice(2),
  xAxis: 'started_at',
  yAxis: 'latency',
  plotType: 'scatter',
  height: 300,
  x: 0,
  y: 0,
  w: 4,
  h: 4,
});

// Default chart configurations with sensible defaults
export const getDefaultChartConfigs = (): ChartConfig[] => [
  {
    id: Math.random().toString(36).substring(2, 11),
    xAxis: 'started_at',
    yAxis: 'latency',
    plotType: 'scatter',
    xMin: undefined,
    xMax: undefined,
    yMin: undefined,
    yMax: undefined,
    height: 300,
    x: 0,
    y: 0,
    w: 4,
    h: 4,
  },
  {
    id: Math.random().toString(36).substring(2, 11),
    xAxis: 'started_at',
    yAxis: 'total_tokens',
    plotType: 'scatter',
    xMin: undefined,
    xMax: undefined,
    yMin: undefined,
    yMax: undefined,
    height: 300,
    x: 4,
    y: 0,
    w: 4,
    h: 4,
  },
];

// Component to add a new chart
const AddChartButton = ({onClick}: {onClick: () => void}) => (
  <button
    onClick={onClick}
    className="rounded bg-teal-500 px-4 py-2 text-white hover:bg-teal-600">
    Add Chart
  </button>
);

const GRID_COLS = 12;
const GRID_ROW_HEIGHT = 60;

const CallsChartsInner = ({
  entity,
  project,
  filter,
  filterModelProp,
}: CallsChartsProps) => {
  const {state, dispatch} = useChartConfigContext();

  // Modal state
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const [editingConfig, setEditingConfig] = React.useState<ChartConfig | null>(
    null
  );
  const [isNewChart, setIsNewChart] = React.useState(false);

  const columns = useMemo(
    () => ['started_at', 'ended_at', 'exception', 'id'],
    []
  );
  const columnSet = useMemo(() => new Set(columns), [columns]);
  const sortCalls: GridSortModel = useMemo(
    () => [{field: 'started_at', sort: 'desc'}],
    []
  );
  const page = useMemo(
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

  // Track if we've sent analytics for metrics plots being viewed
  const sentEvent = useRef(false);
  const callsQueryStartTime = useRef<number | null>(null);

  // Fire analytics for metrics plots viewed
  if (!sentEvent.current) {
    if (calls.loading && callsQueryStartTime.current === null) {
      callsQueryStartTime.current = Date.now();
    } else if (!calls.loading && callsQueryStartTime.current !== null) {
      const endTime = Date.now();
      const latency = endTime - callsQueryStartTime.current;
      userEvents.metricsPlotsViewed({
        entity,
        project,
        latency,
      });
      sentEvent.current = true;
    }
  }

  // Process data for charts
  const processedData = useMemo(() => {
    if (calls.loading || !calls.result || calls.result.length === 0) {
      return [];
    }
    return calls.result.map(call => extractCallData(call));
  }, [calls.result, calls.loading]);

  // Open modal to add a new chart
  const handleAddChart = () => {
    setEditingConfig(createDefaultChartConfig());
    setIsNewChart(true);
    setIsModalOpen(true);
  };

  // Open modal to edit an existing chart
  const handleEditChart = (config: ChartConfig) => {
    setEditingConfig({...config});
    setIsNewChart(false);
    setIsModalOpen(true);
  };

  // Save chart configuration
  const handleSaveConfig = (config: ChartConfig) => {
    if (isNewChart) {
      dispatch({type: 'add', config});
    } else {
      dispatch({type: 'update', config});
    }
    setIsModalOpen(false);
  };

  // Delete a chart
  const handleDeleteChart = (id: string) => {
    dispatch({type: 'delete', id});
  };

  // Close modal without saving
  const handleCancelEdit = () => {
    setIsModalOpen(false);
  };

  // Handle layout change from react-grid-layout
  const handleLayoutChange = (layout: any[]) => {
    layout.forEach(l => {
      const config = state.configs.find(cfg => cfg.id === l.i);
      if (
        config &&
        (config.x !== l.x ||
          config.y !== l.y ||
          config.w !== l.w ||
          config.h !== l.h)
      ) {
        dispatch({
          type: 'update',
          config: {
            ...config,
            x: l.x,
            y: l.y,
            w: l.w,
            h: l.h,
            height: l.h * GRID_ROW_HEIGHT,
          },
        });
      }
    });
  };

  // Build layout array for react-grid-layout
  const gridLayout = state.configs.map(cfg => ({
    i: cfg.id,
    x: cfg.x ?? 0,
    y: cfg.y ?? 0,
    w: cfg.w ?? 4,
    h: cfg.h ?? 4,
    minW: 2,
    minH: 2,
    maxW: GRID_COLS,
  }));

  return (
    <Tailwind>
      <div className="w-full md:max-w-[calc(100vw-56px)]">
        <div className="mx-10 mt-10 flex items-center justify-between">
          <h3 className="text-lg font-medium">Charts</h3>
          <AddChartButton onClick={handleAddChart} />
        </div>

        <div className="m-10">
          <ResponsiveReactGridLayout
            className="layout"
            layouts={{lg: gridLayout}}
            breakpoints={{lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0}}
            cols={{lg: GRID_COLS, md: 8, sm: 6, xs: 4, xxs: 2}}
            rowHeight={GRID_ROW_HEIGHT}
            isResizable
            isDraggable
            onLayoutChange={handleLayoutChange}
            draggableHandle=".drag-handle"
            measureBeforeMount={false}
            useCSSTransforms={true}
            compactType="vertical"
            preventCollision={false}>
            {state.configs.map(config => (
              <div
                key={config.id}
                data-grid={{
                  x: config.x ?? 0,
                  y: config.y ?? 0,
                  w: config.w ?? 4,
                  h: config.h ?? 4,
                  minW: 2,
                  minH: 2,
                  maxW: GRID_COLS,
                }}>
                <div className="relative flex h-full w-full flex-col rounded-lg border border-moon-250 bg-white">
                  <div
                    className="drag-handle absolute left-1/2 top-0 z-10 -translate-x-1/2 cursor-move p-2"
                    style={{textAlign: 'center'}}>
                    <svg
                      width="24"
                      height="24"
                      viewBox="0 0 24 24"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg">
                      <circle cx="12" cy="6" r="1.5" fill="#888" />
                      <circle cx="12" cy="12" r="1.5" fill="#888" />
                      <circle cx="12" cy="18" r="1.5" fill="#888" />
                    </svg>
                  </div>
                  <div className="flex flex-1 flex-col">
                    <ChartDisplay
                      isLoading={calls.loading}
                      processedData={processedData}
                      config={config}
                      onDelete={() => handleDeleteChart(config.id)}
                      onEditConfig={() => handleEditChart(config)}
                    />
                  </div>
                </div>
              </div>
            ))}
          </ResponsiveReactGridLayout>
        </div>

        {isModalOpen && editingConfig && (
          <ChartConfigModal
            config={editingConfig}
            onSave={handleSaveConfig}
            onCancel={handleCancelEdit}
            isNew={isNewChart}
            processedData={processedData}
            isLoading={calls.loading}
          />
        )}
      </div>
    </Tailwind>
  );
};

export const CallsCharts = (props: CallsChartsProps) => {
  return (
    <ChartConfigProvider projectId={`${props.entity}/${props.project}`}>
      <CallsChartsInner {...props} />
    </ChartConfigProvider>
  );
};
