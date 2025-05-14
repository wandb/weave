import React from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  TooltipProps,
  XAxis,
  YAxis,
} from 'recharts';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {useChartsState} from './ChartsContext';
import {
  AggregationMethod,
  binDataPoints,
  BinnedPoint,
  chartContainerStyle,
  chartContentStyle,
  COLOR_PALETTE,
  DataPoint,
  formatAxisTick,
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
  getOpNameDisplay,
  xAxisFields,
  yAxisFields,
} from './extractData';

export type LinePlotProps = {
  data: ExtractedCallData[];
  height?: number;
  initialXAxis?: string;
  initialYAxis?: string;
  binCount?: number;
  aggregation?: AggregationMethod;
  groupKey?: string;
  hoveredGroup?: string | null;
};

const useChartLines = (
  binnedPointsByGroup: Record<string, BinnedPoint[]>,
  groupBy: string | undefined,
  groupColor: (group: string) => string,
  hoveredGroup: string | null
) => {
  return React.useMemo(() => {
    if (groupBy && Object.keys(binnedPointsByGroup).length > 1) {
      return Object.entries(binnedPointsByGroup).map(([group, points]) => {
        const color = groupColor(group);
        const isHighlighted = hoveredGroup === group;
        const isDimmed = hoveredGroup !== null && !isHighlighted;

        const lineData = points.map(point => ({
          x: point.x,
          y: point.y,
          // Store the original value for tooltip
          originalValue: point.originalValue,
          // Add group-specific value for tooltip
          [group]: point.originalValue,
        }));

        return (
          <Line
            key={group}
            data={lineData}
            dataKey="y"
            name={group}
            stroke={color}
            dot={false}
            strokeWidth={isDimmed ? 1 : 2}
            opacity={isDimmed ? 0.2 : 1}
            connectNulls={true}
          />
        );
      });
    }

    return [
      <Line
        key="all"
        data={binnedPointsByGroup.all || []}
        dataKey="y"
        name="Value"
        stroke={TEAL_600}
        dot={false}
      />,
    ];
  }, [binnedPointsByGroup, groupBy, groupColor, hoveredGroup]);
};

type LinePlotTooltipProps = TooltipProps<number, string> & {
  originalData: DataPoint[];
  xField?: ChartAxisField;
  yField?: ChartAxisField;
};

const LinePlotTooltip: React.FC<LinePlotTooltipProps> = ({
  active,
  payload,
  label,
  originalData,
  xField,
  yField,
}) => {
  if (!active || !payload?.length) return null;

  // For each group in the payload, find the closest original data point to the hovered x (label)
  const groupNames = payload
    .map(entry => entry.name)
    .filter((g): g is string => !!g);
  const closestByGroup: Record<string, DataPoint | undefined> = {};
  groupNames.forEach(group => {
    const groupData = originalData.filter(
      d => (d.group || 'Value') === group || (!d.group && group === 'Value')
    );
    if (groupData.length > 0 && typeof label === 'number') {
      // Find points within 16 pixels of the cursor
      // We'll use a simple approximation: 16 pixels is roughly 1% of the chart width
      const xRange =
        Math.max(...groupData.map(d => d.x)) -
        Math.min(...groupData.map(d => d.x));
      const pixelThreshold = xRange * 0.01; // 1% of the range

      const nearbyPoints = groupData.filter(
        d => Math.abs(d.x - label) <= pixelThreshold
      );
      if (nearbyPoints.length > 0) {
        closestByGroup[group] = nearbyPoints.reduce((prev, curr) =>
          Math.abs(curr.x - label) < Math.abs(prev.x - label) ? curr : prev
        );
      }
    }
  });

  // Only show groups that have a closest point
  let validGroups = groupNames.filter(
    group => group && closestByGroup[group] && !isNaN(closestByGroup[group]!.y)
  );

  // Filter out groups with a y value of 0
  validGroups = validGroups.filter(
    group => (closestByGroup[group]?.y ?? 0) !== 0
  );

  // Sort validGroups by their y value (numerical value) in descending order
  validGroups = validGroups.sort((a, b) => {
    const aVal = closestByGroup[a]?.y ?? 0;
    const bVal = closestByGroup[b]?.y ?? 0;
    return bVal - aVal;
  });

  if (validGroups.length === 0) return null;

  return (
    <div style={tooltipContainerStyle}>
      <div style={tooltipHeaderStyle}>
        {xField?.type === 'date'
          ? formatTooltipDate(label)
          : formatTooltipValue(label, xField?.units)}
      </div>
      {validGroups.map((group, index) => {
        const entry = payload.find(e => e.name === group);
        const color = entry?.color;
        const closest = closestByGroup[group]!;
        return (
          <div key={index} style={tooltipRowStyle}>
            <span style={{color}}>{group}</span>
            <span>{formatTooltipValue(closest.y, yField?.units)}</span>
          </div>
        );
      })}
    </div>
  );
};

