/*
  ScatterPlot.tsx

  This file contains the scatter plot implementation for trace plots.
*/
import 'react-vis/dist/style.css';

import React, {useCallback} from 'react';
import {useHistory} from 'react-router-dom';
import {FlexibleXYPlot, Hint, MarkSeries, XAxis, YAxis} from 'react-vis';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {WaveLoader} from '../../../../Loaders/WaveLoader';
import {baseContext, PEEK_PARAM} from '../context';
import {useChartData} from './chartDataProcessing';
import {getScatterXAxisFields, getScatterYAxisFields} from './extractData';
import {createAxisTickFormatters} from './format';
import {formatTooltipDate, formatTooltipValue} from './format';
import {
  chartContainerStyle,
  chartContentStyle,
  createAxisStyle,
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
}> = ({data, xField, yField, isFullscreen}) => {
  if (!data) return null;
  if (isNaN(data.y)) return null;
  const displayName = data.group;
  const isTimeBasedX =
    xField?.type === 'date' ||
    xField?.key === 'started_at' ||
    xField?.key === 'ended_at';

  if (isTimeBasedX) {
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
              fontWeight: 'bold',
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

  return (
    <div style={tooltipContainerStyle(isFullscreen)}>
      <div
        style={{
          ...tooltipRowStyle(isFullscreen),
          fontFamily: 'inconsolata',
          fontWeight: 'bold',
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
        <span style={{fontWeight: 'bold'}}>{xField?.label || 'X'}:</span>
        <span style={{marginLeft: '4px', fontWeight: 'bold'}}>
          {formatTooltipValue(data.x, xField?.units)}
        </span>
      </div>
      <div
        style={{
          ...tooltipRowStyle(isFullscreen),
          fontFamily: 'inconsolata',
        }}>
        <span style={{fontWeight: 'bold'}}>{yField?.label || 'Y'}:</span>
        <span style={{marginLeft: '4px', fontWeight: 'bold'}}>
          {formatTooltipValue(data.y, yField?.units)}
        </span>
      </div>
    </div>
  );
};

export type ScatterPlotProps = {
  data: ExtractedCallData[];
  initialXAxis?: string;
  initialYAxis?: string;
  groupKeys?: string[];
  entity?: string;
  project?: string;
  xAxisLabel?: string;
  isFullscreen?: boolean;
};

export const ScatterPlot: React.FC<ScatterPlotProps> = ({
  data,
  initialXAxis = 'started_at',
  initialYAxis = 'latency',
  groupKeys,
  entity,
  project,
  xAxisLabel,
  isFullscreen,
}) => {
  const history = useHistory();

  const [currentXDomain, setCurrentXDomain] = React.useState<
    [number, number] | undefined
  >();
  const [currentYDomain, setCurrentYDomain] = React.useState<
    [number, number] | undefined
  >();

  const xField = getScatterXAxisFields(data).find(f => f.key === initialXAxis);
  const yField = getScatterYAxisFields(data).find(f => f.key === initialYAxis);

  // Use shared chart data processing logic
  const {points, dataRanges, isDataReady, groupColor} = useChartData(
    data,
    initialXAxis,
    initialYAxis,
    xField,
    yField,
    groupKeys
  );

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

  // Handle domain changes from zoom
  const handleDomainChange = React.useCallback(
    (xDomain: [number, number], yDomain: [number, number] | undefined) => {
      setCurrentXDomain(xDomain);
      setCurrentYDomain(yDomain === undefined ? undefined : yDomain);
    },
    []
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
    xDomain: currentDomains.xDomain,
    yDomain: currentDomains.yDomain,
    originalXDomain: [dataRanges.xMin, dataRanges.xMax] as [number, number],
    originalYDomain: [dataRanges.yMin, dataRanges.yMax] as [number, number],
    onDomainChange: handleDomainChange,
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

  const scatterSeriesData = React.useMemo(() => {
    const domainXDomain = currentXDomain || [dataRanges.xMin, dataRanges.xMax];
    const domainYDomain = currentYDomain || [dataRanges.yMin, dataRanges.yMax];
    const filteredPoints =
      currentXDomain || currentYDomain
        ? points.filter(
            pt =>
              pt.x >= domainXDomain[0] &&
              pt.x <= domainXDomain[1] &&
              pt.y >= domainYDomain[0] &&
              pt.y <= domainYDomain[1]
          )
        : points;

    if (!groupKeys) {
      return [
        {
          group: '',
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

      return {
        group,
        color,
        data: pts
          .filter(pt => !isNaN(pt.x) && !isNaN(pt.y))
          .map(pt => ({
            x: pt.x,
            y: pt.y,
            size: 2,
            originalPoint: pt,
          })),
      };
    });
  }, [
    points,
    groupKeys,
    groupColor,
    currentXDomain,
    currentYDomain,
    dataRanges,
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
              xDomain={currentXDomain}
              yDomain={currentYDomain}
              onMouseLeave={() => setHintValue(null)}>
              <XAxis
                tickFormat={xTickFormatter}
                tickTotal={5}
                title={xAxisLabel}
                style={createAxisStyle(isFullscreen)}
              />
              <YAxis
                tickFormat={yTickFormatter}
                style={createAxisStyle(isFullscreen)}
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
