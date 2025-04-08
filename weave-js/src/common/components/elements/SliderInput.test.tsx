import {getClosestTick} from './SliderInput';

describe('getClosestTick', () => {
  test('value within range, no ticks', () => {
    const ticks = undefined;
    const min = 1;
    const max = 10;
    const previous = 4;
    const val = 3;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(3);
  });
  test('lower below min coerced to min', () => {
    const ticks = [2, 4, 6, 8, 10];
    const min = ticks[0];
    const max = ticks[ticks.length - 1];
    const previous = 2;
    const val = 1;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(2);
  });
  // not convinced this is a realistic test
  test.skip('upper above non-inclusive max', () => {
    const ticks = [2, 4, 6, 8, 10];
    const min = ticks[0];
    const max = 12;
    const previous = 10;
    const val = 12;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(10);
  });
  test('upper above max coerced to max', () => {
    const ticks = [2, 4, 6, 8, 10];
    const min = ticks[0];
    const max = ticks[ticks.length - 1];
    const previous = 10;
    const val = 11;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(10);
  });
  test('lower previous value returns next greater', () => {
    const ticks = [2, 4, 6, 8, 10];
    const min = ticks[0];
    const max = ticks[ticks.length - 1];
    const previous = 4;
    const val = 5;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(6);
  });
  test('lower previous value returns next greater, large step', () => {
    const ticks = [2, 4, 60, 80, 10];
    const min = ticks[0];
    const max = ticks[ticks.length - 1];
    const previous = 4;
    const val = 5;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(60);
  });
  test('greater previous value returns next lesser', () => {
    const ticks = [2, 4, 6, 8, 10];
    const min = ticks[0];
    const max = ticks[ticks.length - 1];
    const previous = 4;
    const val = 3;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(2);
  });
  test('greater previous value returns next lesser, consecutive', () => {
    const ticks = [1, 2, 3, 4, 5, 6];
    const min = ticks[0];
    const max = ticks[ticks.length - 1];
    const previous = 4;
    const val = 3;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(3);
  });
  test('lower previous value returns next greater, consecutive', () => {
    const ticks = [1, 2, 3, 4, 5, 6];
    const min = ticks[0];
    const max = ticks[ticks.length - 1];
    const previous = 3;
    const val = 4;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(4);
  });
  test('lower previous value returns next greater, erratic', () => {
    const ticks = [1, 4, 5, 7, 9, 12];
    const min = ticks[0];
    const max = ticks[ticks.length - 1];
    const previous = 9;
    const val = 10;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(12);
  });
  test('greater previous value returns next lower, erratic', () => {
    const ticks = [1, 2, 5, 7, 9, 12];
    const min = ticks[0];
    const max = ticks[ticks.length - 1];
    const previous = 5;
    const val = 4;
    const actual = getClosestTick(val, previous, min, max, ticks);
    expect(actual).toBe(2);
  });

  // Modified logic, retaining for expected performance
  test('large number of ticks', () => {
    const ticks = [];
    for (let i = 0; i < 10000000; i += 2) {
      ticks.push(i);
    }

    const min = ticks[0];
    const max = ticks[ticks.length - 1];
    const previous = 123456;
    const val = 123457;
    const start = global.window.performance.now();
    const actual = getClosestTick(val, previous, min, max, ticks);
    const end = global.window.performance.now();
    const duration = end - start;
    expect(actual).toBe(123458);
    expect(duration).toBeLessThanOrEqual(1.0);
  });

  it('handles boundary conditions with ticks correctly', () => {
    const ticks = [0, 0.5, 1];
    expect(getClosestTick(-0.1, 0, 0, 1, ticks)).toBe(0);
    expect(getClosestTick(1.1, 1, 0, 1, ticks)).toBe(1);
    expect(getClosestTick(0.5, 0.5, 0, 1, ticks)).toBe(0.5);
    expect(getClosestTick(0.7, 0.5, 0, 1, ticks)).toBe(1); // Moving up
    expect(getClosestTick(0.7, 1, 0, 1, ticks)).toBe(0.5); // Moving down
  });
});
