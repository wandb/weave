import {useEffect} from 'react';

export type ProfileData = {
  id: string;
  start: DOMHighResTimeStamp;
  stop: DOMHighResTimeStamp;
  duration: number;
};

/**
 * Tracks the duration that a component is mounted.
 * @param id - a unique identifier for the component
 * @param cb - a callback to handle the data, e.g. log it for performance profiling
 */
export function useLifecycleProfiling(
  id: string,
  cb: (d: ProfileData) => void,
  onStart?: (name: string) => void
) {
  useEffect(() => {
    const x = performance.now();

    if (onStart) {
      onStart(id);
    }

    return () => {
      const y = performance.now();

      cb({
        id,
        start: x,
        stop: y,
        duration: Math.ceil(y - x), // no need for fractional milliseconds
      });
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}
