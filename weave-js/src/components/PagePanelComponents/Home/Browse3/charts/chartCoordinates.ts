import {AxisPadding, ChartDimensions, ChartMargins} from './chartStyling';

export const createCoordinateClamp = (
  chartDimensions: ChartDimensions,
  margins: ChartMargins,
  axisPadding: AxisPadding = {left: 0, right: 0, top: 0, bottom: 0}
) => {
  return (x: number, y: number) => {
    const clampedX = Math.max(
      margins.left + axisPadding.left,
      Math.min(x, chartDimensions.width - margins.right - axisPadding.right)
    );
    const clampedY = Math.max(
      margins.top + axisPadding.top,
      Math.min(y, chartDimensions.height - margins.bottom - axisPadding.bottom)
    );
    return {x: clampedX, y: clampedY};
  };
};

export const createScreenToDataConverter = (
  chartDimensions: ChartDimensions,
  margins: ChartMargins,
  xDomain: [number, number],
  yDomain: [number, number]
) => {
  return (screenX: number, screenY: number) => {
    const plotWidth = chartDimensions.width - margins.left - margins.right;
    const plotHeight = chartDimensions.height - margins.top - margins.bottom;

    const xRatio = (screenX - margins.left) / plotWidth;
    const yRatio = (plotHeight - (screenY - margins.top)) / plotHeight;

    const dataX = xDomain[0] + xRatio * (xDomain[1] - xDomain[0]);
    const dataY = yDomain[0] + yRatio * (yDomain[1] - yDomain[0]);

    return {dataX, dataY};
  };
};
