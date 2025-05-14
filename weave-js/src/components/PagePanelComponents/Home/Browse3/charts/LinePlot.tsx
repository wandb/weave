import 'react-vis/dist/style.css';

import React from 'react';
import {FlexibleXYPlot, LineSeries, MarkSeries, XAxis, YAxis} from 'react-vis';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {WaveLoader} from '../../../../../components/Loaders/WaveLoader';
import {useChartsState} from './ChartsContext';
import {
  AggregationMethod,
  binDataPoints,
  calculateOptimalTickCount,
  chartContainerStyle,
  chartContentStyle,
  COLOR_PALETTE,
  createAxisTickFormatters,
  createChartMargins,
  DataPoint,
  formatTooltipDate,
  formatTooltipValue,
  getGroupValues,
  tooltipContainerStyle,
  tooltipHeaderStyle,
  tooltipRowStyle,
} from './chartUtils';
import {
  ChartAxisField,
  ExtractedCallData,
  getInputOutputFieldValue,
  getOpNameDisplay,
  getXAxisFields,
  getYAxisFields,
} from './extractData';
import {useChartZoom} from './useChartZoom';

export type LinePlotProps = {
  data: ExtractedCallData[];
  height?: number;
  width?: number;
  initialYAxis?: string;
  binCount?: number;
  aggregation?: AggregationMethod;
  groupKey?: string;
  colorGroupKey?: string;
  hoveredGroup?: string | null;
  chartId?: string;
  xAxisLabel?: string;
  isFullscreen?: boolean;
};

type LinePlotTooltipData = {
  x: number;
  y: number;
  group: string;
  color: string;
};

type CrosshairState = {
  x: number | null;
  y: number | null;
  dataX: number | null;
  intersectionPoints: LinePlotTooltipData[];
};

