import 'react-vis/dist/style.css';

import React from 'react';
import {FlexibleXYPlot, Hint, VerticalBarSeries, XAxis, YAxis} from 'react-vis';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {WaveLoader} from '../../../../../components/Loaders/WaveLoader';
import {calculateBinBoundaries, createBinnedPointsByGroup} from './aggregation';
import {useChartData} from './chartDataProcessing';
import {useChartsDispatch, useChartsState} from './ChartsContext';
import {getXAxisFields, getYAxisFields} from './extractData';
import {
  createAxisTickFormatters,
  formatBinWidth,
  formatSmartDateRange,
  formatTooltipValue,
  truncateText,
} from './format';
import {
  chartContainerStyle,
  chartContentStyle,
  createChartMargins,
  tooltipContainerStyle,
  tooltipHeaderStyle,
  tooltipRowStyle,
} from './styling';
import {ChartAxisField, ExtractedCallData} from './types';
import {AggregationMethod} from './types';
import {useChartZoom} from './useChartZoom';

type BarChartTooltipData = {
  x: number;
  y: number;
  y0: number;
  group: string;
  color: string;
};

const BarChartTooltip: React.FC<{
  data: BarChartTooltipData;
  xField?: ChartAxisField;
  yField?: ChartAxisField;
  isFullscreen?: boolean;
  binStart?: number;
  binEnd?: number;
}> = ({data, xField, yField, isFullscreen, binStart, binEnd}) => {
  if (!data) return null;

  if (isNaN(data.y)) return null;

  const barValue = data.y - data.y0;

  const displayName = data.group || 'Value:';
  const truncatedGroup = truncateText(displayName, isFullscreen ? 100 : 50);

  return (
    <div style={tooltipContainerStyle(isFullscreen)}>
      <div style={tooltipHeaderStyle(isFullscreen)}>
        {binStart !== undefined && binEnd !== undefined
          ? xField?.type === 'date'
            ? `${formatSmartDateRange(binStart, binEnd)} (${formatBinWidth(
                binStart,
                binEnd,
                true
              )})`
            : `${formatTooltipValue(
                binStart,
                xField?.units
              )} - ${formatTooltipValue(
                binEnd,
                xField?.units
              )} (${formatBinWidth(binStart, binEnd, false, xField?.units)})`
          : formatTooltipValue(data.x, xField?.units)}
      </div>
      <div
        style={{
          ...tooltipRowStyle(isFullscreen),
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: isFullscreen ? '16px' : '14px',
          fontFamily: 'inconsolata',
        }}>
        <span
          style={{
            color: data.color,
            flex: '1 1 auto',
            minWidth: 0,
            fontWeight: 600,
          }}
          title={displayName}>
          {truncatedGroup}
        </span>
        <span
          style={{
            flex: '0 0 auto',
            textAlign: 'right',
            minWidth: isFullscreen ? '60px' : '50px',
            color: data.color,
            fontWeight: 'bold',
          }}>
          {formatTooltipValue(barValue, yField?.units)}
        </span>
      </div>
    </div>
  );
};

export type BarChartProps = {
  data: ExtractedCallData[];
  height?: number;
  width?: number;
  initialXAxis?: string;
  initialYAxis?: string;
  binCount?: number;
  aggregation?: AggregationMethod;
  groupKey?: string;
  colorGroupKey?: string;
  chartId?: string;
  xAxisLabel?: string;
  isFullscreen?: boolean;
};

