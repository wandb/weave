import {getClosestTick} from './SliderInput';

describe('getClosestTick', () => {
  test('lower previous value returns next greater', () => {
    let ticks = [...new Set([2, 4, 6, 8, 10])],
      previous = 4,
      val = 5;

    expect(getClosestTick(ticks, val, previous)).toBe(6);
  });
  test('greater previous value returns next lesser', () => {
    let ticks = [...new Set([2, 4, 6, 8, 10])],
      previous = 4,
      val = 3;
    const actual = getClosestTick(ticks, val, previous);
    expect(actual).toBe(2);
  });
  test('greater previous value returns next lesser, consecutive', () => {
    let ticks = [...new Set([1, 2, 3, 4, 5, 6])],
      previous = 4,
      val = 3;
    const actual = getClosestTick(ticks, val, previous);
    expect(actual).toBe(3);
  });
  test('lower previous value returns next greater, consecutive', () => {
    let ticks = [...new Set([1, 2, 3, 4, 5, 6])],
      previous = 3,
      val = 4;
    const actual = getClosestTick(ticks, val, previous);
    expect(actual).toBe(4);
  });
  test('lower previous value returns next greater, erratic', () => {
    let ticks = [...new Set([1, 4, 5, 7, 9, 12])],
      previous = 9,
      val = 10;
    const actual = getClosestTick(ticks, val, previous);
    expect(actual).toBe(12);
  });
  test('greater previous value returns next lower, erratic', () => {
    let ticks = [...new Set([1, 2, 5, 7, 9, 12])],
      previous = 5,
      val = 4;
    const actual = getClosestTick(ticks, val, previous);
    expect(actual).toBe(2);
  });

  // Modified logic, retaining for expected performance
  test('large number of ticks', () => {
    let ticks = [...new Set<number>()],
      previous = 500000,
      val = 500001;

    for (let i = 0; i < 10000000; i += 2) {
      ticks.push(i);
    }
    const start = Date.now();
    const actual = getClosestTick(ticks, val, previous);
    const end = Date.now();
    const duration = end - start;
    expect(actual).toBe(500002);
    expect(duration).toBeLessThanOrEqual(1);
  });
});