const LinePlotTooltip: React.FC<{
  data: LinePlotTooltipData[];
  xField?: ChartAxisField;
  yField?: ChartAxisField;
  isFullscreen?: boolean;
}> = ({data, xField, yField, isFullscreen}) => {
  if (!data || data.length === 0) return null;

  // Filter out zero values and sort by y value
  const validData = data
    .filter(d => d.y !== 0 && !isNaN(d.y))
    .sort((a, b) => b.y - a.y);

  if (validData.length === 0) return null;

  // Intelligent text truncation function
  const truncateText = (text: string, maxLength: number = 40): string => {
    if (text.length <= maxLength) return text;

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

  return (
    <div style={tooltipContainerStyle(isFullscreen)}>
      <div style={tooltipHeaderStyle(isFullscreen)}>
        {xField?.type === 'date'
          ? formatTooltipDate(validData[0].x)
          : formatTooltipValue(validData[0].x, xField?.units)}
      </div>
      {validData.map((item, index) => {
        const truncatedGroup = truncateText(item.group, isFullscreen ? 60 : 30);
        const showTooltip = item.group.length > (isFullscreen ? 60 : 30);

        return (
          <div
            key={index}
            style={{
              ...tooltipRowStyle(isFullscreen),
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: isFullscreen ? '16px' : '12px',
            }}>
            <span
              style={{
                color: item.color,
                fontWeight: 'bold',
                flex: '1 1 auto',
                minWidth: 0,
              }}
              title={showTooltip ? item.group : undefined}>
              {truncatedGroup}
            </span>
            <span
              style={{
                flex: '0 0 auto',
                textAlign: 'right',
                minWidth: isFullscreen ? '60px' : '50px',
              }}>
              {formatTooltipValue(item.y, yField?.units)}
            </span>
          </div>
        );
      })}
    </div>
  );
};

export const LinePlot: React.FC<LinePlotProps> = ({
  data,
  height,
  width,
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

  // Get chart config for domain refinement
  const chartConfig = chartId
    ? globalState.charts.find(c => c.id === chartId)
    : undefined;

  const initialXAxis = 'started_at';
  const xField = getXAxisFields(data).find(f => f.key === initialXAxis);
  const yField = getYAxisFields(data).find(f => f.key === initialYAxis);

  const groupBy = groupKey === 'op_name' ? 'op_name' : undefined;

  // Check if there are multiple operation names in the data
  const hasMultipleOperations = React.useMemo(() => {
    const uniqueOpNames = new Set(
      data.map(d => getOpNameDisplay(d.op_name)).filter(Boolean)
    );
    return uniqueOpNames.size > 1;
  }, [data]);

  // Create color groups based on colorGroupKey and optionally nested with op_name
  const colorGroups = React.useMemo(() => {
    if (!colorGroupKey) {
      // No color grouping, use op_name grouping if available
      return getGroupValues(data, groupBy);
    }

    const groups = new Set<string>();
    data.forEach(d => {
      let colorGroupValue = '';

      // Get the color group value from input/output fields
      if (
        colorGroupKey.startsWith('input.') ||
        colorGroupKey.startsWith('output.')
      ) {
        const value = getInputOutputFieldValue(d, colorGroupKey);
        colorGroupValue = value?.toString() || 'Unknown';
      } else if (colorGroupKey === 'op_name') {
        colorGroupValue = getOpNameDisplay(d.op_name) || 'Unknown';
      }

      // Create nested grouping if there are multiple operations
      if (hasMultipleOperations && colorGroupKey !== 'op_name') {
        const opName = getOpNameDisplay(d.op_name) || 'Unknown';
        groups.add(`${opName} | ${colorGroupValue}`);
      } else {
        groups.add(colorGroupValue);
      }
    });

    return Array.from(groups).sort();
  }, [data, groupBy, colorGroupKey, hasMultipleOperations]);

  const groupColorMap = React.useMemo(() => {
    const map: Record<string, string> = {};
    colorGroups.forEach((group, idx) => {
      map[group] = COLOR_PALETTE[idx % COLOR_PALETTE.length];
    });
    return map;
  }, [colorGroups]);

  const groupColor = React.useCallback(
    (group: string) => {
      if (colorGroupKey) {
        return groupColorMap[group] || '#000';
      }
      // Fallback to original logic for non-colorGroupKey grouping
      const groupValues = getGroupValues(data, groupBy);
      const idx = groupValues.indexOf(group);
      return COLOR_PALETTE[idx % COLOR_PALETTE.length];
    },
    [colorGroupKey, groupColorMap, data, groupBy]
  );

  // Convert raw data to data points
  const points = React.useMemo(() => {
    if (!data || data.length === 0) {
      return [];
    }
    const result = data
      .map(d => {
        const opNameGroup = getOpNameDisplay(d.op_name);

        // Determine the color group for this data point
        let colorGroup = '';
        if (colorGroupKey) {
          if (
            colorGroupKey.startsWith('input.') ||
            colorGroupKey.startsWith('output.')
          ) {
            const value = getInputOutputFieldValue(d, colorGroupKey);
            colorGroup = value?.toString() || 'Unknown';
          } else if (colorGroupKey === 'op_name') {
            colorGroup = getOpNameDisplay(d.op_name) || 'Unknown';
          }

          // Create nested grouping if there are multiple operations
          if (
            hasMultipleOperations &&
            colorGroupKey !== 'op_name' &&
            opNameGroup
          ) {
            colorGroup = `${opNameGroup} | ${colorGroup}`;
          }
        } else if (groupBy && opNameGroup) {
          // Fallback to op_name grouping if no color grouping is specified
          colorGroup = opNameGroup;
        }

        // Extract x value - handle both built-in fields and input/output fields
        let xValue: any;
        if (
          initialXAxis.startsWith('input.') ||
          initialXAxis.startsWith('output.')
        ) {
          xValue = getInputOutputFieldValue(d, initialXAxis);
        } else {
          xValue = d[initialXAxis as keyof ExtractedCallData];
        }

        // Extract y value - handle both built-in fields and input/output fields
        let yValue: any;
        if (
          initialYAxis.startsWith('input.') ||
          initialYAxis.startsWith('output.')
        ) {
          yValue = getInputOutputFieldValue(d, initialYAxis);
        } else {
          yValue = d[initialYAxis as keyof ExtractedCallData];
        }

        return {
          x:
            xField?.type === 'date'
              ? new Date(xValue as any).getTime()
              : xValue,
          y:
            yField?.type === 'date'
              ? new Date(yValue as any).getTime()
              : yValue,
          display_name: d.display_name || '',
          group: colorGroup || (groupBy ? opNameGroup : undefined),
        };
      })
      .filter(
        pt =>
          pt.x !== undefined &&
          pt.y !== undefined &&
          typeof pt.x === 'number' &&
          typeof pt.y === 'number' &&
          !isNaN(pt.x) &&
          !isNaN(pt.y)
      ) as DataPoint[];

    return result;
  }, [
    data,
    initialXAxis,
    initialYAxis,
    xField,
    yField,
    groupBy,
    colorGroupKey,
    hasMultipleOperations,
  ]);

  // Calculate data ranges for domain conversion
  const dataRanges = React.useMemo(() => {
    if (points.length === 0) return {xMin: 0, xMax: 1, yMin: 0, yMax: 1};
    const xValues = points.map(p => p.x);
    const yValues = points.map(p => p.y);
    return {
      xMin: Math.min(...xValues),
      xMax: Math.max(...xValues),
      yMin: Math.min(...yValues),
      yMax: Math.max(...yValues),
    };
  }, [points]);

  // Comprehensive loading state check
  const isDataReady = React.useMemo(() => {
    return (
      data &&
      data.length > 0 &&
      points.length > 0 &&
      xField &&
      yField &&
      dataRanges.xMin !== dataRanges.xMax &&
      dataRanges.yMin !== dataRanges.yMax
    );
  }, [data, points, xField, yField, dataRanges]);

  // State for tooltips and crosshair
  const [hintValue, setHintValue] = React.useState<any>(null);
  const [crosshair, setCrosshair] = React.useState<CrosshairState>({
    x: null,
    y: null,
    dataX: null,
    intersectionPoints: [],
  });

  // Chart margins and padding constants
  const chartMargins = React.useMemo(
    () => createChartMargins(isFullscreen),
    [isFullscreen]
  );

  // Current domains for coordinate conversion
  const currentDomains = React.useMemo(
    () => ({
      xDomain: (chartConfig?.xDomain || [dataRanges.xMin, dataRanges.xMax]) as [
        number,
        number
      ],
      yDomain: (chartConfig?.yDomain || [dataRanges.yMin, dataRanges.yMax]) as [
        number,
        number
      ],
    }),
    [chartConfig?.xDomain, chartConfig?.yDomain, dataRanges]
  );

  // Create unified tick formatters using chartUtils
  const {
    xTickFormatter: unifiedXTickFormatter,
    yTickFormatter: unifiedYTickFormatter,
  } = React.useMemo(
    () =>
      createAxisTickFormatters(
        xField,
        yField,
        currentDomains.xDomain,
        currentDomains.yDomain
      ),
    [xField, yField, currentDomains.xDomain, currentDomains.yDomain]
  );

  // Calculate optimal number of ticks using unified utility
  const unifiedOptimalTickCount = React.useMemo(() => {
    // Use reasonable defaults for FlexibleXYPlot since we don't track dimensions
    const defaultDimensions = {width: 800, height: 400};
    return calculateOptimalTickCount(
      defaultDimensions,
      chartMargins,
      xField,
      currentDomains.xDomain
    );
  }, [chartMargins, xField, currentDomains.xDomain]);

  // Calculate optimal number of Y-axis ticks
  const unifiedOptimalYTickCount = React.useMemo(() => {
    // Use reasonable defaults for FlexibleXYPlot since we don't track dimensions
    const defaultDimensions = {width: 800, height: 400};
    return calculateOptimalTickCount(
      defaultDimensions,
      chartMargins,
      yField,
      currentDomains.yDomain,
      'y'
    );
  }, [chartMargins, yField, currentDomains.yDomain]);

  const binnedPointsByGroup = React.useMemo(() => {
    if (!data || data.length === 0 || points.length === 0) {
      return {};
    }

    // Get current domain for binning
    const currentXDomain = chartConfig?.xDomain || [
      dataRanges.xMin,
      dataRanges.xMax,
    ];

    // For line plots, only filter by X domain when binning data
    // The Y domain should only affect the chart display, not the data that gets binned
    const filteredPoints = points.filter(
      pt => pt.x >= currentXDomain[0] && pt.x <= currentXDomain[1]
    );

    if (filteredPoints.length === 0) {
      return {};
    }

    // Use binDataPoints with the filtered data
    // This will automatically calculate bins based on the filtered x-range
    return binDataPoints(
      filteredPoints,
      binCount,
      aggregation,
      !!(groupBy || colorGroupKey)
    );
  }, [
    data,
    points,
    binCount,
    aggregation,
    groupBy,
    colorGroupKey,
    chartConfig?.xDomain,
    dataRanges,
  ]);

  // Prepare data for react-vis
  const lineSeriesData = React.useMemo(() => {
    const currentYDomain = currentDomains.yDomain;

    if (
      (groupBy || colorGroupKey) &&
      Object.keys(binnedPointsByGroup).length > 1
    ) {
      const result = Object.entries(binnedPointsByGroup).map(
        ([group, points]) => {
          const color = groupColor(group);

          // Filter data to only include points within visible y-domain
          const filteredData = points
            .filter(
              point =>
                !isNaN(point.x) &&
                !isNaN(point.y) &&
                point.y >= currentYDomain[0] &&
                point.y <= currentYDomain[1]
            )
            .map(point => ({x: point.x, y: point.y}));

          return {
            group,
            color,
            data: filteredData,
            opacity: 1,
            style: {strokeWidth: 2},
          };
        }
      );
      return result;
    }

    // Filter data to only include points within visible y-domain
    const allData = (binnedPointsByGroup.all || [])
      .filter(
        point =>
          !isNaN(point.x) &&
          !isNaN(point.y) &&
          point.y >= currentYDomain[0] &&
          point.y <= currentYDomain[1]
      )
      .map(point => ({
        x: point.x,
        y: point.y,
      }));

    const result = [
      {
        group: 'Value',
        color: TEAL_600,
        data: allData,
        opacity: 1,
        style: {strokeWidth: 2},
      },
    ];
    return result;
  }, [
    binnedPointsByGroup,
    groupBy,
    colorGroupKey,
    groupColor,
    currentDomains.yDomain,
  ]);

  // Find intersection points for crosshair
  const findIntersectionPoints = React.useCallback(
    (dataX: number): LinePlotTooltipData[] => {
      const intersections: LinePlotTooltipData[] = [];

      lineSeriesData.forEach(series => {
        if (series.data.length === 0) return;

        // Find the closest point in this series by x-value
        const closestPoint = series.data.reduce((closest, current) => {
          const currentDistance = Math.abs(current.x - dataX);
          const closestDistance = Math.abs(closest.x - dataX);
          return currentDistance < closestDistance ? current : closest;
        });

        // Only include if the point is reasonably close to the crosshair
        const tolerance =
          (currentDomains.xDomain[1] - currentDomains.xDomain[0]) * 0.02;
        if (Math.abs(closestPoint.x - dataX) <= tolerance) {
          intersections.push({
            x: closestPoint.x,
            y: closestPoint.y,
            group: series.group,
            color: series.color,
          });
        }
      });

      return intersections.sort((a, b) => b.y - a.y);
    },
    [lineSeriesData, currentDomains.xDomain]
  );

  // Custom mouse move handler for crosshair functionality
  const handleMouseMoveWithCrosshair = React.useCallback(
    (event: React.MouseEvent) => {
      if (!containerRef.current) return;

      const rect = containerRef.current.getBoundingClientRect();
      const rawX = event.clientX - rect.left;
      const rawY = event.clientY - rect.top;

      // Get current container dimensions
      const currentDimensions = {
        width: rect.width,
        height: rect.height,
      };

      // Check if mouse is within the plot area and clamp to boundaries
      const plotLeft = chartMargins.left;
      const plotRight = currentDimensions.width - chartMargins.right;
      const plotTop = chartMargins.top;
      const plotBottom = currentDimensions.height - chartMargins.bottom;

      if (
        rawX >= plotLeft &&
        rawX <= plotRight &&
        rawY >= plotTop &&
        rawY <= plotBottom
      ) {
        const clampedX = Math.max(plotLeft, Math.min(rawX, plotRight));

        // Convert to data coordinates (simplified calculation)
        const plotWidth =
          currentDimensions.width - chartMargins.left - chartMargins.right;
        const xRatio = (clampedX - chartMargins.left) / plotWidth;
        const dataX =
          currentDomains.xDomain[0] +
          xRatio * (currentDomains.xDomain[1] - currentDomains.xDomain[0]);

        const intersectionPoints = findIntersectionPoints(dataX);

        setCrosshair({
          x: clampedX,
          y: rawY,
          dataX: dataX,
          intersectionPoints,
        });

        // Set hint value for tooltip
        if (intersectionPoints.length > 0) {
          setHintValue({
            x: dataX,
            y: currentDomains.yDomain[1],
            tooltipData: intersectionPoints,
          });
        } else {
          setHintValue(null);
        }
      } else {
        setCrosshair({
          x: null,
          y: null,
          dataX: null,
          intersectionPoints: [],
        });
        setHintValue(null);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [chartMargins, findIntersectionPoints, currentDomains]
  );

  // Use the flexible zoom hook for paint-to-zoom functionality
  const {
    containerRef,
    selectionStyle,
    handleMouseDown,
    handleMouseMove: handleZoomMouseMove,
    handleMouseUp,
    handleDoubleClick: handleZoomDoubleClick,
  } = useChartZoom({
    chartId,
    xDomain: currentDomains.xDomain,
    yDomain: currentDomains.yDomain,
    isFullscreen,
    onMouseMove: handleMouseMoveWithCrosshair,
  });

  // Handle mouse leave
  const handleMouseLeaveChart = React.useCallback(() => {
    setCrosshair({
      x: null,
      y: null,
      dataX: null,
      intersectionPoints: [],
    });
    setHintValue(null);
  }, []);

  // Crosshair line style
  const crosshairLineStyle = React.useMemo(() => {
    if (!crosshair.x || !containerRef.current) return null;

    const containerRect = containerRef.current.getBoundingClientRect();
    const plotTop = chartMargins.top;
    const plotBottom = containerRect.height - chartMargins.bottom;

    return {
      position: 'absolute' as const,
      left: crosshair.x,
      top: plotTop,
      width: '0px',
      height: plotBottom - plotTop,
      borderLeft: '1px dotted #666',
      pointerEvents: 'none' as const,
      zIndex: 5,
    };
  }, [crosshair.x, chartMargins, containerRef]);

  const circleMarkersData = React.useMemo(() => {
    return crosshair.intersectionPoints.map(point => ({
      group: point.group,
      color: point.color,
      data: [{x: point.x, y: point.y}],
    }));
  }, [crosshair.intersectionPoints]);

  const tooltipPosition = React.useMemo(() => {
    if (!crosshair.x || !hintValue || !containerRef.current)
      return {x: 0, y: 0};

    const containerRect = containerRef.current.getBoundingClientRect();
    const tooltipOffset = 5;

    // Determine which side of chart the cursor is on
    const isLeftSide = crosshair.x < containerRect.width / 2;

    // Fixed positions for tooltip
    const fixedY = chartMargins.top + tooltipOffset;

    const fixedXRight = 0.5 * containerRect.width;
    const fixedXLeft = chartMargins.left + tooltipOffset;

    const x = isLeftSide ? fixedXRight : fixedXLeft;
    const y = fixedY;

    return {x, y};
  }, [crosshair.x, hintValue, chartMargins, containerRef]);

  return (
    <div style={chartContainerStyle}>
      {!isDataReady ? (
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
        <span style={{color: '#8F8F8F'}}>No data to display</span>
      ) : (
        <div style={chartContentStyle}>
          {xField && yField && (
            <div
              className="line-plot-container"
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
              onMouseMove={handleZoomMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseLeaveChart}
              onDoubleClick={handleZoomDoubleClick}>
              <FlexibleXYPlot
                xDomain={chartConfig?.xDomain}
                yDomain={chartConfig?.yDomain}
                margin={chartMargins}>
                <XAxis
                  tickFormat={unifiedXTickFormatter}
                  tickTotal={unifiedOptimalTickCount}
                  title={xAxisLabel}
                  style={{
                    text: {
                      fontSize: isFullscreen ? '14px' : '10px',
                      fontFamily: 'Source Sans Pro',
                    },
                  }}
                />
                <YAxis
                  tickFormat={unifiedYTickFormatter}
                  tickTotal={unifiedOptimalYTickCount}
                  style={{
                    text: {
                      fontSize: isFullscreen ? '14px' : '10px',
                      fontFamily: 'Source Sans Pro',
                    },
                  }}
                />
                {lineSeriesData.map((series, index) => (
                  <LineSeries
                    key={series.group}
                    data={series.data}
                    color={series.color}
                    opacity={series.opacity}
                    style={series.style}
                  />
                ))}
                {circleMarkersData.map((marker, index) => (
                  <MarkSeries
                    key={`marker-${marker.group}`}
                    data={marker.data}
                    color={marker.color}
                    fill={marker.color}
                    stroke="#fff"
                    strokeWidth={2}
                  />
                ))}
                {hintValue && crosshair.x && (
                  <div
                    style={{
                      position: 'absolute',
                      left: tooltipPosition.x,
                      top: tooltipPosition.y,
                      zIndex: 20,
                      pointerEvents: 'none',
                    }}>
                    <LinePlotTooltip
                      data={hintValue.tooltipData}
                      xField={xField}
                      yField={yField}
                      isFullscreen={isFullscreen}
                    />
                  </div>
                )}
              </FlexibleXYPlot>
              {crosshairLineStyle && <div style={crosshairLineStyle} />}
              {selectionStyle && <div style={selectionStyle} />}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
