import React from 'react';
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {BLUE_500} from '../../../../../common/css/color.styles';

// Export the chart data types from the types file
export * from './ChartTypes';

// Utility: detect if a field is a timestamp field
const TIMESTAMP_FIELDS = ['started_at', 'ended_at'];
function isTimestampField(field: string) {
  return TIMESTAMP_FIELDS.includes(field);
}
function toTimestamp(val: any) {
  if (typeof val === 'string' && !isNaN(Date.parse(val))) {
    return new Date(val).getTime();
  }
  return val;
}
function formatTimestamp(val: any) {
  if (typeof val === 'number') {
    const d = new Date(val);
    if (!isNaN(d.getTime())) {
      return d.toLocaleString();
    }
  }
  if (typeof val === 'string' && !isNaN(Date.parse(val))) {
    return new Date(val).toLocaleString();
  }
  return val;
}

export type ScatterPlotProps = {
  data: any[];
  height: number | string;
  xLabel: string;
  yLabel: string;
  xField?: string;
  yField?: string;
  color?: string;
  xDomain?: any[];
  yDomain?: any[];
};

export const ScatterPlot: React.FC<ScatterPlotProps> = ({
  data,
  height,
  xLabel,
  yLabel,
  xField,
  yField,
  color = BLUE_500,
  xDomain,
  yDomain,
}) => {
  const xKey = xField || xLabel;
  const yKey = yField || yLabel;
  const mappedData = React.useMemo(
    () =>
      data.map(d => ({
        ...d,
        [xKey]: isTimestampField(xKey) ? toTimestamp(d[xKey]) : d[xKey],
        [yKey]: d[yKey],
        x: isTimestampField(xKey) ? toTimestamp(d[xKey]) : d[xKey],
        y: d[yKey],
      })),
    [data, xKey, yKey]
  );
  const axisFormatter = (val: any) => {
    return isTimestampField(xKey) ? formatTimestamp(val) : val;
  };

  // Custom tooltip for better x/y labeling
  const CustomTooltip = ({active, payload, label}: any) => {
    if (!active || !payload || !payload.length) return null;
    const point = payload[0].payload;
    return (
      <div
        style={{
          background: '#222',
          color: '#fff',
          padding: 8,
          borderRadius: 4,
        }}>
        <div>
          <b>{xLabel}:</b> {axisFormatter(point[xKey])}
        </div>
        <div>
          <b>{yLabel}:</b> {point[yKey]}
        </div>
      </div>
    );
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: typeof height === 'number' ? `${height}px` : height,
      }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart data={mappedData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey={xKey}
            name={xLabel}
            type={'number'}
            domain={xDomain || ['auto', 'auto']}
            tickFormatter={axisFormatter}
          />
          <YAxis
            dataKey={yKey}
            name={yLabel}
            domain={yDomain || ['auto', 'auto']}
          />
          <Tooltip content={<CustomTooltip />} />
          <Scatter dataKey={yKey} fill={color} name={yLabel} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
};
