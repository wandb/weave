import {useEffect, useMemo, useState} from 'react';

type Loadable<T> = {loading: true} | {loading: false; data: T};

export const useAsyncToHook = <T,>(
  asyncFn: (...args: any[]) => Promise<T>,
  args: any[],
  self?: any
): Loadable<T> => {
  const [data, setData] = useState<T>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const mountState = {mounted: true};

    async function doFetch() {
      let fn = asyncFn;
      if (self != null) {
        fn = asyncFn.bind(self);
      }

      const res = await fn(...args);
      if (mountState.mounted) {
        setData(res);
        setLoading(false);
      }
    }

    doFetch();

    return () => {
      mountState.mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asyncFn, self, ...args]);

  return useMemo(() => {
    if (loading) {
      return {
        loading: true as const,
      };
    } else {
      if (data === undefined) {
        throw new Error('data is undefined');
      }
      return {
        loading: false as const,
        data,
      };
    }
  }, [data, loading]);
};

// export const useAllTypes = (projectConn: WFProject): Loadable<WFType[]> => {
//   return useAsyncToHook(projectConn.types, []);
// };
