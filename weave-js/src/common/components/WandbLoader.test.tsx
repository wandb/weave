import {render} from '@testing-library/react';
import React from 'react';
import {vi} from 'vitest';

import {
  fireOnRandom,
  TrackedWandbLoader,
  TrackedWaveLoader,
} from './WandbLoader';

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

describe('<TrackedWaveLoader />', () => {
  it('tracks component lifecycle using track prop', () => {
    const track = vi.fn();
    const {unmount} = render(
      <TrackedWaveLoader
        name="my-wave-loader"
        track={track}
        size="huge"
        samplingRate={1}
      />
    );
    unmount();

    expect(track).toHaveBeenCalledTimes(1);
    const [trackName, {componentId, duration, start, stop}] =
      track.mock.lastCall;
    expect(trackName).toBe('wandb-loader-onscreen');
    expect(componentId).toBe('my-wave-loader');
    expect(typeof duration).toBe('number');
    expect(typeof start).toBe('number');
    expect(typeof stop).toBe('number');
  });
  it('tracks component lifecycle using onStart and onComplete', () => {
    const onStart = vi.fn();
    const onComplete = vi.fn();
    const {unmount} = render(
      <TrackedWaveLoader
        name="my-wave-loader"
        track={vi.fn()}
        onStart={onStart}
        onComplete={onComplete}
        size="huge"
      />
    );

    expect(onStart).toHaveBeenCalledTimes(1);
    expect(onComplete).not.toHaveBeenCalled();
    unmount();
    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});

describe('<TrackedWandbLoader />', () => {
  it('tracks component lifecycle using track prop', () => {
    const track = vi.fn();
    const {unmount} = render(
      <TrackedWandbLoader
        name="my-wandb-loader"
        track={track}
        size="huge"
        samplingRate={1}
      />
    );
    unmount();

    expect(track).toHaveBeenCalledTimes(1);
    const [trackName, {componentId, duration, start, stop}] =
      track.mock.lastCall;
    expect(trackName).toBe('wandb-loader-onscreen');
    expect(componentId).toBe('my-wandb-loader');
    expect(typeof duration).toBe('number');
    expect(typeof start).toBe('number');
    expect(typeof stop).toBe('number');
  });
  it('tracks component lifecycle using onStart and onComplete', () => {
    const onStart = vi.fn();
    const onComplete = vi.fn();
    const {unmount} = render(
      <TrackedWaveLoader
        name="my-wandb-loader"
        track={vi.fn()}
        onStart={onStart}
        onComplete={onComplete}
        size="huge"
      />
    );

    expect(onStart).toHaveBeenCalledTimes(1);
    expect(onComplete).not.toHaveBeenCalled();
    unmount();
    expect(onComplete).toHaveBeenCalledTimes(1);
  });
});
