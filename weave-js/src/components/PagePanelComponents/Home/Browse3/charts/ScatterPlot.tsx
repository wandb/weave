import 'react-vis/dist/style.css';

import React, {useCallback} from 'react';
import {useHistory} from 'react-router-dom';
import {FlexibleXYPlot, Hint, MarkSeries, XAxis, YAxis} from 'react-vis';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {baseContext, PEEK_PARAM} from '../context';
import {useChartData} from './chartDataProcessing';
import {useChartsDispatch, useChartsState} from './ChartsContext';
import {getScatterXAxisFields, getScatterYAxisFields} from './extractData';
import {createAxisTickFormatters} from './format';
import {formatTooltipDate, formatTooltipValue} from './format';
import {
  chartContainerStyle,
  chartContentStyle,
  createChartMargins,
  tooltipContainerStyle,
  tooltipHeaderStyle,
  tooltipRowStyle,
} from './styling';
import {ChartAxisField, ExtractedCallData} from './types';
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

  // Filter out invalid values
  if (isNaN(data.y)) return null;

  // Use display name if available, otherwise use the group (trace ID)
  // Group names are already parsed at the data processing level
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

  // Use shared chart data processing logic
  const {points, dataRanges, isDataReady, hasMultipleOperations, groupColor} =
    useChartData(
      data,
      initialXAxis,
      initialYAxis,
      xField,
      yField,
      groupBy,
      colorGroupKey,
      groupByTraceId
    );

  // Transform ProcessedChartPoint to the format expected by this component
  const transformedPoints = React.useMemo(() => {
    return points.map(point => ({
      x: point.x,
      y: point.y,
      display_name: point.display_name,
      callId: point.callId,
      traceId: point.traceId,
      group: point.group,
      color: point.color || (point.group ? groupColor(point.group) : TEAL_600),
    }));
  }, [points, groupColor]);

  // Check if we have processed data but it's empty (not loading, just no data)
  const hasNoData = React.useMemo(() => {
    return (
      data !== undefined &&
      xField &&
      yField &&
      (data.length === 0 || transformedPoints.length === 0)
    );
  }, [data, transformedPoints, xField, yField]);

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
        ? transformedPoints.filter(
            pt =>
              pt.x >= currentXDomain[0] &&
              pt.x <= currentXDomain[1] &&
              pt.y >= currentYDomain[0] &&
              pt.y <= currentYDomain[1]
          )
        : transformedPoints;

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
    transformedPoints,
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
                        group: value.originalPoint.group, // Use the actual group value, not the series group key
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
