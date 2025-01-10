import {fireOnRandom} from './WandbLoader';

describe('fireOnRandom', () => {
  test('should fire the callback', () => {
    let x = 0;
    const cb = () => {
      x = 1;
    };
    const samplingRate = 0.5;
    const randomNum = 0.3;

    fireOnRandom(cb, samplingRate, randomNum);

    expect(x).toBe(1);
  });

  test('should not fire the callback', () => {
    let x = 0;
    const cb = () => {
      x = 1;
    };
    const samplingRate = 0.5;
    const randomNum = 0.7;

    fireOnRandom(cb, samplingRate, randomNum);

    expect(x).toBe(0);
  });
  test('should throw on a bad sampling rate', () => {
    const cb = () => {};
    const samplingRate = 1.5;
    const randomNum = 0.7;

    expect(() => {
      fireOnRandom(cb, samplingRate, randomNum);
    }).toThrow();
  });
});