const getDateTickFormatter = (domain: [number, number]) => {
  const range = domain[1] - domain[0];
  const oneDay = 24 * 60 * 60 * 1000;
  const oneHour = 60 * 60 * 1000;
  const oneMinute = 60 * 1000;

  if (range <= oneMinute) {
    // Show milliseconds for very small ranges
    return (value: number) =>
      new Date(value).toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        fractionalSecondDigits: 3,
      });
  } else if (range <= oneHour) {
    // Show seconds for ranges up to an hour
    return (value: number) =>
      new Date(value).toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
  } else if (range <= oneDay) {
    // Show hours for ranges up to a day
    return (value: number) =>
      new Date(value).toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
      });
  } else if (range <= 7 * oneDay) {
    // Show date and time for ranges up to a week
    return (value: number) =>
      new Date(value).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
  } else if (range <= 30 * oneDay) {
    // Show date for ranges up to a month
    return (value: number) =>
      new Date(value).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
      });
  } else {
    // Show month and year for longer ranges
    return (value: number) =>
      new Date(value).toLocaleString('en-US', {
        month: 'short',
        year: 'numeric',
      });
  }
};

export const LinePlot: React.FC<LinePlotProps> = ({
  data,
  height,
  initialXAxis = 'started_at',
  initialYAxis = 'latency',
  binCount = 20,
  aggregation = 'average',
  groupKey,
  hoveredGroup: externalHoveredGroup,
}) => {
  // Use either provided hover state or global state
  const globalState = useChartsState();
  const hoveredGroup =
    externalHoveredGroup !== undefined
      ? externalHoveredGroup
      : globalState.hoveredGroup;

  const xField = xAxisFields.find(f => f.key === initialXAxis);
  const yField = yAxisFields.find(f => f.key === initialYAxis);

  // Grouping logic
  const groupBy = groupKey === 'op_name' ? 'op_name' : undefined;
  const groupValues = getGroupValues(data, groupBy);

  const groupColor = (group: string) => {
    const idx = groupValues.indexOf(group);
    return COLOR_PALETTE[idx % COLOR_PALETTE.length];
  };

  // Convert raw data to data points
  const points = React.useMemo(
    () =>
      data
        .map(d => ({
          x:
            xField?.type === 'date'
              ? new Date(
                  d[initialXAxis as keyof ExtractedCallData] as any
                ).getTime()
              : d[initialXAxis as keyof ExtractedCallData],
          y:
            yField?.type === 'date'
              ? new Date(
                  d[initialYAxis as keyof ExtractedCallData] as any
                ).getTime()
              : d[initialYAxis as keyof ExtractedCallData],
          display_name: d.display_name || '',
          group: groupBy
            ? getOpNameDisplay(d[groupBy as keyof ExtractedCallData] as string)
            : undefined,
        }))
        .filter(
          pt =>
            pt.x !== undefined &&
            pt.y !== undefined &&
            typeof pt.x === 'number' &&
            typeof pt.y === 'number' &&
            !isNaN(pt.x) &&
            !isNaN(pt.y)
        ) as DataPoint[],
    [data, initialXAxis, initialYAxis, xField, yField, groupBy]
  );

  // Calculate initial domain from data
  const initialDomain = React.useMemo(() => {
    if (points.length === 0) return [0, 0];
    const xValues = points.map(p => p.x);
    const min = Math.min(...xValues);
    const max = Math.max(...xValues);
    // Add a small padding to the domain
    const padding = (max - min) * 0.05;
    return [min - padding, max + padding];
  }, [points]);

  // State for zooming
  const [xDomain, setXDomain] = React.useState(initialDomain);
  const [refAreaLeft, setRefAreaLeft] = React.useState<number | null>(null);
  const [refAreaRight, setRefAreaRight] = React.useState<number | null>(null);

  // Handle mouse events for zooming
  const handleMouseDown = React.useCallback((e: any) => {
    if (e?.activeLabel) {
      const value = Number(e.activeLabel);
      if (!isNaN(value)) {
        setRefAreaLeft(value);
      }
    }
  }, []);

  const handleMouseMove = React.useCallback(
    (e: any) => {
      if (refAreaLeft && e?.activeLabel) {
        const value = Number(e.activeLabel);
        if (!isNaN(value)) {
          setRefAreaRight(value);
        }
      }
    },
    [refAreaLeft]
  );

  const handleMouseUp = React.useCallback(
    (e: any) => {
      if (refAreaLeft && refAreaRight) {
        const left = Math.min(refAreaLeft, refAreaRight);
        const right = Math.max(refAreaLeft, refAreaRight);
        // Add a small padding to the zoomed domain
        const padding = (right - left) * 0.05;
        setXDomain([left - padding, right + padding]);
      }
      setRefAreaLeft(null);
      setRefAreaRight(null);
    },
    [refAreaLeft, refAreaRight]
  );

  const handleDoubleClick = React.useCallback(
    (e: any) => {
      setXDomain(initialDomain);
      setRefAreaLeft(null);
      setRefAreaRight(null);
    },
    [initialDomain]
  );

  // Use the shared binning utility
  const binnedPointsByGroup = React.useMemo(
    () => binDataPoints(points, binCount, aggregation, !!groupBy),
    [points, binCount, aggregation, groupBy]
  );

  // Use shared formatters from chartUtils
  const xTickFormatter = React.useCallback(
    (value: any) => {
      if (xField?.type === 'date' && xDomain.length === 2) {
        const formatter = getDateTickFormatter([xDomain[0], xDomain[1]]);
        return formatter(value);
      }
      return formatAxisTick(value, xField);
    },
    [xField, xDomain]
  );

  const yTickFormatter = React.useCallback(
    (value: any) => formatAxisTick(value, yField),
    [yField]
  );

  // Generate the line components using our memoized helper
  const lineComponents = useChartLines(
    binnedPointsByGroup,
    groupBy,
    groupColor,
    hoveredGroup
  );

  // Custom tick component to ensure unique keys
  const CustomTick = React.useCallback(
    (props: any) => {
      const {x, y, payload} = props;
      return (
        <g transform={`translate(${x},${y})`}>
          <text
            x={0}
            y={0}
            dy={16}
            textAnchor="middle"
            fill="#666"
            fontSize={10}
            fontFamily="Source Sans Pro">
            {xTickFormatter(payload.value)}
          </text>
        </g>
      );
    },
    [xTickFormatter]
  );

  return (
    <div style={chartContainerStyle}>
      {Object.keys(binnedPointsByGroup).length === 0 ? (
        <span style={{color: '#8F8F8F'}}>No data to display</span>
      ) : (
        <div style={chartContentStyle}>
          {xField && yField && (
            <div
              className="line-plot-container"
              style={{
                width: '100%',
                height: height || '100%',
                position: 'relative',
                isolation: 'isolate',
                zIndex: 1,
                display: 'flex',
                flex: '1 1 auto',
              }}>
              <ResponsiveContainer
                width="100%"
                height={height || '100%'}
                minHeight={0}
                aspect={undefined}>
                <LineChart
                  margin={{
                    top: 2,
                    right: 30,
                    left: 2,
                    bottom: 2,
                  }}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onDoubleClick={handleDoubleClick}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="x"
                    name={xField.label || initialXAxis}
                    type="number"
                    scale="linear"
                    domain={xDomain}
                    allowDataOverflow={true}
                    tickFormatter={xTickFormatter}
                    padding={{left: 0, right: 0}}
                    axisLine={{strokeWidth: 1}}
                    tick={<CustomTick />}
                    tickSize={3}
                  />
                  <YAxis
                    dataKey="y"
                    name={yField.label || initialYAxis}
                    type="number"
                    scale="linear"
                    tick={{fontSize: 10, fontFamily: 'Source Sans Pro'}}
                    tickSize={3}
                    domain={['auto', 'auto']}
                    tickFormatter={yTickFormatter}
                    padding={{top: 0, bottom: 0}}
                    axisLine={{strokeWidth: 1}}
                  />
                  <Tooltip
                    cursor={{stroke: '#999', strokeDasharray: '5 5'}}
                    content={
                      <LinePlotTooltip
                        originalData={points}
                        xField={xField}
                        yField={yField}
                      />
                    }
                    isAnimationActive={false}
                  />
                  {lineComponents}
                  {refAreaLeft && refAreaRight && (
                    <ReferenceArea
                      x1={refAreaLeft}
                      x2={refAreaRight}
                      strokeOpacity={0.3}
                      fill="#8884d8"
                      fillOpacity={0.1}
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
