import React, {createContext, FC, useContext, useMemo} from 'react';

import {TraceServerClient} from './traceServerClient';

const TraceServerClientContext = createContext<TraceServerClient | null>(null);

export const useHasTraceServerClientContext = () => {
  const ctx = useContext(TraceServerClientContext);
  return ctx !== null;
};

export const useTraceServerClientContext = () => {
  const ctx = useContext(TraceServerClientContext);
  if (ctx === null) {
    throw new Error('No TraceServerClientContext');
  }
  return ctx;
};

export const TraceServerClientContextProvider: FC<{
  baseUrl: string;
}> = ({baseUrl, children}) => {
  const client = useMemo(() => {
    return new TraceServerClient(baseUrl);
  }, [baseUrl]);
  return (
    <TraceServerClientContext.Provider value={client}>
      {children}
    </TraceServerClientContext.Provider>
  );
};
