/*
  Chart.tsx

  This file contains the Chart component, which is a wrapper for individual chart types.
  The Chart component adds a title, some controls, a fullscreen mode, and a loading state.
*/
import React from 'react';

import {Button} from '../../../../../components/Button';
import {WaveLoader} from '../../../../../components/Loaders/WaveLoader';
import {WFHighLevelCallFilter} from '../pages/CallsPage/callsTableFilter';
import {BarChart} from './BarChart';
import {useMultipleOperations} from './chartDataProcessing';
import {getScatterXAxisFields, getYAxisFields} from './extractData';
import {LinePlot} from './LinePlot';
import {ScatterPlot} from './ScatterPlot';
import {chartContentStyle} from './styling';
import {AggregationMethod, ExtractedCallData} from './types';

// Utility function to generate auto-names for charts
export const generateChartAutoName = (
  yAxis: string,
  plotType: 'scatter' | 'line' | 'bar',
  aggregation: AggregationMethod,
  xAxis: string,
  data: ExtractedCallData[]
): string => {
  // Get the y-axis field to access its label
  const yField = getYAxisFields(data).find(f => f.key === yAxis);
  const yLabel = yField?.label || yAxis;

  // Get the x-axis field for scatter plots
  const xField =
    plotType === 'scatter'
      ? getScatterXAxisFields(data).find(f => f.key === xAxis)
      : undefined;

  // For scatter plots, include x-axis name if it's not a time-based axis
  if (
    plotType === 'scatter' &&
    xField &&
    xAxis !== 'started_at' &&
    xAxis !== 'ended_at'
  ) {
    const xLabel = xField.label;
    return `${yLabel} vs ${xLabel}`;
  } else if (plotType === 'line' || plotType === 'bar') {
    return `${aggregation} ${yLabel}`;
  }

  return yLabel;
};

export type ChartProps = {
  data: ExtractedCallData[];
  height?: number;
  xAxis?: string;
  yAxis?: string;
  plotType: 'scatter' | 'line' | 'bar';
  binCount?: number;
  aggregation?: AggregationMethod;
  title?: string;
  customName?: string;
  onEdit?: () => void;
  onRemove?: () => void;
  className?: string;
  filter?: WFHighLevelCallFilter;
  chartId?: string;
  entity?: string;
  project?: string;
  groupKeys?: string[];
  isLoading?: boolean;
  addChart?: () => void;
  noFullscreen?: boolean;
};

export const Chart: React.FC<ChartProps> = ({
  data,
  height,
  xAxis = 'started_at',
  yAxis = 'latency',
  plotType,
  binCount = 20,
  aggregation = 'average',
  title,
  customName,
  onEdit,
  onRemove,
  className,
  chartId,
  entity,
  project,
  groupKeys,
  isLoading,
  addChart,
  noFullscreen = false,
}) => {
  const [isChartHovered, setIsChartHovered] = React.useState(false);
  const [isFullscreen, setIsFullscreen] = React.useState(false);
  const hasMultipleOperations = useMultipleOperations(data);

  // Determine effective groupKeys based on multiple operations and user selection
  const effectiveGroupKeys = React.useMemo(() => {
    const keys: string[] = [];

    // Always include op_name when there are multiple operations
    if (hasMultipleOperations) {
      keys.push('op_name');
    }

    // Add user-configured group keys (excluding op_name to avoid duplicates)
    if (groupKeys) {
      groupKeys.forEach(key => {
        if (key !== 'op_name' && !keys.includes(key)) {
          keys.push(key);
        }
      });
    }

    return keys.length > 0 ? keys : undefined;
  }, [hasMultipleOperations, groupKeys]);

  // Get the x-axis field and label
  const xAxisLabel = React.useMemo(() => {
    if (plotType === 'scatter') {
      const xField = getScatterXAxisFields(data).find(f => f.key === xAxis);
      return xField?.label || 'Value';
    }
    return 'Time';
  }, [plotType, xAxis, data]);

  // Generate the final title to display
  const displayTitle = React.useMemo(() => {
    // Use custom name if provided, otherwise generate auto-name
    if (customName) {
      return customName;
    }

    // Generate auto-name based on chart configuration
    return generateChartAutoName(yAxis, plotType, aggregation, xAxis, data);
  }, [customName, yAxis, plotType, aggregation, xAxis, data]);

  const PlotComponent =
    plotType === 'line'
      ? LinePlot
      : plotType === 'bar'
      ? BarChart
      : ScatterPlot;

  const plotProps = {
    data,
    height: isFullscreen ? window.innerHeight - 160 : height,
    initialYAxis: yAxis,
    groupKeys: effectiveGroupKeys,
    chartId,
    entity,
    project,
    xAxisLabel,
    isFullscreen,
    ...(plotType === 'line' || plotType === 'bar'
      ? {binCount, aggregation, initialXAxis: xAxis}
      : {}),
    ...(plotType === 'scatter' ? {initialXAxis: xAxis} : {}),
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
        height: isFullscreen ? window.innerHeight - 140 : height || 280,
        width: isFullscreen ? window.innerWidth - 100 : '100%',
        minHeight: 0,
        boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
        overflow: 'hidden',
        zIndex: isFullscreen ? 1001 : 'auto',
        flexShrink: 0,
      }}
      onMouseEnter={() => setIsChartHovered(true)}
      onMouseLeave={() => setIsChartHovered(false)}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
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
            {displayTitle}
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            gap: 2,
            flex: '0 0 auto',
            zIndex: 1,
            marginLeft: 'auto',
            marginRight: isFullscreen ? 8 : 4,
            marginTop: isFullscreen ? 24 : 0,
            opacity: isChartHovered || isFullscreen ? 1 : 0,
            transition: 'opacity 0.2s ease-in-out',
          }}>
          {addChart && (
            <Button
              icon="add-new"
              variant="ghost"
              size="small"
              onClick={() => addChart?.()}
            />
          )}
          {!noFullscreen && (
            <Button
              className="no-drag"
              icon={isFullscreen ? 'minimize-mode' : 'full-screen-mode-expand'}
              variant="ghost"
              size={isFullscreen ? 'large' : 'small'}
              onClick={handleToggleFullscreen}
            />
          )}
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
              className="no-drag"
              icon="close"
              variant="ghost"
              size="small"
              onClick={onRemove}
            />
          )}
        </div>
      </div>
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
        <div style={chartContentStyle}>
          <PlotComponent {...plotProps} />
        </div>
      )}
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
