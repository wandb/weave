import 'react-vis/dist/style.css';

import React from 'react';
import {FlexibleXYPlot, LineSeries, MarkSeries, XAxis, YAxis} from 'react-vis';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {WaveLoader} from '../../../../../components/Loaders/WaveLoader';
import {binDataPoints} from './aggregation';
import {useChartData} from './chartDataProcessing';
import {useChartsState} from './ChartsContext';
import {
  ChartAxisField,
  ExtractedCallData,
  getXAxisFields,
  getYAxisFields,
} from './extractData';
import {
  AggregationMethod,
  formatSmartDateRange,
  formatTooltipDate,
  formatTooltipValue,
} from './format';
import {createAxisTickFormatters} from './format';
import {
  chartContainerStyle,
  chartContentStyle,
  createChartMargins,
  tooltipContainerStyle,
  tooltipHeaderStyle,
  tooltipRowStyle,
} from './styling';
import {useChartZoom} from './useChartZoom';

export type LinePlotProps = {
  data: ExtractedCallData[];
  height?: number;
  width?: number;
  initialXAxis?: string;
  initialYAxis?: string;
  binCount?: number;
  aggregation?: AggregationMethod;
  groupKey?: string;
  colorGroupKey?: string;
  hoveredGroup?: string | null;
  chartId?: string;
  xAxisLabel?: string;
  isFullscreen?: boolean;
  traceIdToDisplayName?: Map<string, string>;
  groupByTraceId?: boolean;
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
  binStart: number | null;
  binEnd: number | null;
  binXStart: number | null; // Pixel position of bin start
  binXEnd: number | null; // Pixel position of bin end
  intersectionPoints: LinePlotTooltipData[];
};

const LinePlotTooltip: React.FC<{
  data: LinePlotTooltipData[];
  xField?: ChartAxisField;
  yField?: ChartAxisField;
  isFullscreen?: boolean;
  traceIdToDisplayName?: Map<string, string>;
  dataX?: number;
  binStart?: number;
  binEnd?: number;
}> = ({
  data,
  xField,
  yField,
  isFullscreen,
  traceIdToDisplayName,
  dataX,
  binStart,
  binEnd,
}) => {
  // Filter out invalid values and sort by y value
  const validData = data
    ? data.filter(d => !isNaN(d.y)).sort((a, b) => b.y - a.y)
    : [];

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
          : validData.length > 0
          ? // Fallback to single point when no bin bounds
            xField?.type === 'date'
            ? formatTooltipDate(validData[0].x)
            : formatTooltipValue(validData[0].x, xField?.units)
          : // Show current position when no data
          xField?.type === 'date' && dataX
          ? formatTooltipDate(dataX)
          : dataX
          ? formatTooltipValue(dataX, xField?.units)
          : 'No position'}
      </div>
      {validData.length === 0 ? (
        <div
          style={{
            ...tooltipRowStyle(isFullscreen),
            color: '#8F8F8F',
            // fontStyle: 'italic',
            textAlign: 'center',
            fontFamily: 'inconsolata',
          }}>
          No data
        </div>
      ) : (
        validData.map((item, index) => {
          // Use display name if available, otherwise use the group (trace ID)
          // Group names are already parsed at the data processing level
          const displayName =
            traceIdToDisplayName?.get(item.group) || item.group;
          const truncatedGroup = truncateText(
            displayName,
            isFullscreen ? 60 : 30
          );
          const showTooltip = displayName.length > (isFullscreen ? 60 : 30);

          return (
            <div
              key={index}
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
                  color: item.color,
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
                  color: item.color,
                  fontWeight: 'bold',
                }}>
                {formatTooltipValue(item.y, yField?.units)}
              </span>
            </div>
          );
        })
      )}
    </div>
  );
};

