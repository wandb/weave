import _ from 'lodash';

import clamp from './clamp';

export function shiftInputByValue(
  ticks: number[] | undefined,
  strideLength: number | undefined,
  direction: number,
  v: number,
  min: number | undefined,
  max: number | undefined
) {
  let newValue;
  if (ticks) {
    if (strideLength) {
      const shift = direction * strideLength;
      newValue = clamp(shift + v, {
        min: ticks[0],
        max: ticks[ticks.length - 1],
      });
    } else {
      // When no stride length is set get the next valid step
      const currentIndex = _.sortedIndex(ticks, v);
      const finalIndex = clamp(currentIndex + direction, {
        min: 0,
        max: ticks.length - 1,
      });
      newValue = ticks[finalIndex];
    }
  } else {
    newValue = v + direction * (strideLength ?? 1);
    newValue = clamp(newValue, {min, max});
  }
  return newValue;
}
