/* This used to be the custom bouncing dots loader. But that broke
 * with an upgrade of react-spring, so we've switched back to the semantic loader.
 * The react-spring version also used 100% cpu, we should use an animated gif
 * instead if we want a custom loader */
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import React from 'react';
import {Loader, StrictLoaderProps} from 'semantic-ui-react';

import {
  ProfileData,
  useLifecycleProfiling,
} from './../hooks/useLifecycleProfiling';

export interface WandbLoaderProps extends StrictLoaderProps {
  className?: string;
  inline?: StrictLoaderProps['inline'];
  name?: string;
  size?: StrictLoaderProps['size'];
}

/**
 * @deprecated use the new wave loader instead
 */
const WandbLoader: React.FC<WandbLoaderProps> = React.memo(
  ({className, inline, size = 'huge'}) => {
    return <Loader active inline={inline} size={size} className={className} />;
  }
);

export default WandbLoader;

export type TrackedWandbLoaderProps = {
  /* Log the exception to an external service */
  captureException?: (error: unknown) => void;
  /* A unique name so we can differentiate between the loaders */
  name: string;
  /* the sampling rate as a percentage, defaults to 10% */
  samplingRate?: number;
  /* Optional callback fired when finished loading */
  onComplete?(name: string, data: Record<string, unknown> | undefined): void;
  /* Optional callback fired when started loading */
  onStart?(name: string): void;
  /**
   * Run an optional callback that returns an object with additional fields to
   * send to the analytics platform. Useful for getting lifecycle data from the
   * call-site w/out the generalized loader needing to know how to access state.
   * E.g. if you want to send a piece of data from Redux at the point of use, this
   * keeps us from needing to wire this component up that data store
   */
  profilingCb?: () => Record<string, unknown>;
  /* Tell me you're a Segment .track() event without telling me about Segment */
  track: (eventName: string, data: Record<string, unknown> | undefined) => void;
};

export const fireOnRandom = (
  cb: () => void,
  samplingRate: number,
  randomNum: number = Math.random()
) => {
  if (samplingRate > 1 || samplingRate < 0) {
    throw new Error('Sampling rate must be between 0 and 1');
  }

  if (randomNum < samplingRate) {
    cb();
  }
};

export const TrackedWandbLoader = ({
  captureException,
  name,
  profilingCb,
  samplingRate = 0.1,
  track,
  onComplete,
  onStart,
  ...props
}: TrackedWandbLoaderProps & WandbLoaderProps) => {
  useLifecycleProfiling(
    name,
    (data: ProfileData) => {
      try {
        // log the lifecycle for each loader to segment
        const additionalData = profilingCb ? profilingCb() : {};
        const trackedData = {
          componentId: data.id,
          duration: data.duration,
          ...additionalData,
        };
        if (onComplete) {
          onComplete(name, trackedData);
        }
        fireOnRandom(() => {
          track('wandb-loader-onscreen', trackedData);
        }, samplingRate);
      } catch (e) {
        // Tracking should be able to fail gracefully without breaking the app
        captureException?.(e);
      }
    },
    onStart
  );

  return <WandbLoader {...props} />;
};

export const TrackedWaveLoader = ({
  captureException,
  name,
  profilingCb,
  samplingRate = 0.1,
  track,
  onComplete,
  onStart,
  size,
}: TrackedWandbLoaderProps & {
  size: 'small' | 'huge';
}) => {
  useLifecycleProfiling(
    name,
    (data: ProfileData) => {
      try {
        // log the lifecycle for each loader to segment
        const additionalData = profilingCb ? profilingCb() : {};
        const trackedData = {
          componentId: data.id,
          duration: data.duration,
          ...additionalData,
        };
        if (onComplete) {
          onComplete(name, trackedData);
        }
        fireOnRandom(() => {
          track('wandb-loader-onscreen', trackedData);
        }, samplingRate);
      } catch (e) {
        // Tracking should be able to fail gracefully without breaking the app
        captureException?.(e);
      }
    },
    onStart
  );

  return <WaveLoader size={size} />;
};
