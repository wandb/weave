import 'react-vis/dist/style.css';

import React, {useCallback} from 'react';
import {useHistory} from 'react-router-dom';
import {FlexibleXYPlot, Hint, MarkSeries, XAxis, YAxis} from 'react-vis';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {baseContext, PEEK_PARAM} from '../context';
import {useChartsDispatch, useChartsState} from './ChartsContext';
import {
  chartContainerStyle,
  chartContentStyle,
  COLOR_PALETTE,
  createAxisTickFormatters,
  createChartMargins,
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
  getDisplayValue,
  getInputOutputFieldValue,
  getOpNameDisplay,
  getScatterXAxisFields,
  getScatterYAxisFields,
} from './extractData';
import {useChartZoom} from './useChartZoom';

type ScatterPlotTooltipData = {
  x: number;
  y: number;
  group: string;
  color: string;
};

const ScatterPlotTooltip: React.FC<{
  data: ScatterPlotTooltipData;
  xField?: ChartAxisField;
  yField?: ChartAxisField;
  isFullscreen?: boolean;
  traceIdToDisplayName?: Map<string, string>;
}> = ({data, xField, yField, isFullscreen, traceIdToDisplayName}) => {
  if (!data) return null;

  // Filter out zero values
  if (data.y === 0 || isNaN(data.y)) return null;

  // Use display name if available, otherwise use the group (trace ID)
  const displayName = traceIdToDisplayName?.get(data.group) || data.group;

  // Check if this is a time-based x-axis
  const isTimeBasedX =
    xField?.type === 'date' ||
    xField?.key === 'started_at' ||
    xField?.key === 'ended_at';

  if (isTimeBasedX) {
    // Original time-based layout
    return (
      <div style={tooltipContainerStyle(isFullscreen)}>
        <div style={tooltipHeaderStyle(isFullscreen)}>
          {formatTooltipDate(data.x)}
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
            }}>
            {displayName}
          </span>
          <span
            style={{
              flex: '0 0 auto',
              textAlign: 'right',
              minWidth: isFullscreen ? '60px' : '50px',
              color: data.color,
              fontWeight: 'bold',
            }}>
            {formatTooltipValue(data.y, yField?.units)}
          </span>
        </div>
      </div>
    );
  }

  // New non-time layout: group, x-axis, y-axis
  return (
    <div style={tooltipContainerStyle(isFullscreen)}>
      <div
        style={{
          ...tooltipRowStyle(isFullscreen),
          fontFamily: 'inconsolata',
          fontWeight: 600,
          color: data.color,
          marginBottom: isFullscreen ? '8px' : '6px',
        }}>
        {displayName}
      </div>
      <div
        style={{
          ...tooltipRowStyle(isFullscreen),
          fontFamily: 'inconsolata',
          marginBottom: isFullscreen ? '4px' : '2px',
        }}>
        <span style={{fontWeight: 600}}>{xField?.label || 'X'}:</span>
        <span style={{marginLeft: '4px', fontWeight: 'bold'}}>
          {formatTooltipValue(data.x, xField?.units)}
        </span>
      </div>
      <div
        style={{
          ...tooltipRowStyle(isFullscreen),
          fontFamily: 'inconsolata',
        }}>
        <span style={{fontWeight: 600}}>{yField?.label || 'Y'}:</span>
        <span style={{marginLeft: '4px', fontWeight: 'bold'}}>
          {formatTooltipValue(data.y, yField?.units)}
        </span>
      </div>
    </div>
  );
};

export type ScatterPlotProps = {
  data: ExtractedCallData[];
  height?: number;
  width?: number;
  initialXAxis?: string;
  initialYAxis?: string;
  groupKey?: string;
  colorGroupKey?: string;
  hoveredGroup?: string | null;
  chartId?: string;
  entity?: string;
  project?: string;
  xAxisLabel?: string;
  isFullscreen?: boolean;
  traceIdToDisplayName?: Map<string, string>;
  groupByTraceId?: boolean;
};

