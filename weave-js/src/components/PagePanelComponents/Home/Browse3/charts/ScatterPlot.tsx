import React, {useCallback} from 'react';
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  TooltipProps,
  XAxis,
  YAxis,
} from 'recharts';

import {TEAL_600} from '../../../../../common/css/color.styles';
import {useChartsState} from './ChartsContext';
import {
  chartContainerStyle,
  chartContentStyle,
  COLOR_PALETTE,
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

type ScatterPlotTooltipProps = TooltipProps<number, string> & {
  xField?: ChartAxisField;
  yField?: ChartAxisField;
};

const ScatterPlotTooltip: React.FC<ScatterPlotTooltipProps> = ({
  active,
  payload,
  label,
  xField,
  yField,
}) => {
  if (!active || !payload?.length) return null;

  const point = payload[0].payload;
  if (!point) return null;

  // Filter out zero values and sort by y value
  const entries = payload
    .filter(entry => entry.value !== 0 && entry.dataKey === 'y')
    .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

  if (entries.length === 0) return null;

  return (
    <div style={tooltipContainerStyle}>
      {xField?.type === 'date' ? (
        <div style={tooltipHeaderStyle}>{formatTooltipDate(point.x)}</div>
      ) : (
        <div style={tooltipHeaderStyle}>
          {formatTooltipValue(point.x, xField?.units)}
        </div>
      )}
      {entries.map((entry, index) => (
        <div key={index} style={tooltipRowStyle}>
          <span style={{color: entry.color}}>{entry.name}</span>
          <span>{formatTooltipValue(entry.value, yField?.units)}</span>
        </div>
      ))}
    </div>
  );
};

const useScatterPoints = (
  groupedPoints: Record<string, any[]>,
  groupBy: string | undefined,
  groupColor: (group: string) => string,
  hoveredGroup: string | null,
  groupValues: string[]
) => {
  return React.useMemo(() => {
    if (groupBy && groupValues.length > 0) {
      if (hoveredGroup) {
        return (
          <>
            {Object.entries(groupedPoints).map(([group, pts]) => {
              if (group === 'all' || !pts.length || group === hoveredGroup)
                return null;

              const color = groupColor(group);
              return (
                <Scatter
                  key={`dimmed-${group}`}
                  name={group}
                  data={pts}
                  fill={color}
                  shape="circle"
                  opacity={0.04}
                  isAnimationActive={false}
                />
              );
            })}

            <Scatter
              key={`highlighted-${hoveredGroup}`}
              name={hoveredGroup}
              data={groupedPoints[hoveredGroup] || []}
              fill={groupColor(hoveredGroup)}
              shape="circle"
              opacity={1}
              isAnimationActive={false}
            />
          </>
        );
      }

      return (
        <>
          {Object.entries(groupedPoints).map(([group, pts]) => {
            if (group === 'all' || !pts.length) return null;

            const color = groupColor(group);
            return (
              <Scatter
                key={group}
                name={group}
                data={pts}
                fill={color}
                shape="circle"
                isAnimationActive={false}
              />
            );
          })}
        </>
      );
    }

    return (
      <Scatter
        name="All points"
        data={groupedPoints.all || []}
        fill={TEAL_600}
        isAnimationActive={false}
      />
    );
  }, [groupedPoints, groupBy, groupColor, hoveredGroup, groupValues]);
};

export type ScatterPlotProps = {
  data: ExtractedCallData[];
  height?: number;
  initialXAxis?: string;
  initialYAxis?: string;
  groupKey?: string;
  hoveredGroup?: string | null;
};

export const ScatterPlot: React.FC<ScatterPlotProps> = ({
  data,
  height,
  initialXAxis = 'started_at',
  initialYAxis = 'latency',
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

  const groupBy = groupKey === 'op_name' ? 'op_name' : undefined;
  const groupValues = getGroupValues(data, groupBy);

  const groupColorMap = React.useMemo(() => {
    const map: Record<string, string> = {};
    groupValues.forEach((group, idx) => {
      map[group] = COLOR_PALETTE[idx % COLOR_PALETTE.length];
    });
    return map;
  }, [groupValues]);

  const groupColor = useCallback(
    (group: string) => groupColorMap[group] || '#000',
    [groupColorMap]
  );

  const points = React.useMemo(
    () =>
      data
        .map(d => {
          const group = groupBy
            ? getOpNameDisplay(d[groupBy as keyof ExtractedCallData] as string)
            : undefined;
          return {
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
            group,
            color: groupBy && group ? groupColor(group) : TEAL_600,
          };
        })
        .filter(pt => pt.x !== undefined && pt.y !== undefined),
    [data, initialXAxis, initialYAxis, xField, yField, groupBy, groupColor]
  );

  const xTickFormatter = React.useCallback(
    (value: any) => formatAxisTick(value, xField),
    [xField]
  );

  const yTickFormatter = React.useCallback(
    (value: any) => formatAxisTick(value, yField),
    [yField]
  );

  const pointsWithHighlight = React.useMemo(() => {
    if (!groupBy || !hoveredGroup) return points;

    return points.map(pt => ({
      ...pt,
      opacity: pt.group === hoveredGroup ? 1 : 0.04,
      size: pt.group === hoveredGroup ? 60 : 15,
    }));
  }, [points, groupBy, hoveredGroup]);

  const groupedPoints = React.useMemo(() => {
    if (!groupBy) return {all: pointsWithHighlight};

    const grouped: Record<string, typeof pointsWithHighlight> = {};
    pointsWithHighlight.forEach(pt => {
      const group = pt.group || 'Other';
      if (!grouped[group]) grouped[group] = [];
      grouped[group].push(pt);
    });
    return grouped;
  }, [pointsWithHighlight, groupBy]);

  const scatterComponents = useScatterPoints(
    groupedPoints,
    groupBy,
    groupColor,
    hoveredGroup,
    groupValues
  );

  return (
    <div style={chartContainerStyle}>
      {points.length === 0 ? (
        <span style={{color: '#8F8F8F'}}>No data to display</span>
      ) : (
        <div style={chartContentStyle}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{top: 2, right: 30, bottom: 2, left: 2}}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="x"
                name={xField?.label || initialXAxis}
                type="number"
                domain={['auto', 'auto']}
                tickFormatter={xTickFormatter}
                tick={{fontSize: 10, fontFamily: 'Source Sans Pro'}}
                tickSize={3}
              />
              <YAxis
                dataKey="y"
                name={yField?.label || initialYAxis}
                type="number"
                domain={['auto', 'auto']}
                tickFormatter={yTickFormatter}
                tick={{fontSize: 10, fontFamily: 'Source Sans Pro'}}
                tickSize={3}
              />
              <Tooltip
                cursor={{stroke: '#999', strokeDasharray: '5 5'}}
                content={<ScatterPlotTooltip xField={xField} yField={yField} />}
                isAnimationActive={false}
              />
              {scatterComponents}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
