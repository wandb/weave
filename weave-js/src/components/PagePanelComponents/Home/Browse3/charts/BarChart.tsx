import 'react-vis/dist/style.css';

import React from 'react';
import {FlexibleXYPlot, Hint, VerticalBarSeries, XAxis, YAxis} from 'react-vis';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {WaveLoader} from '../../../../../components/Loaders/WaveLoader';
import {aggregateValues, binDataPoints} from './aggregation';
import {useChartData} from './chartDataProcessing';
import {useChartsDispatch, useChartsState} from './ChartsContext';
import {
  ChartAxisField,
  ExtractedCallData,
  getXAxisFields,
  getYAxisFields,
} from './extractData';
import {createAxisTickFormatters} from './format';
import {
  AggregationMethod,
  formatSmartDateRange,
  formatTooltipDate,
  formatTooltipValue,
} from './format';
import {
  chartContainerStyle,
  chartContentStyle,
  createChartMargins,
  tooltipContainerStyle,
  tooltipHeaderStyle,
  tooltipRowStyle,
} from './styling';
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

  // Format bin width succinctly
  const formatBinWidth = (
    start: number,
    end: number,
    isDate: boolean
  ): string => {
    const width = end - start;
    if (!isDate) {
      return formatTooltipValue(width, xField?.units);
    }

    // For time ranges, format as duration
    const seconds = width / 1000;
    if (seconds < 1) {
      return `${Math.round(width)}ms`;
    } else if (seconds < 60) {
      return `${Math.round(seconds)}s`;
    } else if (seconds < 3600) {
      return `${Math.round(seconds / 60)}m`;
    } else if (seconds < 86400) {
      return `${Math.round(seconds / 3600)}h`;
    } else {
      return `${Math.round(seconds / 86400)}d`;
    }
  };

  // Intelligent text truncation function (same as LinePlot)
  const truncateText = (text: string, maxLength: number = 40): string => {
    if (!text || text.length <= maxLength) return text || '';

    // Special handling for labels with " | " separator - truncate both parts
    if (text.includes(' | ')) {
      const parts = text.split(' | ');
      if (parts.length === 2) {
        const [leftPart, rightPart] = parts;
        const availableLength = maxLength - 3; // Reserve space for " | "
        const leftMaxLength = Math.floor(availableLength * 0.5);
        const rightMaxLength = Math.floor(availableLength * 0.5);

        const truncatedLeft =
          leftPart.length > leftMaxLength
            ? leftPart.substring(0, Math.max(1, leftMaxLength - 3)) + '...'
            : leftPart;

        const truncatedRight =
          rightPart.length > rightMaxLength
            ? rightPart.substring(0, Math.max(1, rightMaxLength - 3)) + '...'
            : rightPart;

        return `${truncatedLeft} | ${truncatedRight}`;
      }
    }

    // For other long text, show beginning and end
    if (maxLength < 10) return text.substring(0, maxLength) + '...';

    const startLength = Math.floor((maxLength - 3) * 0.6);
    const endLength = Math.floor((maxLength - 3) * 0.4);

    return (
      text.substring(0, startLength) +
      '...' +
      text.substring(text.length - endLength)
    );
  };

  // Use group directly, with fallback for undefined values
  const displayName = data.group || 'Unknown';
  const truncatedGroup = truncateText(displayName, isFullscreen ? 60 : 30);
  const showTooltip = displayName.length > (isFullscreen ? 60 : 30);

  return (
    <div style={tooltipContainerStyle(isFullscreen)}>
      <div style={tooltipHeaderStyle(isFullscreen)}>
        {binStart !== undefined && binEnd !== undefined
          ? // Show bin range when available
            xField?.type === 'date'
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
              )} (${formatBinWidth(binStart, binEnd, false)})`
          : // Fallback to single point when no bin bounds
          xField?.type === 'date'
          ? formatTooltipDate(data.x)
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
          title={showTooltip ? displayName : undefined}>
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
    () =>
      initialXAxis === 'prediction_index'
        ? {
            key: 'prediction_index',
            label: 'Prediction Index',
            type: 'number' as const,
            render: (v: any) => `${v}`,
          }
        : getXAxisFields(data).find(f => f.key === initialXAxis),
    [initialXAxis, data]
  );
  const yField = getYAxisFields(data).find(f => f.key === initialYAxis);

  const groupBy =
    groupKey === 'op_name'
      ? 'op_name'
      : groupKey === 'traceId'
      ? 'traceId'
      : undefined;

  // Use shared chart data processing logic
  const {points, dataRanges, isDataReady, groupColor} = useChartData(
    data,
    initialXAxis,
    initialYAxis,
    xField,
    yField,
    groupBy,
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

    // Skip binning for prediction index plots - return raw data points grouped by their groups
    if (initialXAxis === 'prediction_index') {
      const grouped: Record<string, any[]> = {};
      transformedPoints.forEach(pt => {
        const group = pt.group || 'Other';
        if (!grouped[group]) grouped[group] = [];
        grouped[group].push({
          x: pt.x,
          y: pt.y,
          originalValue: pt.y,
        });
      });
      return grouped;
    }

    // Get current domain for binning
    const currentXDomain = chartConfig?.xDomain || [
      dataRanges.xMin,
      dataRanges.xMax,
    ];

    // Filter by X domain when binning data
    const filteredPoints = transformedPoints.filter(
      pt => pt.x >= currentXDomain[0] && pt.x <= currentXDomain[1]
    );

    // If no points after filtering, use all points to ensure we have data to display
    const pointsToUse =
      filteredPoints.length > 0 ? filteredPoints : transformedPoints;

    // For stacked bars, we need shared x-axis bins across all groups
    if ((groupBy || colorGroupKey) && pointsToUse.some(pt => pt.group)) {
      // Calculate shared x-axis range from all filtered points
      const xVals = pointsToUse.map(pt => pt.x);
      const xMin = Math.min(...xVals);
      const xMax = Math.max(...xVals);

      if (xMax === xMin) {
        // All points have same x value, group them without binning
        const grouped: Record<string, any[]> = {};
        pointsToUse.forEach(pt => {
          const group = pt.group || 'Other';
          if (!grouped[group]) grouped[group] = [];
          grouped[group].push({
            x: pt.x,
            y: pt.y,
            originalValue: pt.y,
          });
        });
        return grouped;
      }

      // Create shared bins
      const binSize = (xMax - xMin) / binCount;
      const sharedBins: {x: number; groups: Record<string, number[]>}[] =
        Array.from({length: binCount}, (_, i) => ({
          x: xMin + binSize * (i + 0.5),
          groups: {},
        }));

      // Assign points to shared bins
      pointsToUse.forEach(pt => {
        const group = pt.group || 'Other';
        const binIndex = Math.min(
          Math.floor((pt.x - xMin) / binSize),
          binCount - 1
        );

        if (!sharedBins[binIndex].groups[group]) {
          sharedBins[binIndex].groups[group] = [];
        }
        sharedBins[binIndex].groups[group].push(pt.y);
      });

      // Aggregate values in each bin by group
      const result: Record<string, any[]> = {};
      const allGroups = Array.from(
        new Set(pointsToUse.map(pt => pt.group || 'Other'))
      );

      allGroups.forEach(group => {
        result[group] = sharedBins.map(bin => ({
          x: bin.x,
          y: bin.groups[group]
            ? aggregateValues(bin.groups[group], aggregation)
            : 0,
          originalValue: bin.groups[group] ? bin.groups[group][0] : 0,
        }));
      });

      return result;
    }

    // No grouping, use original binning
    return binDataPoints(pointsToUse, binCount, aggregation, false);
  }, [
    data,
    transformedPoints,
    binCount,
    aggregation,
    groupBy,
    colorGroupKey,
    chartConfig?.xDomain,
    dataRanges,
    initialXAxis,
  ]);

  // Prepare stacked bar data for react-vis
  const stackedBarData = React.useMemo(() => {
    if (!groupBy && !colorGroupKey) {
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
  }, [binnedPointsByGroup, groupBy, colorGroupKey, groupColor]);

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
                    // Calculate bin bounds for tooltip
                    let binStart = undefined;
                    let binEnd = undefined;

                    if (
                      initialXAxis !== 'prediction_index' &&
                      binnedPointsByGroup &&
                      Object.keys(binnedPointsByGroup).length > 0
                    ) {
                      // Use the same binning logic as data processing to calculate bounds
                      const currentXDomain = chartConfig?.xDomain || [
                        dataRanges.xMin,
                        dataRanges.xMax,
                      ];
                      const filteredXValues = transformedPoints
                        .filter(
                          pt =>
                            pt.x >= currentXDomain[0] &&
                            pt.x <= currentXDomain[1]
                        )
                        .map(pt => pt.x);

                      if (filteredXValues.length >= 2) {
                        const xMin = Math.min(...filteredXValues);
                        const xMax = Math.max(...filteredXValues);

                        if (xMax > xMin) {
                          const binSize = (xMax - xMin) / binCount;
                          // Find which bin this point belongs to
                          const binIndex = Math.max(
                            0,
                            Math.min(
                              Math.floor(
                                (value.originalPoint.x - xMin) / binSize
                              ),
                              binCount - 1
                            )
                          );
                          binStart = xMin + binSize * binIndex;
                          binEnd = xMin + binSize * (binIndex + 1);
                        }
                      }
                    }

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