export const ScatterPlot: React.FC<ScatterPlotProps> = ({
  data,
  height,
  width,
  initialXAxis = 'started_at',
  initialYAxis = 'latency',
  groupKey,
  colorGroupKey,
  hoveredGroup: externalHoveredGroup,
  chartId,
  entity,
  project,
  xAxisLabel,
  isFullscreen,
  traceIdToDisplayName,
  groupByTraceId,
}) => {
  const globalState = useChartsState();
  const dispatch = useChartsDispatch();
  const history = useHistory();
  const hoveredGroup =
    externalHoveredGroup !== undefined
      ? externalHoveredGroup
      : globalState.hoveredGroup;

  // Get chart config for domain refinement
  const chartConfig = chartId
    ? globalState.charts.find(c => c.id === chartId)
    : undefined;

  const xField = getScatterXAxisFields(data).find(f => f.key === initialXAxis);
  const yField = getScatterYAxisFields(data).find(f => f.key === initialYAxis);

  const groupBy =
    groupKey === 'op_name'
      ? 'op_name'
      : groupKey === 'traceId'
      ? 'traceId'
      : undefined;

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
        colorGroupValue = getDisplayValue(value) || 'Unknown';
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

  const groupColor = useCallback(
    (group: string) => groupColorMap[group] || '#000',
    [groupColorMap]
  );

  const points = React.useMemo(() => {
    if (!data || data.length === 0) {
      return [];
    }

    // Special handling for evaluations when x-axis is start time
    if (groupByTraceId && initialXAxis === 'started_at') {
      // Group data by traceId
      const groupedByTrace = new Map<string, ExtractedCallData[]>();

      data.forEach(d => {
        if (!groupedByTrace.has(d.traceId)) {
          groupedByTrace.set(d.traceId, []);
        }
        groupedByTrace.get(d.traceId)!.push(d);
      });

      const result: Array<{
        x: number;
        y: number;
        display_name: string;
        callId: string;
        traceId: string;
        group: string | undefined;
        color: string;
      }> = [];

      // Process each trace group
      groupedByTrace.forEach(traceData => {
        // Sort by start time within each trace
        const sortedTraceData = [...traceData].sort(
          (a, b) =>
            new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
        );

        // Assign index-based x coordinates
        sortedTraceData.forEach((d, index) => {
          const opNameGroup = getOpNameDisplay(d.op_name);

          // Determine the flexible group name based on groupBy
          let groupName: string | undefined;
          if (groupBy === 'op_name') {
            groupName = opNameGroup;
          } else if (groupBy === 'traceId') {
            groupName = d.traceId;
          }

          // Determine the color group for this data point
          let colorGroup = '';
          if (colorGroupKey) {
            if (
              colorGroupKey.startsWith('input.') ||
              colorGroupKey.startsWith('output.')
            ) {
              const value = getInputOutputFieldValue(d, colorGroupKey);
              colorGroup = getDisplayValue(value) || 'Unknown';
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
          } else if (groupBy && groupName) {
            // Use the flexible group name instead of hardcoded op_name
            colorGroup = groupName;
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

          const point = {
            x: index, // Use index instead of timestamp
            y:
              yField?.type === 'date'
                ? new Date(yValue as any).getTime()
                : yValue,
            display_name: d.display_name || '',
            callId: d.callId,
            traceId: d.traceId,
            group: colorGroup || 'All',
            color: colorGroup ? groupColor(colorGroup) : TEAL_600,
          };

          // Only include valid points
          if (
            point.y !== undefined &&
            typeof point.y === 'number' &&
            !isNaN(point.y)
          ) {
            result.push(point);
          }
        });
      });

      return result;
    }

    // Standard processing for non-evaluation cases
    return data
      .map(d => {
        const opNameGroup = getOpNameDisplay(d.op_name);

        // Determine the flexible group name based on groupBy
        let groupName: string | undefined;
        if (groupBy === 'op_name') {
          groupName = opNameGroup;
        } else if (groupBy === 'traceId') {
          groupName = d.traceId;
        }

        // Determine the color group for this data point
        let colorGroup = '';
        if (colorGroupKey) {
          if (
            colorGroupKey.startsWith('input.') ||
            colorGroupKey.startsWith('output.')
          ) {
            const value = getInputOutputFieldValue(d, colorGroupKey);
            colorGroup = getDisplayValue(value) || 'Unknown';
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
        } else if (groupBy && groupName) {
          // Use the flexible group name instead of hardcoded op_name
          colorGroup = groupName;
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
          callId: d.callId,
          traceId: d.traceId,
          group: colorGroup || 'All',
          color: colorGroup ? groupColor(colorGroup) : TEAL_600,
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
      ) as Array<{
      x: number;
      y: number;
      display_name: string;
      callId: string;
      traceId: string;
      group: string | undefined;
      color: string;
    }>;
  }, [
    data,
    initialXAxis,
    initialYAxis,
    xField,
    yField,
    groupBy,
    hasMultipleOperations,
    colorGroupKey,
    groupColor,
    groupByTraceId,
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

  // Check if we have processed data but it's empty (not loading, just no data)
  const hasNoData = React.useMemo(() => {
    return (
      data !== undefined &&
      xField &&
      yField &&
      (data.length === 0 || points.length === 0)
    );
  }, [data, points, xField, yField]);

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
  const {xTickFormatter, yTickFormatter} = React.useMemo(
    () =>
      createAxisTickFormatters(
        xField,
        yField,
        currentDomains.xDomain,
        currentDomains.yDomain
      ),
    [xField, yField, currentDomains.xDomain, currentDomains.yDomain]
  );

  // State for tooltips
  const [hintValue, setHintValue] = React.useState<any>(null);
  const [isHoveringPoint, setIsHoveringPoint] = React.useState(false);

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
  });

  // Handle click on scatter plot point
  const handlePointClick = useCallback(
    (value: any, event: React.MouseEvent) => {
      const callId = value.originalPoint?.callId;
      const traceId = value.originalPoint?.traceId;

      if (!callId || !traceId || !entity || !project) {
        console.warn('Missing required data for navigation:', {
          callId,
          traceId,
          entity,
          project,
        });
        return;
      }

      // Construct the peek URL for the call
      const callPeekComponent = baseContext.callUIUrl(
        entity,
        project,
        traceId,
        callId,
        undefined
      );

      // Get current URL and add peek parameter
      const currentLocation = history.location;
      const searchParams = new URLSearchParams(currentLocation.search);
      searchParams.set(PEEK_PARAM, callPeekComponent);

      // Navigate to the current page with the peek parameter
      history.push({
        pathname: currentLocation.pathname,
        search: searchParams.toString(),
      });
    },
    [entity, project, history]
  );

  // Prepare data for react-vis
  const scatterSeriesData = React.useMemo(() => {
    // Get current domain for filtering
    const currentXDomain = chartConfig?.xDomain || [
      dataRanges.xMin,
      dataRanges.xMax,
    ];
    const currentYDomain = chartConfig?.yDomain || [
      dataRanges.yMin,
      dataRanges.yMax,
    ];

    // Only filter points if there's actually a zoom state (domains are set in chartConfig)
    // Otherwise, use all points to avoid filtering out boundary values
    const filteredPoints =
      chartConfig?.xDomain || chartConfig?.yDomain
        ? points.filter(
            pt =>
              pt.x >= currentXDomain[0] &&
              pt.x <= currentXDomain[1] &&
              pt.y >= currentYDomain[0] &&
              pt.y <= currentYDomain[1]
          )
        : points;

    if (!hasMultipleOperations && !colorGroupKey && !groupBy) {
      return [
        {
          group: 'All points',
          color: TEAL_600,
          data: filteredPoints
            .filter(pt => !isNaN(pt.x) && !isNaN(pt.y))
            .map(pt => ({
              x: pt.x,
              y: pt.y,
              size: 2,
              originalPoint: pt,
            })),
        },
      ];
    }

    const grouped: Record<string, typeof filteredPoints> = {};
    filteredPoints.forEach(pt => {
      const group = pt.group || 'Other';
      if (!grouped[group]) grouped[group] = [];
      grouped[group].push(pt);
    });

    return Object.entries(grouped).map(([group, pts]) => {
      const color = groupColor(group);
      const isHighlighted = hoveredGroup === group;
      const isDimmed = hoveredGroup !== null && !isHighlighted;

      return {
        group,
        color,
        data: pts
          .filter(pt => !isNaN(pt.x) && !isNaN(pt.y))
          .map(pt => ({
            x: pt.x,
            y: pt.y,
            size: isHighlighted ? 4 : isDimmed ? 1 : 2,
            opacity: isDimmed ? 0.04 : 1,
            originalPoint: pt,
          })),
      };
    });
  }, [
    points,
    hasMultipleOperations,
    groupBy,
    groupColor,
    hoveredGroup,
    chartConfig?.xDomain,
    chartConfig?.yDomain,
    dataRanges,
    colorGroupKey,
  ]);

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
      dispatch &&
      chartConfig &&
      data &&
      data.length > 0 &&
      !hasResetRef.current &&
      (chartConfig.xDomain || chartConfig.yDomain) // Only reset if there's actually a zoom state
    ) {
      // Check if filtering resulted in no visible data
      const hasVisibleData = scatterSeriesData.some(
        series => series.data.length > 0
      );
      if (!hasVisibleData) {
        hasResetRef.current = true; // Prevent multiple dispatches
        // Only auto-reset if we have original data but no visible data (meaning the zoom filtered out everything)
        dispatch({
          type: 'RESET_CHART_DOMAIN',
          id: chartId,
        });
      }
    }
  }, [chartId, dispatch, data, scatterSeriesData, chartConfig]);

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
      ) : scatterSeriesData.every(series => series.data.length === 0) ? (
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
              cursor: isHoveringPoint ? 'pointer' : 'crosshair',
              userSelect: 'none',
              WebkitUserSelect: 'none',
              MozUserSelect: 'none',
              msUserSelect: 'none',
            }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleZoomMouseMove}
            onMouseUp={handleMouseUp}
            onDoubleClick={handleZoomDoubleClick}>
            <FlexibleXYPlot
              margin={chartMargins}
              xDomain={chartConfig?.xDomain}
              yDomain={chartConfig?.yDomain}
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
                style={{
                  text: {
                    fontSize: isFullscreen ? '14px' : '10px',
                    fontFamily: 'Source Sans Pro',
                  },
                }}
              />
              {scatterSeriesData.map((series, index) => (
                <MarkSeries
                  key={series.group}
                  data={series.data}
                  color={series.color}
                  onValueMouseOver={(value: any) => {
                    setHintValue({
                      x: value.x,
                      y: value.y,
                      tooltipData: {
                        x: value.originalPoint.x,
                        y: value.originalPoint.y,
                        group: series.group,
                        color: series.color,
                      },
                    });
                    setIsHoveringPoint(true);
                  }}
                  onValueClick={handlePointClick}
                  size={4}
                  // Typescript thinks the size prop is not valid, but it is, hence the any
                  {...({} as any)}
                  onValueMouseOut={() => {
                    setHintValue(null);
                    setIsHoveringPoint(false);
                  }}
                />
              ))}
              {hintValue && (
                <Hint value={hintValue}>
                  <ScatterPlotTooltip
                    data={hintValue.tooltipData}
                    xField={xField}
                    yField={yField}
                    isFullscreen={isFullscreen}
                    traceIdToDisplayName={traceIdToDisplayName}
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
