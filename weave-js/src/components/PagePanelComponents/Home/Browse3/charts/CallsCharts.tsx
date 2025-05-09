import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Modal,
  Select,
  Typography,
} from '@mui/material';
import {GridFilterModel, GridSortModel} from '@mui/x-data-grid-pro';
import React, {useMemo, useRef, useState} from 'react';

import {MOON_400, RED_400} from '../../../../../common/css/color.styles';
import * as userEvents from '../../../../../integrations/analytics/userEvents';
import {IconInfo, IconSettings} from '../../../../Icon';
import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {Tailwind} from '../../../../Tailwind';
import {WFHighLevelCallFilter} from '../pages/CallsPage/callsTableFilter';
import {useCallsForQuery} from '../pages/CallsPage/callsTableQuery';
import {ChartConfigProvider, useChartConfigContext} from './ChartConfigContext';
import {HistogramPlot, LinePlot, ScatterPlot} from './Charts';
import {ChartConfig} from './ChartTypes';

// Available axis options - allow any field for either axis
type AxisOption =
  | 'started_at'
  | 'ended_at'
  | 'latency'
  | 'cost'
  | 'isError'
  | 'prompt_tokens'
  | 'completion_tokens'
  | 'input_tokens'
  | 'output_tokens'
  | 'total_tokens';
type PlotType = 'scatter' | 'bar' | 'line';

