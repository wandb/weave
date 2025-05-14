import React from 'react';

import {Button} from '../../../../../components/Button';
import {WaveLoader} from '../../../../../components/Loaders/WaveLoader';
import {WFHighLevelCallFilter} from '../pages/CallsPage/callsTableFilter';
import {BarChart} from './BarChart';
import {chartContentStyle} from './chartUtils';
import {AggregationMethod} from './chartUtils';
import {
  ExtractedCallData,
  getScatterXAxisFields,
  getYAxisFields,
} from './extractData';
import {LinePlot} from './LinePlot';
import {ScatterPlot} from './ScatterPlot';

export type ChartProps = {
  data: ExtractedCallData[];
  height?: number;
  xAxis?: string;
  yAxis?: string;
  plotType: 'scatter' | 'line' | 'bar';
  binCount?: number;
  aggregation?: AggregationMethod;
  title?: string;
  onEdit?: () => void;
  onRemove?: () => void;
  className?: string;
  filter?: WFHighLevelCallFilter;
  chartId?: string;
  entity?: string;
  project?: string;
  colorGroupKey?: string;
  isLoading?: boolean;
};

/**
 * Chart component that wraps LinePlot and ScatterPlot components with local hover state
 */
export const Chart: React.FC<ChartProps> = ({
  data,
  height,
  xAxis = 'started_at',
  yAxis = 'latency',
  plotType,
  binCount = 20,
  aggregation = 'average',
  title,
  onEdit,
  onRemove,
  className,
  filter,
  chartId,
  entity,
  project,
  colorGroupKey,
  isLoading,
}) => {
  const [isChartHovered, setIsChartHovered] = React.useState(false);
  const [isFullscreen, setIsFullscreen] = React.useState(false);

  // Determine effective groupKey based on filter
  const effectiveGroupKey = React.useMemo(() => {
    const hasSpecificOpFilter = (filter?.opVersionRefs?.length ?? 0) > 0;

    if (!hasSpecificOpFilter) {
      // "All ops" is selected - group by op_name
      return 'op_name';
    }

    // Specific op is filtered - no grouping
    return undefined;
  }, [filter?.opVersionRefs]);

  // Get the y-axis field to access its units
  const yField = React.useMemo(() => {
    return getYAxisFields(data).find(f => f.key === yAxis);
  }, [yAxis, data]);

  // Get the x-axis field and label
  const xAxisLabel = React.useMemo(() => {
    if (plotType === 'scatter') {
      const xField = getScatterXAxisFields(data).find(f => f.key === xAxis);
      return xField?.label || 'Value';
    }
    return 'Time';
  }, [plotType, xAxis, data]);

  // Get the x-axis field for scatter plots (used in title generation)
  const xField = React.useMemo(() => {
    if (plotType === 'scatter') {
      return getScatterXAxisFields(data).find(f => f.key === xAxis);
    }
    return undefined;
  }, [plotType, xAxis, data]);

  // Format aggregation method for display
  const formatAggregationMethod = React.useCallback(
    (method: AggregationMethod): string => {
      switch (method) {
        case 'average':
          return 'Average';
        case 'sum':
          return 'Sum';
        case 'min':
          return 'Minimum';
        case 'max':
          return 'Maximum';
        case 'p95':
          return 'P95';
        case 'p99':
          return 'P99';
        default:
          return method;
      }
    },
    []
  );

  // Format the title with units and aggregation method if available
  const formattedTitle = React.useMemo(() => {
    if (!title) return '';

    let formattedTitle = title;

    // For scatter plots, include x-axis name if it's not a time-based axis
    if (
      plotType === 'scatter' &&
      xField &&
      xAxis !== 'started_at' &&
      xAxis !== 'ended_at'
    ) {
      const yAxisLabel = yField?.label || title;
      const xAxisLabel = xField.label;
      formattedTitle = `${yAxisLabel} vs ${xAxisLabel}`;
    } else {
      // Add aggregation method for line plots and bar charts
      if (plotType === 'line' || plotType === 'bar') {
        formattedTitle = `${formatAggregationMethod(aggregation)} ${title}`;
      }
    }

    // Add units if available
    if (yField?.units) {
      formattedTitle = `${formattedTitle} (${yField.units})`;
    }

    return formattedTitle;
  }, [
    title,
    yField?.units,
    yField?.label,
    plotType,
    aggregation,
    formatAggregationMethod,
    xField,
    xAxis,
  ]);

  // Calculate what plot to render
  const PlotComponent =
    plotType === 'line'
      ? LinePlot
      : plotType === 'bar'
      ? BarChart
      : ScatterPlot;

  // Get props for the plot component
  const plotProps = {
    data,
    height: isFullscreen ? window.innerHeight - 160 : height,
    width: isFullscreen ? window.innerWidth - 140 : undefined,
    initialYAxis: yAxis,
    groupKey: effectiveGroupKey,
    chartId, // Pass the chart ID for domain management
    entity, // Pass entity for peek drawer navigation
    project, // Pass project for peek drawer navigation
    xAxisLabel, // Pass the x-axis label
    isFullscreen, // Pass fullscreen state for larger text
    ...(plotType === 'line' || plotType === 'bar'
      ? {binCount, aggregation}
      : {}),
    ...(plotType === 'scatter' ? {initialXAxis: xAxis} : {}),
    colorGroupKey,
  };

  const handleToggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const chartContent = (
    <div
      className={className}
      style={{
        border: '1px solid #e0e0e0',
        borderRadius: 6,
        background: '#fff',
        display: 'flex',
        flexDirection: 'column',
        height: isFullscreen ? window.innerHeight - 140 : 300,
        width: isFullscreen ? window.innerWidth - 100 : 500,
        minHeight: 0,
        boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
        overflow: 'hidden',
        flexShrink: 0,
        zIndex: isFullscreen ? 1001 : 'auto',
      }}
      onMouseEnter={() => setIsChartHovered(true)}
      onMouseLeave={() => setIsChartHovered(false)}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '4px 8px',
          fontWeight: 500,
          userSelect: 'none',
          position: 'relative',
          height: 32,
          flex: '0 0 auto',
        }}>
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none',
            zIndex: 0,
          }}>
          <span
            style={{
              fontWeight: 600,
              fontSize: isFullscreen ? 20 : 13,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              pointerEvents: 'none',
              maxWidth: 'calc(100% - 60px)',
            }}>
            {formattedTitle}
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            gap: 2,
            flex: '0 0 auto',
            zIndex: 1,
            marginLeft: 'auto',
            marginTop: isFullscreen ? 24 : 0,
            opacity: isChartHovered || isFullscreen ? 1 : 0,
            transition: 'opacity 0.2s ease-in-out',
          }}>
          <Button
            icon={isFullscreen ? 'minimize-mode' : 'full-screen-mode-expand'}
            variant="ghost"
            size={isFullscreen ? 'large' : 'small'}
            onClick={handleToggleFullscreen}
          />
          {onEdit && !isFullscreen && (
            <Button
              icon="settings"
              variant="ghost"
              size="small"
              onClick={onEdit}
            />
          )}
          {onRemove && !isFullscreen && (
            <Button
              icon="close"
              variant="ghost"
              size="small"
              onClick={onRemove}
            />
          )}
        </div>
      </div>
      <div style={chartContentStyle}>
        {isLoading ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              minHeight: 200,
            }}>
            <WaveLoader size="small" />
          </div>
        ) : (
          <PlotComponent {...plotProps} />
        )}
      </div>
    </div>
  );

  if (isFullscreen) {
    return (
      <div
        style={{
          position: 'fixed',
          top: 40,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}
        onClick={e => {
          if (e.target === e.currentTarget) {
            setIsFullscreen(false);
          }
        }}>
        {chartContent}
      </div>
    );
  }

  return chartContent;
};
