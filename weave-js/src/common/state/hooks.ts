import _ from 'lodash';
import {useEffect, useRef, useState} from 'react';
import {useInView} from 'react-intersection-observer';

// From stackoverflow
export function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T>();
  useEffect(() => {
    ref.current = value;
  });
  return ref.current;
}

// Only return a new value if value changes by deep-comparison
// from one call to the next.
export const useDeepMemo = <T extends any>(
  value: T,
  equalityFn?: (a: T, b: T | undefined) => boolean
) => {
  equalityFn = equalityFn ?? _.isEqual;
  const ref = useRef<T>();
  const prev = usePrevious(value);
  if (!equalityFn(value, prev)) {
    ref.current = value;
  }
  return ref.current as T;
};

export const useGatedValue = <T extends any>(
  value: T,
  updateWhen: (val: T) => boolean
) => {
  const ref = useRef<T>(value);
  if (value !== ref.current && updateWhen(value)) {
    ref.current = value;
  }
  return ref.current;
};

// Returns true when domRef becomes onScreen for the first time after
// some time period, and stays true until value changes. Useful for
// scrolling loading
export function useWhenOnScreenAfterNewValueDebounced(
  value: any,
  debounceMs: number = 100
) {
  const {ref, inView} = useInView();
  const prevValue = usePrevious(value);
  const [ready, setReady] = useState(false);

  const [firstMomentOnScreen, setFirstMomentOnScreen] = useState<number | null>(
    null
  );
  const [queryMoment, setQueryMoment] = useState<number | null>(null);
  const mountMoment = useRef<number>(Date.now());
  const moment = Date.now();

  useEffect(() => {
    if (inView) {
      if (!ready && moment - mountMoment.current < 1000) {
        // Short-circuit if we've just mounted
        setFirstMomentOnScreen(moment);
        setReady(true);
      } else if (firstMomentOnScreen == null) {
        setFirstMomentOnScreen(moment);
        setTimeout(() => {
          if (queryMoment === null) {
            setQueryMoment(moment);
          }
        }, debounceMs + 1);
      } else if (!ready && firstMomentOnScreen + debounceMs < moment) {
        setReady(true);
      }
    } else if (value !== prevValue) {
      setFirstMomentOnScreen(null);
    }
  }, [
    inView,
    firstMomentOnScreen,
    prevValue,
    value,
    queryMoment,
    debounceMs,
    moment,
    ready,
  ]);
  return [ref, ready] as const;
}