// All available field options
const allAxisOptions: {value: AxisOption; label: string}[] = [
  {value: 'started_at', label: 'Start Time'},
  {value: 'ended_at', label: 'End Time'},
  {value: 'latency', label: 'Latency'},
  {value: 'cost', label: 'Cost'},
  {value: 'isError', label: 'Errors'},
  {value: 'prompt_tokens', label: 'Prompt Tokens'},
  {value: 'completion_tokens', label: 'Completion Tokens'},
  {value: 'input_tokens', label: 'Input Tokens'},
  {value: 'output_tokens', label: 'Output Tokens'},
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
    {value: 'bar', label: 'Bar Chart'},
    {value: 'line', label: 'Line Plot'},
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
      .filter(
        item =>
          item[xAxis] != null && (yAxis === 'isError' || item[yAxis] != null)
      )
      .map(item => ({
        started_at: item[xAxis],
        [yAxis]: item[yAxis],
        isError: yAxis === 'isError' ? item.isError : undefined,
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
          <Button variant="outlined" onClick={onCancel} sx={{px: 3, py: 1}}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            sx={{
              px: 3,
              py: 1,
              bgcolor: 'teal.500',
              '&:hover': {bgcolor: 'teal.600'},
            }}>
            {isNew ? 'Add Chart' : 'Save Changes'}
          </Button>
        </Box>
      </Box>
    </Modal>
  );
};

// Helper to determine if a field is time-based
const isTimeField = (field: AxisOption) =>
  field === 'started_at' || field === 'ended_at';

// Custom chart component that supports different plot types
const CustomChart = ({
  chartData,
  height,
  plotType,
  yAxisField,
  config,
}: {
  chartData: any[];
  height: number;
  plotType: PlotType;
  yAxisField: AxisOption;
  config: ChartConfig;
}) => {
  if (!chartData || chartData.length === 0) {
    return <div style={{height: `${height}px`}}></div>;
  }

  const xDomain =
    config.xMin !== undefined || config.xMax !== undefined
      ? [config.xMin, config.xMax]
      : undefined;

  const yDomain =
    config.yMin !== undefined || config.yMax !== undefined
      ? [config.yMin, config.yMax]
      : undefined;

  // Determine the units and label based on y-axis field
  let units = '';
  if (yAxisField.includes('tokens')) {
    units = yAxisField.replace(/_/g, ' ');
  } else if (yAxisField === 'latency') {
    units = 'ms';
  } else if (yAxisField === 'cost') {
    units = '$';
  }

  // Tooltip x value format
  const xTooltipFormat = isTimeField(config.xAxis as AxisOption)
    ? '%{x|%b %d, %H:%M}'
    : '%{x:,.1f}';

  // Map data to TimestampPoint[] for generic chart components
  const mappedData = chartData
    .map(item => ({
      started_at: item.started_at || item[config.xAxis],
      [yAxisField]: item[yAxisField],
      isError: yAxisField === 'isError' ? item.isError : undefined,
    }))
    .filter(item => item[yAxisField] != null);

  if (mappedData.length === 0) {
    return <div style={{height: `${height}px`}}>No data available</div>;
  }

  if (yAxisField === 'isError') {
    // Show a histogram of errors (count per bin)
    return (
      <HistogramPlot
        data={mappedData}
        height={height}
        xLabel={config.xAxis}
        yLabel={'Errors'}
        color={RED_400}
        minBins={config.minBins}
        aggregation={'sum'}
        tooltipTemplate={`%{y} errors<br>Calls in bin: %{customdata[0]}<br>${xTooltipFormat}<extra></extra>`}
        xDomain={xDomain}
        yDomain={yDomain}
      />
    );
  }

  if (plotType === 'bar') {
    return (
      <HistogramPlot
        data={mappedData}
        height={height}
        xLabel={config.xAxis}
        yLabel={yAxisField}
        minBins={config.minBins}
        aggregation={config.aggregation as any}
        tooltipTemplate={`%{y} ${
          units || ''
        }<br>Calls in bin: %{customdata[0]}<br>${xTooltipFormat}<extra></extra>`}
        xDomain={xDomain}
        yDomain={yDomain}
      />
    );
  }

  if (plotType === 'line') {
    return (
      <LinePlot
        data={mappedData}
        height={height}
        xLabel={config.xAxis}
        yLabel={yAxisField}
        aggregation={config.aggregation as any}
        minBins={config.minBins}
        tooltipTemplate={`%{y} ${
          units || ''
        }<br>Calls in bin: %{customdata[0]}<br>${xTooltipFormat}<extra></extra>`}
        xDomain={xDomain}
        yDomain={yDomain}
      />
    );
  }

  return (
    <ScatterPlot
      data={mappedData}
      height={height}
      xLabel={config.xAxis}
      yLabel={yAxisField}
      tooltipTemplate={`%{y} ${
        units || ''
      }<br>${xTooltipFormat}<extra></extra>`}
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
    'flex-1 rounded-lg border border-moon-250 bg-white p-10 relative';
  const CHART_TITLE_STYLES =
    'ml-12 mt-8 text-base font-semibold text-moon-750 flex justify-between items-center';
  const CHART_HEIGHT = 250;
  const LOADING_CONTAINER_STYLES = `flex h-[${CHART_HEIGHT}px] items-center justify-center`;

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
      .filter(
        item =>
          item[config.xAxis] != null &&
          (config.yAxis === 'isError' || item[config.yAxis] != null)
      )
      .map(item => ({
        started_at: item[config.xAxis],
        [config.yAxis]: item[config.yAxis],
        isError: config.yAxis === 'isError' ? item.isError : undefined,
      }));

    if (filteredData.length > 0) {
      chart = (
        <CustomChart
          chartData={filteredData}
          height={CHART_HEIGHT}
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
          <button
            onClick={onEditConfig}
            className="text-moon-500 hover:text-moon-700"
            aria-label="Edit chart settings">
            <IconSettings color={MOON_400} />
          </button>
          <button
            onClick={onDelete}
            className="text-moon-500 hover:text-moon-700"
            aria-label="Delete chart">
            <IconInfo color={MOON_400} />
          </button>
        </div>
      </div>
      {chart}
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
  },
  {
    id: Math.random().toString(36).substring(2, 11),
    xAxis: 'started_at',
    yAxis: 'isError',
    plotType: 'scatter',
    xMin: undefined,
    xMax: undefined,
    yMin: undefined,
    yMax: undefined,
    height: 300,
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

    return calls.result
      .map(call => {
        const started_at = call.traceCall?.started_at;
        if (!started_at) {
          return null;
        }

        const ended_at = call.traceCall?.ended_at;
        const isError =
          call.traceCall?.exception !== null &&
          call.traceCall?.exception !== undefined &&
          call.traceCall?.exception !== '';

        let latency = null;
        if (ended_at != null) {
          latency =
            new Date(ended_at).getTime() - new Date(started_at).getTime();
        }

        // Extract token metrics from summary if available
        const weave_summary = call.traceCall?.summary?.weave || {};
        const usage = weave_summary.costs || {};
        const firstProvider = Object.keys(usage)[0];
        const tokenData = firstProvider ? usage[firstProvider] : {};
        const prompt_tokens = tokenData.prompt_tokens || null;
        const completion_tokens = tokenData.completion_tokens || null;
        const input_tokens = tokenData.input_tokens || null;
        const output_tokens = tokenData.output_tokens || null;
        const total_tokens =
          tokenData.total_tokens ||
          (prompt_tokens && completion_tokens
            ? prompt_tokens + completion_tokens
            : null);

        return {
          started_at,
          ended_at,
          latency,
          isError: isError ? 1 : 0,
          count: 1,
          prompt_tokens,
          completion_tokens,
          input_tokens,
          output_tokens,
          total_tokens,
        };
      })
      .filter(Boolean);
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

  return (
    <Tailwind>
      <div className="w-full md:max-w-[calc(100vw-56px)]">
        <div className="mx-10 mt-10 flex items-center justify-between">
          <h3 className="text-lg font-medium">Charts</h3>
          <AddChartButton onClick={handleAddChart} />
        </div>

        <div className="m-10 flex flex-wrap gap-10">
          {state.configs.map(config => (
            <div
              key={config.id}
              className="mb-10 w-full md:w-[calc(33.33%-28px)]">
              <ChartDisplay
                isLoading={calls.loading}
                processedData={processedData}
                config={config}
                onDelete={() => handleDeleteChart(config.id)}
                onEditConfig={() => handleEditChart(config)}
              />
            </div>
          ))}
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