export const LinePlot: React.FC<LinePlotProps> = ({
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
  traceIdToDisplayName,
  groupByTraceId,
}) => {
  const globalState = useChartsState();

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
    colorGroupKey,
    groupByTraceId
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

  // State for tooltips and crosshair
  const [hintValue, setHintValue] = React.useState<any>(null);
  const [crosshair, setCrosshair] = React.useState<CrosshairState>({
    x: null,
    y: null,
    dataX: null,
    binStart: null,
    binEnd: null,
    binXStart: null,
    binXEnd: null,
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

  const binnedPointsByGroup = React.useMemo(() => {
    if (!data || data.length === 0 || transformedPoints.length === 0) {
      return {};
    }

    // Skip binning for prediction index plots - return raw data points grouped by their groups
    if (initialXAxis === 'prediction_index') {
      const grouped: Record<string, any[]> = {};
      transformedPoints.forEach(pt => {
        const group = pt.group || 'all';
        if (!grouped[group]) grouped[group] = [];
        grouped[group].push({
          x: pt.x,
          y: pt.y,
          originalValue: pt.y,
        });
      });
      return grouped;
    }

    // Get current domain for binning - use chart domain if zoomed, otherwise full data range
    const currentXDomain = chartConfig?.xDomain || [
      dataRanges.xMin,
      dataRanges.xMax,
    ];

    // Filter points by current X domain for rebinning (like bar chart)
    const filteredPoints = transformedPoints.filter(
      pt => pt.x >= currentXDomain[0] && pt.x <= currentXDomain[1]
    );

    // Always use filtered points for rebinning - this ensures proper rebinning on zoom
    // If no points in the current domain, we'll get empty bins which is correct behavior
    return binDataPoints(
      filteredPoints,
      binCount,
      aggregation,
      !!(groupBy || colorGroupKey)
    );
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

  // Prepare data for react-vis
  const lineSeriesData = React.useMemo(() => {
    const currentYDomain = currentDomains.yDomain;

    if (groupBy || colorGroupKey) {
      const result = Object.entries(binnedPointsByGroup).map(
        ([group, points]) => {
          const color = groupColor(group);

          // Filter data to only include points within visible y-domain
          // Also filter out NaN values that represent missing data for this group in certain bins
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

      // For prediction index plots (no binning), use the closest point approach
      if (initialXAxis === 'prediction_index') {
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
      } else {
        // For binned data, use the same domain-based binning logic as the data processing
        const currentXDomain = chartConfig?.xDomain || [
          dataRanges.xMin,
          dataRanges.xMax,
        ];
        const filteredXValues = transformedPoints
          .filter(pt => pt.x >= currentXDomain[0] && pt.x <= currentXDomain[1])
          .map(pt => pt.x);

        if (filteredXValues.length < 2) {
          // If we have less than 2 points in the current domain, fall back to closest point logic
          lineSeriesData.forEach(series => {
            if (series.data.length === 0) return;
            const closestPoint = series.data[0];
            intersections.push({
              x: closestPoint.x,
              y: closestPoint.y,
              group: series.group,
              color: series.color,
            });
          });
        } else {
          const xMin = Math.min(...filteredXValues);
          const xMax = Math.max(...filteredXValues);

          if (xMax > xMin) {
            const binSize = (xMax - xMin) / binCount;

            // Find which bin the mouse position falls into
            const binIndex = Math.floor((dataX - xMin) / binSize);
            const clampedBinIndex = Math.max(
              0,
              Math.min(binIndex, binCount - 1)
            );

            // Calculate the center of this bin (where data points should be)
            const binCenter = xMin + binSize * (clampedBinIndex + 0.5);

            // Find all points that belong to this bin by looking for the bin center
            lineSeriesData.forEach(series => {
              if (series.data.length === 0) return;

              // Find the point that matches this bin center (with small tolerance for floating point)
              const targetPoint = series.data.find(point => {
                return Math.abs(point.x - binCenter) < binSize * 0.1;
              });

              if (targetPoint) {
                intersections.push({
                  x: targetPoint.x,
                  y: targetPoint.y,
                  group: series.group,
                  color: series.color,
                });
              }
            });
          }
        }
      }

      return intersections.sort((a, b) => b.y - a.y);
    },
    [
      lineSeriesData,
      currentDomains.xDomain,
      initialXAxis,
      transformedPoints,
      binCount,
      chartConfig?.xDomain,
      dataRanges,
    ]
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

        // Calculate bin boundaries for shaded area
        let binStart = null;
        let binEnd = null;
        let binXStart = null;
        let binXEnd = null;

        if (initialXAxis === 'prediction_index') {
          // For prediction index, no binning - just snap to nearest point
          if (intersectionPoints.length > 0) {
            binStart = intersectionPoints[0].x;
            binEnd = intersectionPoints[0].x;
            const pointXRatio =
              (binStart - currentDomains.xDomain[0]) /
              (currentDomains.xDomain[1] - currentDomains.xDomain[0]);
            const pointPixelX = chartMargins.left + pointXRatio * plotWidth;
            binXStart = pointPixelX;
            binXEnd = pointPixelX;
          }
        } else {
          // For binned data, use the same domain-based binning logic as the data processing
          const currentXDomain = chartConfig?.xDomain || [
            dataRanges.xMin,
            dataRanges.xMax,
          ];
          const filteredXValues = transformedPoints
            .filter(
              pt => pt.x >= currentXDomain[0] && pt.x <= currentXDomain[1]
            )
            .map(pt => pt.x);

          if (filteredXValues.length >= 2) {
            const xMin = Math.min(...filteredXValues);
            const xMax = Math.max(...filteredXValues);

            if (xMax > xMin) {
              const binSize = (xMax - xMin) / binCount;

              // Find which bin the mouse position falls into
              const binIndex = Math.floor((dataX - xMin) / binSize);
              const clampedBinIndex = Math.max(
                0,
                Math.min(binIndex, binCount - 1)
              );

              // Calculate actual bin boundaries (not center-based)
              binStart = xMin + binSize * clampedBinIndex;
              binEnd = xMin + binSize * (clampedBinIndex + 1);

              // Convert to pixel coordinates
              const binStartRatio =
                (binStart - currentDomains.xDomain[0]) /
                (currentDomains.xDomain[1] - currentDomains.xDomain[0]);
              const binEndRatio =
                (binEnd - currentDomains.xDomain[0]) /
                (currentDomains.xDomain[1] - currentDomains.xDomain[0]);

              binXStart = chartMargins.left + binStartRatio * plotWidth;
              binXEnd = chartMargins.left + binEndRatio * plotWidth;
            }
          }
        }

        setCrosshair({
          x: clampedX,
          y: rawY,
          dataX: dataX,
          binStart,
          binEnd,
          binXStart,
          binXEnd,
          intersectionPoints,
        });

        // Always set hint value for tooltip when mouse is over chart area
        setHintValue({
          x: dataX,
          y: currentDomains.yDomain[1],
          tooltipData: intersectionPoints, // This can be empty array - tooltip will handle it
        });
      } else {
        setCrosshair({
          x: null,
          y: null,
          dataX: null,
          binStart: null,
          binEnd: null,
          binXStart: null,
          binXEnd: null,
          intersectionPoints: [],
        });
        setHintValue(null);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      chartMargins,
      findIntersectionPoints,
      currentDomains,
      transformedPoints,
      binCount,
      chartConfig?.xDomain,
      dataRanges,
    ]
  );

  // Use the flexible zoom hook for paint-to-zoom functionality with smart zoom behavior
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
    smartZoom: true, // Enable smart zoom behavior
  });

  // Handle mouse leave
  const handleMouseLeaveChart = React.useCallback(() => {
    setCrosshair({
      x: null,
      y: null,
      dataX: null,
      binStart: null,
      binEnd: null,
      binXStart: null,
      binXEnd: null,
      intersectionPoints: [],
    });
    setHintValue(null);
  }, []);

  // Crosshair shaded area style
  const crosshairShadeStyle = React.useMemo(() => {
    if (!crosshair.binXStart || !crosshair.binXEnd || !containerRef.current)
      return null;

    const containerRect = containerRef.current.getBoundingClientRect();
    const plotTop = chartMargins.top;
    const plotBottom = containerRect.height - chartMargins.bottom;

    return {
      position: 'absolute' as const,
      left: crosshair.binXStart,
      top: plotTop,
      width: Math.max(1, crosshair.binXEnd - crosshair.binXStart),
      height: plotBottom - plotTop,
      backgroundColor: 'rgba(102, 102, 102, 0.15)',
      pointerEvents: 'none' as const,
      zIndex: 5,
    };
  }, [crosshair.binXStart, crosshair.binXEnd, chartMargins, containerRef]);

  const circleMarkersData = React.useMemo(() => {
    return crosshair.intersectionPoints.map(point => ({
      group: point.group,
      color: point.color,
      data: [{x: point.x, y: point.y}],
    }));
  }, [crosshair.intersectionPoints]);

  const tooltipPosition = React.useMemo(() => {
    if (!hintValue || !containerRef.current)
      return {x: 0, y: 0, anchorRight: false};

    const containerRect = containerRef.current.getBoundingClientRect();
    const tooltipOffset = isFullscreen ? 45 : 20;

    // Use bin center for positioning when available, otherwise use mouse position
    const referenceX =
      crosshair.binXStart && crosshair.binXEnd
        ? (crosshair.binXStart + crosshair.binXEnd) / 2
        : crosshair.x || 0;

    // Determine which side of chart the reference point is on
    const isLeftSide = referenceX < containerRect.width / 2;

    // Dynamic positioning relative to reference point
    const fixedY = chartMargins.top + tooltipOffset;

    let x: number;
    let anchorRight = false;

    if (isLeftSide) {
      // Reference on left side: position tooltip to the right
      x = referenceX + tooltipOffset;
      anchorRight = false;
    } else {
      // Reference on right side: anchor tooltip's right edge to the left
      x = containerRect.width - referenceX + tooltipOffset;
      anchorRight = true;
    }

    return {x, y: fixedY, anchorRight};
  }, [
    isFullscreen,
    crosshair.x,
    crosshair.binXStart,
    crosshair.binXEnd,
    hintValue,
    chartMargins,
    containerRef,
  ]);

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
          onDoubleClick={handleZoomDoubleClick}>
          <span style={{fontSize: '14px', marginBottom: '8px'}}>
            No data to display
          </span>
          <span style={{fontSize: '12px', fontStyle: 'italic'}}>
            Double-click to reset zoom
          </span>
        </div>
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
                  tickFormat={unifiedYTickFormatter}
                  tickTotal={6}
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
                {hintValue && (crosshair.x || crosshair.binXStart) && (
                  <div
                    style={{
                      position: 'absolute',
                      ...(tooltipPosition.anchorRight
                        ? {right: tooltipPosition.x}
                        : {left: tooltipPosition.x}),
                      top: tooltipPosition.y,
                      zIndex: 20,
                      pointerEvents: 'none',
                    }}>
                    <LinePlotTooltip
                      data={hintValue.tooltipData}
                      xField={xField}
                      yField={yField}
                      isFullscreen={isFullscreen}
                      traceIdToDisplayName={traceIdToDisplayName}
                      dataX={crosshair.dataX ?? undefined}
                      binStart={crosshair.binStart ?? undefined}
                      binEnd={crosshair.binEnd ?? undefined}
                    />
                  </div>
                )}
              </FlexibleXYPlot>
              {crosshairShadeStyle && <div style={crosshairShadeStyle} />}
              {selectionStyle && <div style={selectionStyle} />}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
