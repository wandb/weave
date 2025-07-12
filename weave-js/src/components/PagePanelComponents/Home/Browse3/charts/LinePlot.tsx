/*
  LinePlot.tsx

  This file contains the line plot implementation for trace plots.
*/
import 'react-vis/dist/style.css';

import React from 'react';
import {FlexibleXYPlot, LineSeries, MarkSeries, XAxis, YAxis} from 'react-vis';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {WaveLoader} from '../../../../../components/Loaders/WaveLoader';
import {calculateBinBoundaries, createBinnedPointsByGroup} from './aggregation';
import {useChartData} from './chartDataProcessing';
import {getXAxisFields, getYAxisFields} from './extractData';
import {
  createAxisTickFormatters,
  formatBinWidth,
  formatSmartDateRange,
  formatTooltipDate,
  formatTooltipValue,
  truncateText,
} from './format';
import {
  chartContainerStyle,
  chartContentStyle,
  createAxisStyle,
  createChartMargins,
  tooltipContainerStyle,
  tooltipHeaderStyle,
  tooltipRowStyle,
} from './styling';
import {AggregationMethod, BinningMode, ChartAxisField, ExtractedCallData} from './types';
import {useChartZoom} from './useChartZoom';

export type LinePlotProps = {
  data: ExtractedCallData[];
  initialXAxis?: string;
  initialYAxis?: string;
  binCount?: number;
  binningMode?: BinningMode;
  aggregation?: AggregationMethod;
  groupKeys?: string[];
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
  dataX?: number;
  binStart?: number;
  binEnd?: number;
}> = ({data, xField, yField, isFullscreen, dataX, binStart, binEnd}) => {
  // Filter out invalid values and sort by y value
  const validData = data
    ? data.filter(d => !isNaN(d.y)).sort((a, b) => b.y - a.y)
    : [];

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
              )} (${formatBinWidth(binStart, binEnd, false, xField?.units)})`
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
          const displayName = item.group;
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
  initialXAxis = 'started_at',
  initialYAxis = 'latency',
  binCount = 20,
  binningMode = 'absolute',
  aggregation = 'average',
  groupKeys,
  xAxisLabel,
  isFullscreen,
}) => {
  const [currentXDomain, setCurrentXDomain] = React.useState<
    [number, number] | undefined
  >();
  const [currentYDomain, setCurrentYDomain] = React.useState<
    [number, number] | undefined
  >();

  const xField = React.useMemo(
    () => getXAxisFields(data).find(f => f.key === initialXAxis),
    [initialXAxis, data]
  );
  const yField = getYAxisFields(data).find(f => f.key === initialYAxis);

  const {points, dataRanges, isDataReady, groupColor} = useChartData(
    data,
    initialXAxis,
    initialYAxis,
    xField,
    yField,
    groupKeys
  );

  // Handle domain changes from zoom
  const handleDomainChange = React.useCallback(
    (xDomain: [number, number], yDomain: [number, number] | undefined) => {
      setCurrentXDomain(xDomain);
      setCurrentYDomain(yDomain === undefined ? undefined : yDomain);
    },
    []
  );

  // Initialize state to match double-click reset behavior once data is ready
  const [hasInitialized, setHasInitialized] = React.useState(false);
  React.useEffect(() => {
    if (isDataReady && !hasInitialized) {
      // Use the exact same logic as double-click reset:
      // onDomainChange([dataRanges.xMin, dataRanges.xMax], undefined)
      handleDomainChange(
        [dataRanges.xMin, dataRanges.xMax] as [number, number],
        undefined
      );
      setHasInitialized(true);
    }
  }, [isDataReady, dataRanges, hasInitialized, handleDomainChange]);

  // Check if we have processed data but it's empty (not loading, just no data)
  const hasNoData = React.useMemo(() => {
    return (
      data !== undefined &&
      xField &&
      yField &&
      (data.length === 0 || points.length === 0)
    );
  }, [data, points, xField, yField]);

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

  const chartMargins = React.useMemo(
    () => createChartMargins(isFullscreen),
    [isFullscreen]
  );

  // Current domains for coordinate conversion
  const currentDomains = React.useMemo(
    () => ({
      xDomain: (currentXDomain || [dataRanges.xMin, dataRanges.xMax]) as [
        number,
        number
      ],
      yDomain: (currentYDomain || [dataRanges.yMin, dataRanges.yMax]) as [
        number,
        number
      ],
    }),
    [currentXDomain, currentYDomain, dataRanges]
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
    if (!data || data.length === 0 || points.length === 0) {
      return {};
    }

    const domainXDomain = currentXDomain || [dataRanges.xMin, dataRanges.xMax];

    return createBinnedPointsByGroup(
      points,
      binCount,
      aggregation,
      domainXDomain,
      dataRanges,
      groupKeys,
      false, // useStackedBinning = false for line plots
      binningMode
    );
  }, [
    data,
    points,
    binCount,
    binningMode,
    aggregation,
    groupKeys,
    currentXDomain,
    dataRanges,
  ]);

  // Prepare data for react-vis
  const lineSeriesData = React.useMemo(() => {
    // Only filter by Y domain when we have an explicit currentYDomain set
    // When currentYDomain is undefined, let FlexibleXYPlot handle the domain calculation
    const shouldFilterByYDomain = currentYDomain !== undefined;
    const filterYDomain = shouldFilterByYDomain
      ? currentDomains.yDomain
      : undefined;

    if (groupKeys && groupKeys.length > 0) {
      const result = Object.entries(binnedPointsByGroup).map(
        ([group, points]) => {
          const color = groupColor(group);

          // Filter data - always filter NaN, conditionally filter by Y domain
          const filteredData = points
            .filter(
              point =>
                !isNaN(point.x) &&
                !isNaN(point.y) &&
                (filterYDomain === undefined ||
                  (point.y >= filterYDomain[0] && point.y <= filterYDomain[1]))
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

    // Filter data - always filter NaN, conditionally filter by Y domain
    const allData = (binnedPointsByGroup.all || [])
      .filter(
        point =>
          !isNaN(point.x) &&
          !isNaN(point.y) &&
          (filterYDomain === undefined ||
            (point.y >= filterYDomain[0] && point.y <= filterYDomain[1]))
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
    groupKeys,
    groupColor,
    currentYDomain,
    currentDomains.yDomain,
  ]);

  // Find intersection points for crosshair - simplified to use binned data directly
  const findIntersectionPoints = React.useCallback(
    (dataX: number): LinePlotTooltipData[] => {
      const intersections: LinePlotTooltipData[] = [];

      // Calculate which bin the mouse is over
      const domainXDomain = currentXDomain || [
        dataRanges.xMin,
        dataRanges.xMax,
      ];
      const {binStart, binEnd} = calculateBinBoundaries(
        dataX,
        points,
        binCount,
        domainXDomain
      );

      if (binStart === null || binEnd === null) return intersections;

      // Find the bin center to match against binned data
      const binCenter = (binStart + binEnd) / 2;

      // Get intersection points from each group's binned data
      Object.entries(binnedPointsByGroup).forEach(([group, binData]) => {
        // Find the bin that matches our hovered position
        const matchingBin = binData.find(point => {
          return Math.abs(point.x - binCenter) < (binEnd - binStart) * 0.1;
        });

        if (matchingBin && !isNaN(matchingBin.y)) {
          const color =
            groupKeys && groupKeys.length > 0 ? groupColor(group) : TEAL_600;

          intersections.push({
            x: matchingBin.x,
            y: matchingBin.y,
            group: group === 'all' ? 'Value' : group,
            color,
          });
        }
      });

      return intersections.sort((a, b) => b.y - a.y);
    },
    [
      binnedPointsByGroup,
      groupKeys,
      groupColor,
      points,
      binCount,
      currentXDomain,
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

        // Calculate bin boundaries for shaded area using shared utility
        const domainXDomain = currentXDomain || [
          dataRanges.xMin,
          dataRanges.xMax,
        ];

        const {binStart, binEnd} = calculateBinBoundaries(
          dataX,
          points,
          binCount,
          domainXDomain
        );

        // Convert to pixel coordinates for shaded area
        let binXStart = null;
        let binXEnd = null;

        if (binStart !== null && binEnd !== null) {
          const binStartRatio =
            (binStart - currentDomains.xDomain[0]) /
            (currentDomains.xDomain[1] - currentDomains.xDomain[0]);
          const binEndRatio =
            (binEnd - currentDomains.xDomain[0]) /
            (currentDomains.xDomain[1] - currentDomains.xDomain[0]);

          binXStart = chartMargins.left + binStartRatio * plotWidth;
          binXEnd = chartMargins.left + binEndRatio * plotWidth;
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
      points,
      binCount,
      currentXDomain,
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
    xDomain: currentDomains.xDomain,
    yDomain: currentDomains.yDomain,
    originalXDomain: [dataRanges.xMin, dataRanges.xMax] as [number, number],
    originalYDomain: undefined as any, // Let FlexibleXYPlot use its default domain calculation
    onDomainChange: handleDomainChange,
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
                height: '100%',
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
                xDomain={currentXDomain}
                yDomain={currentYDomain}
                margin={chartMargins}>
                <XAxis
                  tickFormat={unifiedXTickFormatter}
                  tickTotal={5}
                  title={xAxisLabel}
                  style={createAxisStyle(isFullscreen)}
                />
                <YAxis
                  tickFormat={unifiedYTickFormatter}
                  tickTotal={6}
                  style={createAxisStyle(isFullscreen)}
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
