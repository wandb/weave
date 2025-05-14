import 'react-vis/dist/style.css';

import React from 'react';
import {FlexibleXYPlot, Hint, VerticalBarSeries, XAxis, YAxis} from 'react-vis';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {WaveLoader} from '../../../../../components/Loaders/WaveLoader';
import {useChartsDispatch, useChartsState} from './ChartsContext';
import {
  aggregateValues,
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
}> = ({data, xField, yField, isFullscreen}) => {
  if (!data) return null;

  if (data.y === 0 || isNaN(data.y)) return null;

  const barValue = data.y - data.y0;

  return (
    <div style={tooltipContainerStyle(isFullscreen)}>
      {xField?.type === 'date' ? (
        <div style={tooltipHeaderStyle(isFullscreen)}>
          {formatTooltipDate(data.x)}
        </div>
      ) : (
        <div style={tooltipHeaderStyle(isFullscreen)}>
          {formatTooltipValue(data.x, xField?.units)}
        </div>
      )}
      <div style={tooltipRowStyle(isFullscreen)}>
        <span style={{color: data.color, fontWeight: 'bold'}}>
          {data.group}
        </span>
        <span>{formatTooltipValue(barValue, yField?.units)}</span>
      </div>
    </div>
  );
};

export type BarChartProps = {
  data: ExtractedCallData[];
  height?: number;
  width?: number;
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

  // State for tooltips
  const [hintValue, setHintValue] = React.useState<any>(null);

  const binnedPointsByGroup = React.useMemo(() => {
    if (!data || data.length === 0 || points.length === 0) {
      return {};
    }

    // Get current domain for binning
    const currentXDomain = chartConfig?.xDomain || [
      dataRanges.xMin,
      dataRanges.xMax,
    ];

    // Filter by X domain when binning data
    const filteredPoints = points.filter(
      pt => pt.x >= currentXDomain[0] && pt.x <= currentXDomain[1]
    );

    if (filteredPoints.length === 0) {
      return {};
    }

    // For stacked bars, we need shared x-axis bins across all groups
    if ((groupBy || colorGroupKey) && filteredPoints.some(pt => pt.group)) {
      // Calculate shared x-axis range from all filtered points
      const xVals = filteredPoints.map(pt => pt.x);
      const xMin = Math.min(...xVals);
      const xMax = Math.max(...xVals);

      if (xMax === xMin) {
        // All points have same x value, group them without binning
        const grouped: Record<string, any[]> = {};
        filteredPoints.forEach(pt => {
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
      filteredPoints.forEach(pt => {
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
        new Set(filteredPoints.map(pt => pt.group || 'Other'))
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
    return binDataPoints(filteredPoints, binCount, aggregation, false);
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

  // Prepare stacked bar data for react-vis
  const stackedBarData = React.useMemo(() => {
    if (
      (!groupBy && !colorGroupKey) ||
      Object.keys(binnedPointsByGroup).length <= 1
    ) {
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

  // Calculate optimal number of ticks using unified utility
  const optimalTickCount = React.useMemo(() => {
    // Use reasonable defaults for FlexibleXYPlot since we don't track dimensions
    const defaultDimensions = {width: 800, height: 400};
    return calculateOptimalTickCount(
      defaultDimensions,
      chartMargins,
      xField,
      adjustedDomains.xDomain
    );
  }, [chartMargins, xField, adjustedDomains.xDomain]);

  // Calculate optimal number of Y-axis ticks
  const optimalYTickCount = React.useMemo(() => {
    // Use reasonable defaults for FlexibleXYPlot since we don't track dimensions
    const defaultDimensions = {width: 800, height: 400};
    return calculateOptimalTickCount(
      defaultDimensions,
      chartMargins,
      yField,
      adjustedDomains.yDomain,
      'y'
    );
  }, [chartMargins, yField, adjustedDomains.yDomain]);

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
  React.useEffect(() => {
    if (chartId && globalDispatch && chartConfig && data && data.length > 0) {
      const hasVisibleData = stackedBarData.some(
        series => series.data.length > 0
      );
      if (!hasVisibleData) {
        globalDispatch({
          type: 'RESET_CHART_DOMAIN',
          id: chartId,
        });
      }
    }
  }, [chartId, globalDispatch, chartConfig, stackedBarData, data]);

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
                tickTotal={optimalTickCount}
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
                tickTotal={optimalYTickCount}
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
                  barWidth={0.8}
                  onValueMouseOver={(value: any) => {
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
