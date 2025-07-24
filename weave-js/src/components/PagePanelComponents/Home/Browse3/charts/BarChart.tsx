/*
  BarChart.tsx

  This file contains the bar chart implementation for trace plots.
*/
import 'react-vis/dist/style.css';

import React from 'react';
import {FlexibleXYPlot, Hint, VerticalBarSeries, XAxis, YAxis} from 'react-vis';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {WaveLoader} from '../../../../../components/Loaders/WaveLoader';
import {createBinnedPointsByGroup} from './aggregation';
import {useChartData} from './chartDataProcessing';
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
  createAxisStyle,
  createChartMargins,
  tooltipContainerStyle,
  tooltipHeaderStyle,
  tooltipRowStyle,
} from './styling';
import {AggregationMethod, BinningMode, ChartAxisField, ExtractedCallData} from './types';
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
  binningMode?: BinningMode;
  aggregation?: AggregationMethod;
  groupKeys?: string[];
  chartId?: string;
  xAxisLabel?: string;
  isFullscreen?: boolean;
};

export const BarChart: React.FC<BarChartProps> = ({
  data,
  height,
  initialXAxis = 'started_at',
  initialYAxis = 'latency',
  binCount = 20,
  binningMode = 'absolute',
  aggregation = 'average',
  groupKeys,
  chartId,
  xAxisLabel,
  isFullscreen,
}) => {
  const [currentXDomain, setCurrentXDomain] = React.useState<
    [number, number] | undefined
  >();

  // Handle domain changes from zoom
  const handleDomainChange = React.useCallback(
    (xDomain: [number, number], yDomain: [number, number] | undefined) => {
      setCurrentXDomain(xDomain);
      // Y domain is automatically calculated based on visible data in adjustedDomains
    },
    []
  );

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
    groupKeys
  );

  // Calculate original Y domain for reset logic
  const originalYDomainForBarChart = React.useMemo(() => {
    if (!isDataReady || points.length === 0) {
      return [dataRanges.yMin, dataRanges.yMax] as [number, number];
    }
    const fullXDomain: [number, number] = [dataRanges.xMin, dataRanges.xMax];
    const allBinnedPointsByGroup = createBinnedPointsByGroup(
      points,
      binCount,
      aggregation,
      fullXDomain,
      dataRanges,
      groupKeys,
      true,
      binningMode
    );
    let maxY = 0;
    if (groupKeys && groupKeys.length > 0) {
      const groups = Object.keys(allBinnedPointsByGroup);
      const firstGroup = allBinnedPointsByGroup[groups[0]] || [];
      firstGroup.forEach((_, xIndex) => {
        let stackedHeight = 0;
        groups.forEach(group => {
          const point = allBinnedPointsByGroup[group][xIndex];
          const value = point && !isNaN(point.y) ? point.y : 0;
          if (value > 0) {
            stackedHeight += value;
          }
        });
        maxY = Math.max(maxY, stackedHeight);
      });
    } else {
      const allData = allBinnedPointsByGroup.all || [];
      allData.forEach(point => {
        if (!isNaN(point.y) && point.y > 0) {
          maxY = Math.max(maxY, point.y);
        }
      });
    }
    return [0, maxY * 1.1] as [number, number];
  }, [points, binCount, binningMode, aggregation, dataRanges, groupKeys, isDataReady]);

  // Initialize state to match double-click reset behavior once data is ready
  const [hasInitialized, setHasInitialized] = React.useState(false);
  React.useEffect(() => {
    if (isDataReady && !hasInitialized) {
      // Use the exact same logic as double-click reset:
      // onDomainChange([dataRanges.xMin, dataRanges.xMax], originalYDomainForBarChart)
      handleDomainChange(
        [dataRanges.xMin, dataRanges.xMax] as [number, number],
        originalYDomainForBarChart
      );
      setHasInitialized(true);
    }
  }, [
    isDataReady,
    dataRanges,
    hasInitialized,
    handleDomainChange,
    originalYDomainForBarChart,
  ]);

  // Check if we have processed data but it's empty (not loading, just no data)
  const hasNoData = React.useMemo(() => {
    return (
      data !== undefined &&
      xField &&
      yField &&
      (data.length === 0 || points.length === 0)
    );
  }, [data, points, xField, yField]);

  // State for tooltips
  const [hintValue, setHintValue] = React.useState<any>(null);

  const binnedPointsByGroup = React.useMemo(() => {
    if (!data || data.length === 0 || points.length === 0) {
      return {};
    }

    // Use current zoom domain for rebinning to maintain the configured bin count within visible range
    const domainXDomain = currentXDomain || [dataRanges.xMin, dataRanges.xMax];

    return createBinnedPointsByGroup(
      points,
      binCount,
      aggregation,
      domainXDomain,
      dataRanges,
      groupKeys,
      true,
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

  // Prepare stacked bar data for react-vis
  const stackedBarData = React.useMemo(() => {
    if (!groupKeys || groupKeys.length === 0) {
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
  }, [binnedPointsByGroup, groupKeys, groupColor]);

  const adjustedDomains = React.useMemo(() => {
    const domainXDomain = currentXDomain || [dataRanges.xMin, dataRanges.xMax];

    // Use consistent Y domain calculation:
    // - When not zoomed (initial): use originalYDomainForBarChart (matches reset)
    // - When zoomed: calculate from visible data
    const currentYDomain = currentXDomain
      ? // When zoomed, calculate Y domain from visible data
        (() => {
          let maxY = 0;
          stackedBarData.forEach(series => {
            series.data.forEach(point => {
              maxY = Math.max(maxY, point.y);
            });
          });
          return [0, maxY * 1.1] as [number, number];
        })()
      : // When not zoomed, use the same calculation as reset
        originalYDomainForBarChart;

    return {
      xDomain: domainXDomain,
      yDomain: currentYDomain,
    };
  }, [currentXDomain, dataRanges, stackedBarData, originalYDomainForBarChart]);

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
    xDomain: adjustedDomains.xDomain,
    yDomain: adjustedDomains.yDomain,
    originalXDomain: [dataRanges.xMin, dataRanges.xMax] as [number, number],
    originalYDomain: originalYDomainForBarChart,
    onDomainChange: handleDomainChange,
    isFullscreen,
    xAxisZoomOnly: true,
  });

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
              xDomain={currentXDomain}
              yDomain={adjustedDomains.yDomain}
              margin={chartMargins}
              onMouseLeave={() => setHintValue(null)}>
              <XAxis
                tickFormat={xTickFormatter}
                tickTotal={5}
                title={xAxisLabel}
                style={createAxisStyle(isFullscreen)}
              />
              <YAxis
                tickFormat={yTickFormatter}
                tickTotal={6}
                style={createAxisStyle(isFullscreen)}
              />
              {stackedBarData.map((series, index) => (
                <VerticalBarSeries
                  key={series.group}
                  data={series.data}
                  colorType="literal"
                  {...({barWidth: 0.95} as any)}
                  onValueMouseOver={(value: any) => {
                    // Use pre-calculated bin boundaries from the originalPoint
                    const binStart = value.originalPoint?.binStart;
                    const binEnd = value.originalPoint?.binEnd;

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
