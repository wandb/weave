/* This used to be the custom bouncing dots loader. But that broke
 * with an upgrade of react-spring, so we've switched back to the semantic loader.
 * The react-spring version also used 100% cpu, we should use an animated gif
 * instead if we want a custom loader */
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

const WandbLoader: React.FC<WandbLoaderProps> = React.memo(
  ({className, inline, size = 'huge'}) => {
    return <Loader active inline={inline} size={size} className={className} />;
  }
);

export default WandbLoader;

export interface TrackedWandbLoaderProps extends WandbLoaderProps {
  /* Log the exception to an external service */
  captureException?: (error: unknown) => void;
  /* A unique name so we can differentiate between the loaders */
  name: string;
  /**
   * Run an optional callback that returns an object with additional fields to
   * send to the analytics platform. Useful for getting lifecycle data from the
   * call-site w/out the generalized loader needing to know how to access state.
   * E.g. if you want to send a piece of data from Redux at the point of use, this
   * keeps us from needing to wire this component up that data store
   */
  profilingCb?: () => Record<string, unknown>;
  /* the sampling rate as a percentage, defaults to 10% */
  samplingRate?: number;
  /* Tell me you're a Segment .track() event without telling me about Segment */
  track: (eventName: string, data: Record<string, unknown> | undefined) => void;
  /* Optional callback fired when finished loading */
  onComplete?(name: string, data: Record<string, unknown> | undefined): void;
  /* Optional callback fired when started loading */
  onStart?(name: string): void;
}

export const TrackedWandbLoader = ({
  captureException,
  name,
  profilingCb,
  samplingRate = 0.1,
  track,
  onComplete,
  onStart,
  ...props
}: TrackedWandbLoaderProps) => {
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
        const randomNum = Number(Math.random().toString().slice(-2)); // take the last two digits off a random number
        if (randomNum <= samplingRate * 100) {
          track('wandb-loader-onscreen', trackedData);
        }
      } catch (e) {
        // Tracking should be able to fail gracefully without breaking the app
        captureException?.(e);
      }
    },
    onStart
  );

  return <WandbLoader {...props} />;
};
