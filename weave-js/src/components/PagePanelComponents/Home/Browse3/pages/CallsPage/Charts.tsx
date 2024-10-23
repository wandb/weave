import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from 'recharts';
import moment from 'moment'; // Optional, for formatting timestamps
import {
  TEAL_300,
  TEAL_400,
  TEAL_500,
  TEAL_600,
} from '../../../../../../common/css/color.styles';
import _ from 'lodash';

type GradientAreaChartProps = {
  chartData: ChartData[];
};

type ChartData = {
  started_at: string;
  latency: number;
};

type LatencyData = {
  latency: number;
  started_at: string;
};

export const GradientAreaChart = ({chartData}: GradientAreaChartProps) => {
  const pointsPerGroup = 20; // Group data every 5 points for averaging

  const calculatePercentile = (sortedArray: number[], percentile: number) => {
    const index = Math.ceil((percentile / 100.0) * sortedArray.length) - 1;
    return sortedArray[index];
  };

  const aggregateLatencyData = (data: ChartData[]) => {
    // Group the data by 15-minute intervals
    return _(data)
      .groupBy(d =>
        moment(d.started_at)
          .startOf('minute')
          .minute(Math.floor(moment(d.started_at).minute() / 15) * 15)
          .format()
      ) // Group by 15-minute intervals
      .map((group, date) => {
        const latencies = group.map(d => d.latency).sort((a, b) => a - b);
        const p50 = calculatePercentile(latencies, 50);
        const p95 = calculatePercentile(latencies, 95);
        const p99 = calculatePercentile(latencies, 99);
        const formattedInterval = moment(date).format('MMM DD, YYYY HH:mm'); // Format the 15-minute interval label

        return {
          timestamp: formattedInterval,
          p50,
          p95,
          p99,
        };
      })
      .value();
  };

  const aggregatedData = aggregateLatencyData(chartData);

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart
        data={aggregatedData}
        margin={{top: 10, right: 30, left: 0, bottom: 0}}>
        <defs>
          <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={TEAL_300} stopOpacity={0.3} />
            <stop offset="95%" stopColor={TEAL_300} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="timestamp"
          type="category"
          domain={['auto', 'auto']}
          //   ticks={ticks}
          //   tickFormatter={tick => moment(tick).format('MMM DD, YYYY')}
        />
        <YAxis />
        <Tooltip
          labelFormatter={label => moment(label).format('MMM DD, YYYY')}
          cursor={{stroke: TEAL_400, strokeWidth: 2}}
        />
        <Line
          type="linear"
          dataKey="p50"
          stroke="#8884d8"
          dot={false}
          name="p50"
        />
        <Line
          type="linear"
          dataKey="p95"
          stroke="#82ca9d"
          dot={false}
          name="p95"
        />
        <Line
          type="linear"
          dataKey="p99"
          stroke="#ff7300"
          dot={false}
          name="p99"
        />
        {/* <Area
          type="monotone"
          dataKey="value"
          stroke={TEAL_500}
          fillOpacity={1}
          fill="url(#colorValue)"
        /> */}
      </LineChart>
    </ResponsiveContainer>
  );
};

export default GradientAreaChart;
