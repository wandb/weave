import {getClosestTick} from './SliderInput';

describe('getClosestTick', () => {
  test('lower previous value returns next greater', () => {
    const ticks = [2, 4, 6, 8, 10];
    const previous = 4;
    const val = 5;
    expect(getClosestTick(ticks, val, previous)).toBe(6);
  });
  test('lower previous value returns next greater, large step', () => {
    const ticks = [2, 4, 60, 80, 10];
    const previous = 4;
    const val = 5;
    expect(getClosestTick(ticks, val, previous)).toBe(60);
  });
  test('greater previous value returns next lesser', () => {
    const ticks = [2, 4, 6, 8, 10];
    const previous = 4;
    const val = 3;
    const actual = getClosestTick(ticks, val, previous);
    expect(actual).toBe(2);
  });
  test('greater previous value returns next lesser, consecutive', () => {
    const ticks = [1, 2, 3, 4, 5, 6];
    const previous = 4;
    const val = 3;
    const actual = getClosestTick(ticks, val, previous);
    expect(actual).toBe(3);
  });
  test('lower previous value returns next greater, consecutive', () => {
    const ticks = [1, 2, 3, 4, 5, 6];
    const previous = 3;
    const val = 4;
    const actual = getClosestTick(ticks, val, previous);
    expect(actual).toBe(4);
  });
  test('lower previous value returns next greater, erratic', () => {
    const ticks = [1, 4, 5, 7, 9, 12];
    const previous = 9;
    const val = 10;
    const actual = getClosestTick(ticks, val, previous);
    expect(actual).toBe(12);
  });
  test('greater previous value returns next lower, erratic', () => {
    const ticks = [1, 2, 5, 7, 9, 12];
    const previous = 5;
    const val = 4;
    const actual = getClosestTick(ticks, val, previous);
    expect(actual).toBe(2);
  });

  // Modified logic, retaining for expected performance
  test('large number of ticks', () => {
    const ticks = [];
    for (let i = 0; i < 10000000; i += 2) {
      ticks.push(i);
    }

    const previous = 500000;
    const val = 500001;
    const start = Date.now();
    const actual = getClosestTick(ticks, val, previous);
    const end = Date.now();
    const duration = end - start;
    expect(actual).toBe(500002);
    expect(duration).toBeLessThanOrEqual(1);
  });
});
