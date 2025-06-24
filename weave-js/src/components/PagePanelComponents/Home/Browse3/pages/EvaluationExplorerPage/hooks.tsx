import {useDeepMemo} from '@wandb/weave/hookUtils';
import {useCallback, useEffect, useMemo, useState} from 'react';

import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';

type HookResult<T> =
  | {
      loading: true;
      data: T | null;
      error: Error | null;
    }
  | {
      loading: false;
      error: Error;
    }
  | {
      loading: false;
      data: T;
    };

export const promiseToHook = <TArgs extends any[], TReturn>(
  promiseFn: (...inputs: TArgs) => Promise<TReturn>
): ((...inputs: TArgs) => HookResult<TReturn>) => {
  const useFn = (...inputs: TArgs) => {
    const deepInputs = useDeepMemo(inputs);
    const [data, setData] = useState<TReturn | null>(null);
    const [error, setError] = useState<Error | null>(null);
    const [loading, setLoading] = useState(true);
    useEffect(() => {
      const resultsFor = deepInputs;
      let mounted = true;
      setLoading(true);
      promiseFn(...deepInputs)
        .then(res => {
          if (!mounted || resultsFor !== deepInputs) {
            return;
          }
          setData(res);
          setError(null);
        })
        .catch(error => {
          if (!mounted || resultsFor !== deepInputs) {
            return;
          }
          setData(null);
          setError(error);
        })
        .finally(() => {
          if (!mounted || resultsFor !== deepInputs) {
            return;
          }
          setLoading(false);
        });
      return () => {
        mounted = false;
      };
    }, [deepInputs]);
    const res = useMemo(() => {
      if (loading) {
        return {
          loading,
          data,
          error,
        };
      } else if (error) {
        return {
          loading,
          error,
        };
      } else if (data) {
        return {
          loading,
          data,
        };
      } else {
        console.error('Invalid state', {loading, data, error});
        return {
          loading: true as const,
          data: null,
          error: null,
        };
      }
    }, [loading, data, error]);
    return res;
  };
  return useFn;
};

export const bindClientHook = <TArgs extends any[], TReturn>(
  useHook: (client: TraceServerClient, ...inputs: TArgs) => HookResult<TReturn>
) => {
  const useFn = (...inputs: TArgs) => {
    const client = useGetTraceServerClientContext()();
    return useHook(client, ...inputs);
  };
  return useFn;
};
