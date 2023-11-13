import _ from 'lodash';
import {
  DependencyList,
  EffectCallback,
  MutableRefObject,
  SetStateAction,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {difference} from './data';
import {SetState} from './types';

// This hook is used in development for debugging state changes
// It shouldn't be used in production
export function useTraceUpdate(name: string, props: any) {
  const prev = useRef(props);
  useEffect(() => {
    const changedProps = Object.entries(props).reduce((ps, [k, v]) => {
      if (prev.current[k] !== v) {
        (ps as any)[k] = {
          prev: prev.current[k],
          current: v,
          diff: prev.current[k] != null ? difference(prev.current[k], v) : v,
        };
      }
      return ps;
    }, {});
    if (Object.keys(changedProps).length > 0) {
      console.log('Changed props:', name, changedProps);
    }
    prev.current = props;
  });
}

// Drop-in replacement for useEffect which
// will debounce the effect function across
// multiple re-renders and dep changes
export const useDebouncedEffect = (
  effect: EffectCallback,
  deps?: DependencyList,
  wait?: number,
  options?: _.DebounceSettings
) => {
  const debouncedFn = useRef(
    _.debounce(
      (innerFn: CallableFunction) => {
        innerFn();
      },
      wait,
      options
    )
  );
  const debouncedEffect = () => {
    debouncedFn.current(effect);
    return debouncedFn.current.cancel;
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(debouncedEffect, deps);
};

export function useMap<I, O>(
  kernel: (singleton: I, index?: number) => O,
  inputs: I[]
): O[] {
  return useMemo(() => inputs.map(kernel), [inputs, kernel]);
}

export function useUnzip<I extends {[key: string]: any}>(
  zipped: I[]
): {[K in keyof I]: Array<I[K]>} {
  return useMemo(() => {
    const keySet = new Set<keyof I>();
    zipped.forEach(item => {
      Object.keys(item).forEach(key => {
        keySet.add(key);
      });
    });
    return Array.from(keySet).reduce((acc, key) => {
      acc[key] = zipped.map(row => row[key]);
      return acc;
    }, {} as {[K in keyof I]: Array<I[K]>});
  }, [zipped]);
}

export function useIsFirstRender(): boolean {
  const isFirstRenderRef = useRef(true);
  useEffect(() => {
    isFirstRenderRef.current = false;
  }, []);
  return isFirstRenderRef.current;
}

// Same as useEffect/useLayoutEffect, but does not execute on first render.
// Useful for effects which are only supposed to run when dependencies change.
export function useEffectExceptFirstRender(
  effect: EffectCallback,
  deps?: DependencyList,
  layoutEffect = false
): void {
  const effectHook = layoutEffect ? useLayoutEffect : useEffect;
  const isFirstRender = useIsFirstRender();
  effectHook(() => {
    if (isFirstRender) {
      return;
    }
    effect();
  }, deps);
}

// Same as useEffect/useLayoutEffect, but runs an async effect.
// The async effect always waits until the previous invocation
// finishes before running the current render's invocation.
// Useful for async effects that should not overlap, like autosaving.
export function useSerialAsyncEffect(
  asyncEffect: () => Promise<void>,
  deps?: DependencyList,
  layoutEffect = false
): void {
  const effectHook = layoutEffect ? useLayoutEffect : useEffect;
  const effectCallback = useSerialAsyncEffectCallback(asyncEffect);
  effectHook(effectCallback, deps);
}

// useSerialAsyncEffect + useEffectExceptFirstRender
export function useSerialAsyncEffectExceptFirstRender(
  asyncEffect: () => Promise<void>,
  deps?: DependencyList,
  layoutEffect = false
): void {
  const effectCallback = useSerialAsyncEffectCallback(asyncEffect);
  useEffectExceptFirstRender(effectCallback, deps, layoutEffect);
}

function useSerialAsyncEffectCallback(
  asyncEffect: () => Promise<void>
): EffectCallback {
  const currentlyRunningPromiseRef = useRef<Promise<void> | null>(null);

  return () => {
    const previouslyRunningPromise = currentlyRunningPromiseRef.current;

    currentlyRunningPromiseRef.current = (async () => {
      // Wait for the previous effect to complete
      // before initiating another one
      if (previouslyRunningPromise != null) {
        await previouslyRunningPromise;
      }

      await asyncEffect();
    })();
  };
}

type ForceRemount = {
  shouldRenderNull: boolean;
};

// Sometimes, we want component state to completely reset when something changes.
// We can do this (quite hackily) by using this hook in the parent component
// and rendering `null` for exactly one render cycle.
// On the next render cycle, the child component should be remounted by the parent.
export function useForceRemountOnChange(deps: DependencyList): ForceRemount {
  const [shouldRenderNull, setShouldRenderNull] = useState(false);

  useEffectExceptFirstRender(() => {
    setShouldRenderNull(true);
  }, deps);

  useLayoutEffect(() => {
    if (shouldRenderNull) {
      setShouldRenderNull(false);
    }
  }, [shouldRenderNull]);

  return {shouldRenderNull};
}

type UseBooleanStateResult = {
  state: boolean;
  setTrue: () => void;
  setFalse: () => void;
  toggle: () => void;
};

export function useBooleanState(initValue: boolean): UseBooleanStateResult {
  const [state, setState] = useState(initValue);
  const setTrue = useCallback(() => setState(true), []);
  const setFalse = useCallback(() => setState(false), []);
  const toggle = useCallback(() => setState(prevState => !prevState), []);
  return {state, setTrue, setFalse, toggle};
}

type UseSyncedStateParams<T> = {
  stateToSyncWith: T;
  setStateToSyncWith: (state: T) => void;
};

type UseSyncedStateResult<T> = {
  state: T;
  setState: (newState: T) => void;
};

export function useSyncedState<T>({
  stateToSyncWith,
  setStateToSyncWith,
}: UseSyncedStateParams<T>): UseSyncedStateResult<T> {
  const [state, setState] = useState(stateToSyncWith);
  useEffect(() => {
    setState(stateToSyncWith);
  }, [stateToSyncWith]);

  const setStateAndStateToSyncWith = useCallback(
    (newState: T) => {
      setState(newState);
      setStateToSyncWith(newState);
    },
    [setStateToSyncWith]
  );

  return {state, setState: setStateAndStateToSyncWith};
}

type UseStateWithRefResult<T> = [T, SetState<T>, MutableRefObject<T>];

export function useStateWithRef<T>(initValue: T): UseStateWithRefResult<T> {
  const [state, setState] = useState(initValue);
  const stateRef = useRef(state);

  const setStateAndRef = useCallback((v: SetStateAction<T>) => {
    stateRef.current = isNewStateFunction(v) ? v(stateRef.current) : v;
    setState(v);
  }, []);

  return [state, setStateAndRef, stateRef];
}

function isNewStateFunction<T>(v: SetStateAction<T>): v is (prevState: T) => T {
  return typeof v === `function`;
}

export const useUpdatingState = <T extends any>(initialValue: T) => {
  const [state, setState] = useState(initialValue);

  useEffect(() => {
    setState(initialValue);
  }, [initialValue]);

  return [state, setState] as const;
};

export function useIsMounted() {
  // This hook exposes a method to check if a component is mounted. The returned
  // function will be a stable reference across renders, so it is safe to use in
  // dependencies. This is useful to use in callbacks for example to check if a
  // component is still mounted before updating state. Stylistically, I think it
  // is more readable to maintain mount state near the useEffect that uses it.
  // However, with non-useEffect hooks, we sometimes want to check if a
  // component is mounted before updating state. In those cases, we can use this
  // hook.
  const isMountedRef = useRef(false);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);
  return useCallback(() => isMountedRef.current, []);
}