export const BarChart: React.FC<BarChartProps> = ({
  data,
  height,
  width,
  initialXAxis = 'started_at',
  initialYAxis = 'latency',
  binCount = 20,
  aggregation = 'average',
  groupKey,
  colorGroupKey,
  chartId,
  xAxisLabel,
  isFullscreen,
}) => {
  const globalState = useChartsState();
  const globalDispatch = useChartsDispatch();

  // Get chart config for domain refinement
  const chartConfig = chartId
    ? globalState.charts.find(c => c.id === chartId)
    : undefined;

  const xField = React.useMemo(
    () => getXAxisFields(data).find(f => f.key === initialXAxis),
    [initialXAxis, data]
  );
  const yField = getYAxisFields(data).find(f => f.key === initialYAxis);

  // Use shared chart data processing logic
  const {points, dataRanges, isDataReady, groupColor} = useChartData(
    data,
    initialXAxis,
    initialYAxis,
    xField,
    yField,
    groupKey,
    colorGroupKey
  );

  // Transform ProcessedChartPoint to DataPoint format expected by this component
  const transformedPoints = React.useMemo(() => {
    return points.map(point => ({
      x: point.x,
      y: point.y,
      display_name: point.display_name,
      group: point.group,
    }));
  }, [points]);

  // Check if we have processed data but it's empty (not loading, just no data)
  const hasNoData = React.useMemo(() => {
    return (
      data !== undefined &&
      xField &&
      yField &&
      (data.length === 0 || transformedPoints.length === 0)
    );
  }, [data, transformedPoints, xField, yField]);

  // State for tooltips
  const [hintValue, setHintValue] = React.useState<any>(null);

  const binnedPointsByGroup = React.useMemo(() => {
    if (!data || data.length === 0 || transformedPoints.length === 0) {
      return {};
    }

    const currentXDomain = chartConfig?.xDomain || [
      dataRanges.xMin,
      dataRanges.xMax,
    ];

    return createBinnedPointsByGroup(
      transformedPoints,
      binCount,
      aggregation,
      currentXDomain,
      dataRanges,
      groupKey,
      colorGroupKey,
      true
    );
  }, [
    data,
    transformedPoints,
    binCount,
    aggregation,
    groupKey,
    colorGroupKey,
    chartConfig?.xDomain,
    dataRanges,
  ]);

  // Prepare stacked bar data for react-vis
  const stackedBarData = React.useMemo(() => {
    if (!groupKey && !colorGroupKey) {
      const allData = binnedPointsByGroup.all || [];
      return [
        {
          group: 'Value',
          color: TEAL_600,
          data: allData
            .filter(point => !isNaN(point.x) && !isNaN(point.y) && point.y > 0)
            .map(point => ({
              x: point.x,
              y: point.y,
              y0: 0,
              originalPoint: point,
            })),
        },
      ];
    }

    const groups = Object.keys(binnedPointsByGroup);
    const firstGroup = binnedPointsByGroup[groups[0]] || [];

    // Create a single dataset with all stacked segments
    const allStackedSegments: any[] = [];

    firstGroup.forEach((_, xIndex) => {
      let cumulativeY = 0;
      let hasAnyData = false;

      groups.forEach(group => {
        const point = binnedPointsByGroup[group][xIndex];
        const value = point && !isNaN(point.y) ? point.y : 0;

        if (value > 0) {
          const color = groupColor(group);

          allStackedSegments.push({
            x: point.x,
            y: cumulativeY + value,
            y0: cumulativeY,
            color: color,
            group: group,
            originalPoint: point,
          });
          cumulativeY += value;
          hasAnyData = true;
        }
      });

      // If no group had data for this bin, create a minimal invisible segment to preserve x-axis position
      if (!hasAnyData && firstGroup[xIndex]) {
        allStackedSegments.push({
          x: firstGroup[xIndex].x,
          y: 0.001, // Minimal height to ensure it appears on axis
          y0: 0,
          color: 'transparent',
          group: 'Empty',
          originalPoint: firstGroup[xIndex],
        });
      }
    });

    return [
      {
        group: 'Stacked',
        color: '#000', // Not used since each segment has its own color
        data: allStackedSegments,
      },
    ];
  }, [binnedPointsByGroup, groupKey, colorGroupKey, groupColor]);

  // Calculate adjusted domains for bar charts - AFTER stackedBarData is defined
  const adjustedDomains = React.useMemo(() => {
    // For bar charts, Y should always start from 0
    const currentXDomain = chartConfig?.xDomain || [
      dataRanges.xMin,
      dataRanges.xMax,
    ];

    // Calculate the maximum Y value from stacked data
    let maxY = 0;
    stackedBarData.forEach(series => {
      series.data.forEach(point => {
        maxY = Math.max(maxY, point.y);
      });
    });

    const currentYDomain: [number, number] = [0, maxY * 1.1]; // Always start from 0, add 10% padding

    return {
      xDomain: currentXDomain,
      yDomain: currentYDomain,
    };
  }, [chartConfig?.xDomain, dataRanges, stackedBarData]);

  // Create unified tick formatters using chartUtils
  const {xTickFormatter, yTickFormatter} = React.useMemo(
    () =>
      createAxisTickFormatters(
        xField,
        yField,
        adjustedDomains.xDomain,
        adjustedDomains.yDomain
      ),
    [xField, yField, adjustedDomains.xDomain, adjustedDomains.yDomain]
  );

  // Chart margins and padding constants
  const chartMargins = React.useMemo(
    () => createChartMargins(isFullscreen),
    [isFullscreen]
  );

  // Use the flexible zoom hook for paint-to-zoom functionality
  const {
    containerRef,
    selectionStyle,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    handleDoubleClick,
  } = useChartZoom({
    chartId,
    xDomain: adjustedDomains.xDomain,
    yDomain: adjustedDomains.yDomain,
    isFullscreen,
    xAxisZoomOnly: true,
  });

  // Auto-reset domains if no data is available after zooming
  const hasResetRef = React.useRef(false);
  const previousConfigRef = React.useRef(chartConfig);

  React.useEffect(() => {
    // Reset the flag when chartConfig changes (new zoom state)
    if (previousConfigRef.current !== chartConfig) {
      hasResetRef.current = false;
      previousConfigRef.current = chartConfig;
    }

    if (
      chartId &&
      globalDispatch &&
      chartConfig &&
      data &&
      data.length > 0 &&
      !hasResetRef.current &&
      (chartConfig.xDomain || chartConfig.yDomain) // Only reset if there's actually a zoom state
    ) {
      const hasVisibleData = stackedBarData.some(
        series => series.data.length > 0
      );
      if (!hasVisibleData) {
        hasResetRef.current = true; // Prevent multiple dispatches
        globalDispatch({
          type: 'RESET_CHART_DOMAIN',
          id: chartId,
        });
      }
    }
  }, [chartId, globalDispatch, data, stackedBarData, chartConfig]);

  return (
    <div style={chartContainerStyle}>
      {hasNoData ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            minHeight: 200,
            color: '#8F8F8F',
            fontSize: '14px',
          }}>
          No data could be found
        </div>
      ) : !isDataReady ? (
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
      ) : Object.keys(binnedPointsByGroup).length === 0 ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            minHeight: 200,
            color: '#8F8F8F',
            cursor: 'pointer',
            userSelect: 'none',
          }}
          onDoubleClick={handleDoubleClick}>
          <span style={{fontSize: '14px', marginBottom: '8px'}}>
            No data to display
          </span>
          <span style={{fontSize: '12px', fontStyle: 'italic'}}>
            Double-click to reset zoom
          </span>
        </div>
      ) : (
        <div style={chartContentStyle}>
          <div
            ref={containerRef}
            style={{
              width: '100%',
              height: height || '100%',
              position: 'relative',
              isolation: 'isolate',
              zIndex: 1,
              display: 'flex',
              flex: '1 1 auto',
              justifyContent: 'flex-start',
              alignItems: 'center',
              maxWidth: '100%',
              overflow: 'hidden',
              cursor: 'crosshair',
              userSelect: 'none',
              WebkitUserSelect: 'none',
              MozUserSelect: 'none',
              msUserSelect: 'none',
            }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onDoubleClick={handleDoubleClick}>
            <FlexibleXYPlot
              xDomain={chartConfig?.xDomain}
              yDomain={chartConfig?.yDomain}
              margin={chartMargins}
              onMouseLeave={() => setHintValue(null)}>
              <XAxis
                tickFormat={xTickFormatter}
                tickTotal={5}
                title={xAxisLabel}
                style={{
                  text: {
                    fontSize: isFullscreen ? '14px' : '10px',
                    fontFamily: 'Source Sans Pro',
                  },
                }}
              />
              <YAxis
                tickFormat={yTickFormatter}
                tickTotal={6}
                style={{
                  text: {
                    fontSize: isFullscreen ? '14px' : '10px',
                    fontFamily: 'Source Sans Pro',
                  },
                }}
              />
              {stackedBarData.map((series, index) => (
                <VerticalBarSeries
                  key={series.group}
                  data={series.data}
                  colorType="literal"
                  barWidth={0.95}
                  onValueMouseOver={(value: any) => {
                    // Calculate bin bounds for tooltip using shared utility
                    const currentXDomain = chartConfig?.xDomain || [
                      dataRanges.xMin,
                      dataRanges.xMax,
                    ];

                    const {binStart, binEnd} = calculateBinBoundaries(
                      value.originalPoint.x,
                      transformedPoints,
                      binCount,
                      currentXDomain,
                      initialXAxis === 'prediction_index'
                    );

                    setHintValue({
                      x: value.x,
                      y: value.y,
                      tooltipData: {
                        x: value.originalPoint.x,
                        y: value.y,
                        y0: value.y0,
                        group: value.group,
                        color: value.color,
                      },
                      binStart,
                      binEnd,
                    });
                  }}
                  onValueMouseOut={() => setHintValue(null)}
                />
              ))}
              {hintValue && (
                <Hint value={hintValue}>
                  <BarChartTooltip
                    data={hintValue.tooltipData}
                    xField={xField}
                    yField={yField}
                    isFullscreen={isFullscreen}
                    binStart={hintValue.binStart}
                    binEnd={hintValue.binEnd}
                  />
                </Hint>
              )}
            </FlexibleXYPlot>
            {selectionStyle && <div style={selectionStyle} />}
          </div>
        </div>
      )}
    </div>
  );
};
