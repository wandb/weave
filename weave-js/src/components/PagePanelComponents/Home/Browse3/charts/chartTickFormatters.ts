import {createDateTickFormatter, formatAxisTick} from './chartFormatting';
import {ChartAxisField} from './extractData';

export type AxisFieldType = ChartAxisField;

export const createAxisTickFormatters = (
  xField?: AxisFieldType,
  yField?: AxisFieldType,
  xDomain?: [number, number],
  yDomain?: [number, number]
) => {
  const xTickFormatter = (value: any) => {
    if (xField?.type === 'date' && xDomain) {
      const formatter = createDateTickFormatter(xDomain);
      return formatter(value);
    }
    return formatAxisTick(value, xField);
  };

  const yTickFormatter = (value: any) => {
    if (yField?.type === 'date' && yDomain) {
      const formatter = createDateTickFormatter(yDomain);
      return formatter(value);
    }
    return formatAxisTick(value, yField);
  };

  return {xTickFormatter, yTickFormatter};
};
