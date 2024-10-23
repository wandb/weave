import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import moment from 'moment'; // Optional, for formatting timestamps
import {
  TEAL_300,
  TEAL_400,
  TEAL_500,
  TEAL_600,
} from '../../../../../../common/css/color.styles';

const data = [
  {timestamp: 1665619200000, value: 30}, // Example timestamps (in milliseconds)
  {timestamp: 1665705600000, value: 20},
  {timestamp: 1665792000000, value: 50},
  {timestamp: 1665878400000, value: 40},
  {timestamp: 1665964800000, value: 70},
  {timestamp: 1666051200000, value: 60},
];

type GradientAreaChartProps = {
  costAndTimeData: {
    value: number | undefined;
    timestamp: string;
  }[];
};

export const GradientAreaChart = ({
  costAndTimeData,
}: GradientAreaChartProps) => {
  const formattedData = costAndTimeData.map(d => ({
    ...d,
    timestamp: moment(d.timestamp).valueOf(), // Convert to milliseconds
  }));

  // Generate an array of unique monthly ticks
  const startMonth = moment(formattedData[0]?.timestamp).startOf('month');
  const endMonth = moment(
    formattedData[formattedData.length - 1]?.timestamp
  ).endOf('month');
  const monthlyTicks = [];

  let currentMonth = startMonth.clone();
  while (currentMonth <= endMonth) {
    monthlyTicks.push(currentMonth.valueOf());
    currentMonth.add(1, 'month');
  }

  const startTimestamp = formattedData[0]?.timestamp;
  const endTimestamp = formattedData[formattedData.length - 1]?.timestamp;

  return (
    <ResponsiveContainer width="100%" height={400}>
      <AreaChart
        data={formattedData}
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
          type="number"
          //   scale='point'
          //   domain={['auto', 'auto']}
          domain={['dataMin', 'dataMax']} // Use 'dataMin' and 'dataMax' for exact fit
          ticks={monthlyTicks} // Use generated monthly ticks
          tickFormatter={tick => moment(tick).format('MMM YYYY')}
        />

        <YAxis />
        <Tooltip
          labelFormatter={label => moment(label).format('MMM DD, YYYY')} // Format tooltip
          cursor={{stroke: TEAL_400, strokeWidth: 2}} // Set crosshair color and thickness
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke={TEAL_500}
          fillOpacity={1}
          fill="url(#colorValue)"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};

export default GradientAreaChart;
