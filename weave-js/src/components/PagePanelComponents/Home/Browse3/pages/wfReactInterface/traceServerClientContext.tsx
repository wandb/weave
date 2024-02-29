import React, {
  createContext,
  FC,
  useCallback,
  useContext,
  useMemo,
} from 'react';

import {TraceServerClient} from './traceServerClient';

const TraceServerClientContext = createContext<TraceServerClient | null>(null);

export const useHasTraceServerClientContext = () => {
  const ctx = useContext(TraceServerClientContext);
  return ctx !== null;
};

export const useGetTraceServerClientContext = () => {
  const ctx = useContext(TraceServerClientContext);
  return useCallback(() => {
    if (ctx === null) {
      throw new Error('No TraceServerClientContext');
    }
    return ctx;
  }, [ctx]);
};

export const OptionalTraceServerClientContextProvider: FC<{
  baseUrl: string;
}> = ({baseUrl, children}) => {
  const client = useMemo(() => {
    if (baseUrl === '') {
      return null;
    }
    return new TraceServerClient(baseUrl);
  }, [baseUrl]);
  if (!client) {
    return <>{children}</>;
  }
  return (
    <TraceServerClientContext.Provider value={client}>
      {children}
    </TraceServerClientContext.Provider>
  );
};
