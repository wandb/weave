import {useEffect, useMemo, useState} from 'react';

import {WFProject} from './types';

type Loadable<T> = {loading: true} | {loading: false; data: T};

// type UseAsyncToHookType<FT> = FT extends (...args: any[]) => Promise<infer T> ? T : never;

const useAsyncToHook = <
  FT extends (...args: any[]) => Promise<any>,
  T = Awaited<ReturnType<FT>>
>(
  asyncFn: FT,
  args: Parameters<FT>,
  self?: any
): Loadable<T> => {
  const [data, setData] = useState<T>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const mountState = {mounted: true};

    async function doFetch() {
      let fn = asyncFn;
      if (self != null) {
        fn = asyncFn.bind(self) as FT;
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

export const useProjectTypeVersions = (project: WFProject) => {
  return useAsyncToHook(project.typeVersions, [], project);
};

export const useProjectTypes = (project: WFProject) => {
  return useAsyncToHook(project.types, [], project);
};

export const useProjectOpVersion = (
  project: WFProject,
  args: Parameters<WFProject['opVersion']>
) => {
  return useAsyncToHook(project.opVersion, args, project);
};

export const useProjectOpVersions = (project: WFProject) => {
  return useAsyncToHook(project.opVersions, [], project);
};

export const useProjectTypeVersion = (
  project: WFProject,
  args: Parameters<WFProject['typeVersion']>
) => {
  return useAsyncToHook(project.typeVersion, args, project);
};
